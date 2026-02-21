"""
Oda Atama Modülü
- Oda yönetimi (CRUD)
- Manuel oda atama
- Scan sonrası otomatik oda atama
- Müsait oda kontrolü
"""
from datetime import datetime, timezone
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase
import uuid


# Oda tipleri
ROOM_TYPES = [
    {"code": "standard", "name": "Standart Oda"},
    {"code": "deluxe", "name": "Deluxe Oda"},
    {"code": "suite", "name": "Süit"},
    {"code": "family", "name": "Aile Odası"},
    {"code": "single", "name": "Tek Kişilik"},
    {"code": "double", "name": "Çift Kişilik"},
    {"code": "twin", "name": "İki Yataklı"},
]

ROOM_STATUSES = ["available", "occupied", "cleaning", "maintenance", "reserved"]


async def create_room(db: AsyncIOMotorDatabase, room_number: str, room_type: str = "standard",
                      floor: int = 1, capacity: int = 2, property_id: str = None,
                      features: list = None) -> dict:
    """Yeni oda oluştur"""
    col = db["rooms"]
    
    # Check if room already exists
    existing = await col.find_one({"room_number": room_number, "property_id": property_id})
    if existing:
        raise ValueError(f"Oda {room_number} zaten mevcut")
    
    room_doc = {
        "room_id": str(uuid.uuid4()),
        "room_number": room_number,
        "room_type": room_type,
        "floor": floor,
        "capacity": capacity,
        "property_id": property_id or "default",
        "status": "available",
        "current_guest_ids": [],
        "features": features or [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    
    result = await col.insert_one(room_doc)
    room_doc["_id"] = result.inserted_id
    return room_doc


async def list_rooms(db: AsyncIOMotorDatabase, property_id: str = None,
                     status: str = None, room_type: str = None,
                     floor: int = None) -> list:
    """Odaları listele"""
    col = db["rooms"]
    query = {}
    if property_id:
        query["property_id"] = property_id
    if status:
        query["status"] = status
    if room_type:
        query["room_type"] = room_type
    if floor is not None:
        query["floor"] = floor
    
    cursor = col.find(query).sort("room_number", 1)
    rooms = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        rooms.append(doc)
    return rooms


async def get_room(db: AsyncIOMotorDatabase, room_id: str) -> Optional[dict]:
    """Oda detayını getir"""
    col = db["rooms"]
    doc = await col.find_one({"room_id": room_id})
    if doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


async def update_room(db: AsyncIOMotorDatabase, room_id: str, updates: dict) -> Optional[dict]:
    """Oda bilgilerini güncelle"""
    col = db["rooms"]
    updates["updated_at"] = datetime.now(timezone.utc)
    result = await col.update_one({"room_id": room_id}, {"$set": updates})
    if result.matched_count == 0:
        return None
    doc = await col.find_one({"room_id": room_id})
    if doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


async def assign_room(db: AsyncIOMotorDatabase, room_id: str, guest_id: str) -> dict:
    """Misafire oda ata"""
    col = db["rooms"]
    room = await col.find_one({"room_id": room_id})
    if not room:
        raise ValueError("Oda bulunamadı")
    
    if room["status"] not in ("available", "reserved"):
        raise ValueError(f"Oda müsait değil (durum: {room['status']})")
    
    current_guests = room.get("current_guest_ids", [])
    if len(current_guests) >= room.get("capacity", 2):
        raise ValueError("Oda kapasitesi dolu")
    
    if guest_id not in current_guests:
        current_guests.append(guest_id)
    
    status = "occupied" if len(current_guests) > 0 else "available"
    
    await col.update_one(
        {"room_id": room_id},
        {"$set": {
            "current_guest_ids": current_guests,
            "status": status,
            "updated_at": datetime.now(timezone.utc),
        }}
    )
    
    # Update guest with room info
    guests_col = db["guests"]
    from bson import ObjectId
    try:
        await guests_col.update_one(
            {"_id": ObjectId(guest_id)},
            {"$set": {
                "room_number": room["room_number"],
                "room_id": room_id,
                "updated_at": datetime.now(timezone.utc),
            }}
        )
    except Exception:
        pass
    
    # Create assignment record
    assignments_col = db["room_assignments"]
    assignment = {
        "assignment_id": str(uuid.uuid4()),
        "room_id": room_id,
        "room_number": room["room_number"],
        "guest_id": guest_id,
        "assigned_at": datetime.now(timezone.utc),
        "released_at": None,
        "status": "active",
    }
    await assignments_col.insert_one(assignment)
    
    updated_room = await col.find_one({"room_id": room_id})
    if updated_room:
        updated_room["id"] = str(updated_room.pop("_id"))
    return {"room": updated_room, "assignment": assignment}


async def release_room(db: AsyncIOMotorDatabase, room_id: str, guest_id: str = None) -> dict:
    """Odayı serbest bırak"""
    col = db["rooms"]
    room = await col.find_one({"room_id": room_id})
    if not room:
        raise ValueError("Oda bulunamadı")
    
    current_guests = room.get("current_guest_ids", [])
    if guest_id:
        current_guests = [g for g in current_guests if g != guest_id]
    else:
        current_guests = []
    
    status = "cleaning" if len(current_guests) == 0 else "occupied"
    
    await col.update_one(
        {"room_id": room_id},
        {"$set": {
            "current_guest_ids": current_guests,
            "status": status,
            "updated_at": datetime.now(timezone.utc),
        }}
    )
    
    # Update assignment record
    assignments_col = db["room_assignments"]
    query = {"room_id": room_id, "status": "active"}
    if guest_id:
        query["guest_id"] = guest_id
    await assignments_col.update_many(
        query,
        {"$set": {"status": "released", "released_at": datetime.now(timezone.utc)}}
    )
    
    updated_room = await col.find_one({"room_id": room_id})
    if updated_room:
        updated_room["id"] = str(updated_room.pop("_id"))
    return updated_room


async def auto_assign_room(db: AsyncIOMotorDatabase, guest_id: str,
                           property_id: str = None, preferred_type: str = None) -> Optional[dict]:
    """Scan sonrası otomatik oda atama"""
    col = db["rooms"]
    
    query = {"status": "available"}
    if property_id:
        query["property_id"] = property_id
    if preferred_type:
        query["room_type"] = preferred_type
    
    # Find first available room
    room = await col.find_one(query, sort=[("floor", 1), ("room_number", 1)])
    if not room:
        return None
    
    result = await assign_room(db, room["room_id"], guest_id)
    return result


async def get_room_stats(db: AsyncIOMotorDatabase, property_id: str = None) -> dict:
    """Oda istatistikleri"""
    col = db["rooms"]
    query = {}
    if property_id:
        query["property_id"] = property_id
    
    total = await col.count_documents(query)
    available = await col.count_documents({**query, "status": "available"})
    occupied = await col.count_documents({**query, "status": "occupied"})
    cleaning = await col.count_documents({**query, "status": "cleaning"})
    maintenance = await col.count_documents({**query, "status": "maintenance"})
    reserved = await col.count_documents({**query, "status": "reserved"})
    
    return {
        "total": total,
        "available": available,
        "occupied": occupied,
        "cleaning": cleaning,
        "maintenance": maintenance,
        "reserved": reserved,
        "occupancy_rate": round((occupied / total * 100), 1) if total > 0 else 0,
    }
