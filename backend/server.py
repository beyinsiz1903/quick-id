from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import json
import base64
import asyncio
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import uuid

load_dotenv()

app = FastAPI(title="Quick ID Reader")

# CORS
origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "quick_id_reader")
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# Collections
guests_col = db["guests"]
scans_col = db["scans"]

# Emergent LLM Key
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

# System prompt for ID extraction
ID_EXTRACTION_PROMPT = """You are an expert ID document reader for a hotel check-in system. You analyze images of identity documents (ID cards, passports, driver's licenses) and extract structured information.

IMPORTANT RULES:
1. Extract ALL visible text fields from the document
2. Return ONLY valid JSON - no markdown, no extra text, no code blocks
3. If a field is not visible or unclear, set it to null
4. Normalize dates to YYYY-MM-DD format
5. For gender, use "M" (Male/Erkek) or "F" (Female/Kadin)
6. Detect the document type automatically
7. If the image is blurry, cropped, or not an ID document, set "is_valid" to false
8. For Turkish ID cards (TC Kimlik), extract TC Kimlik No
9. For passports, extract passport number and MRZ data if visible
10. For driver's licenses, extract license number

Return this exact JSON structure (no markdown, no code fences):
{
    "is_valid": true or false,
    "document_type": "tc_kimlik" | "passport" | "drivers_license" | "old_nufus_cuzdani" | "other",
    "first_name": "string or null",
    "last_name": "string or null",
    "id_number": "string or null",
    "birth_date": "YYYY-MM-DD or null",
    "gender": "M" | "F" | null,
    "nationality": "string or null",
    "expiry_date": "YYYY-MM-DD or null",
    "document_number": "string or null",
    "birth_place": "string or null",
    "issue_date": "YYYY-MM-DD or null",
    "mother_name": "string or null",
    "father_name": "string or null",
    "address": "string or null",
    "warnings": ["list of any issues or uncertain fields"],
    "raw_extracted_text": "all visible text from the document"
}"""


def serialize_doc(doc):
    """Convert MongoDB document to JSON-serializable dict"""
    if doc is None:
        return None
    result = {}
    for key, value in doc.items():
        if key == "_id":
            result["id"] = str(value)
        elif isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, list):
            result[key] = [serialize_doc(v) if isinstance(v, dict) else str(v) if isinstance(v, (ObjectId, datetime)) else v for v in value]
        elif isinstance(value, dict):
            result[key] = serialize_doc(value)
        else:
            result[key] = value
    return result


# --- Pydantic Models ---
class ScanRequest(BaseModel):
    image_base64: str

class GuestCreate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    id_number: Optional[str] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    birth_place: Optional[str] = None
    expiry_date: Optional[str] = None
    issue_date: Optional[str] = None
    mother_name: Optional[str] = None
    father_name: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    scan_id: Optional[str] = None

class GuestUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    id_number: Optional[str] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    birth_place: Optional[str] = None
    expiry_date: Optional[str] = None
    issue_date: Optional[str] = None
    mother_name: Optional[str] = None
    father_name: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


async def extract_id_data(image_base64: str) -> dict:
    """Extract data from ID image using OpenAI Vision"""
    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
    
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"scan-{uuid.uuid4().hex[:8]}",
        system_message=ID_EXTRACTION_PROMPT
    )
    chat.with_model("openai", "gpt-4o")
    
    # Clean base64 string
    if "," in image_base64:
        image_base64 = image_base64.split(",")[1]
    
    image_content = ImageContent(image_base64=image_base64)
    user_message = UserMessage(
        text="Analyze this identity document and extract all fields. Return ONLY the JSON structure, no markdown.",
        file_contents=[image_content]
    )
    
    response = await chat.send_message(user_message)
    
    # Parse JSON from response
    json_str = response.strip()
    if json_str.startswith("```"):
        lines = json_str.split("\n")
        json_str = "\n".join(lines[1:-1]) if len(lines) > 2 else json_str[3:-3]
        json_str = json_str.strip()
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Try to find JSON in the response
        start = json_str.find("{")
        end = json_str.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(json_str[start:end])
        raise ValueError(f"Could not parse JSON from response: {json_str[:200]}")


# ===== API ROUTES =====

@app.get("/api/health")
async def health():
    return {"status": "healthy", "service": "Quick ID Reader"}


# --- Scan Endpoints ---
@app.post("/api/scan")
async def scan_id(request: ScanRequest):
    """Scan an ID document and extract data"""
    try:
        extracted = await extract_id_data(request.image_base64)
        
        # Save scan record
        scan_doc = {
            "extracted_data": extracted,
            "is_valid": extracted.get("is_valid", False),
            "document_type": extracted.get("document_type", "other"),
            "created_at": datetime.now(timezone.utc),
            "status": "completed",
            "warnings": extracted.get("warnings", [])
        }
        
        result = await scans_col.insert_one(scan_doc)
        scan_doc["_id"] = result.inserted_id
        
        return {
            "success": True,
            "scan": serialize_doc(scan_doc),
            "extracted_data": extracted
        }
    except Exception as e:
        # Save failed scan
        scan_doc = {
            "status": "failed",
            "error": str(e),
            "created_at": datetime.now(timezone.utc)
        }
        await scans_col.insert_one(scan_doc)
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@app.get("/api/scans")
async def get_scans(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Get scan history"""
    skip = (page - 1) * limit
    total = await scans_col.count_documents({})
    cursor = scans_col.find({}).sort("created_at", -1).skip(skip).limit(limit)
    scans = [serialize_doc(doc) async for doc in cursor]
    return {"scans": scans, "total": total, "page": page, "limit": limit}


# --- Guest Endpoints ---
@app.post("/api/guests")
async def create_guest(guest: GuestCreate):
    """Create a new guest from scan data"""
    guest_doc = {
        **guest.model_dump(exclude_none=True),
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "check_in_at": None,
        "check_out_at": None,
        "scan_ids": [guest.scan_id] if guest.scan_id else []
    }
    if "scan_id" in guest_doc:
        del guest_doc["scan_id"]
    
    result = await guests_col.insert_one(guest_doc)
    guest_doc["_id"] = result.inserted_id
    return {"success": True, "guest": serialize_doc(guest_doc)}


@app.get("/api/guests")
async def get_guests(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    nationality: Optional[str] = None,
    document_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
):
    """Get guests with filters"""
    query = {}
    
    if search:
        query["$or"] = [
            {"first_name": {"$regex": search, "$options": "i"}},
            {"last_name": {"$regex": search, "$options": "i"}},
            {"id_number": {"$regex": search, "$options": "i"}},
            {"document_number": {"$regex": search, "$options": "i"}}
        ]
    
    if status:
        query["status"] = status
    
    if nationality:
        query["nationality"] = {"$regex": nationality, "$options": "i"}
    
    if document_type:
        query["document_type"] = document_type
    
    if date_from:
        try:
            from_dt = datetime.fromisoformat(date_from)
            query.setdefault("created_at", {})["$gte"] = from_dt
        except ValueError:
            pass
    
    if date_to:
        try:
            to_dt = datetime.fromisoformat(date_to)
            query.setdefault("created_at", {})["$lte"] = to_dt
        except ValueError:
            pass
    
    skip = (page - 1) * limit
    total = await guests_col.count_documents(query)
    cursor = guests_col.find(query).sort("created_at", -1).skip(skip).limit(limit)
    guests = [serialize_doc(doc) async for doc in cursor]
    
    return {"guests": guests, "total": total, "page": page, "limit": limit}


@app.get("/api/guests/{guest_id}")
async def get_guest(guest_id: str):
    """Get a single guest"""
    try:
        doc = await guests_col.find_one({"_id": ObjectId(guest_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid guest ID")
    
    if not doc:
        raise HTTPException(status_code=404, detail="Guest not found")
    return {"guest": serialize_doc(doc)}


@app.patch("/api/guests/{guest_id}")
async def update_guest(guest_id: str, update: GuestUpdate):
    """Update guest fields"""
    try:
        oid = ObjectId(guest_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid guest ID")
    
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    result = await guests_col.update_one({"_id": oid}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Guest not found")
    
    doc = await guests_col.find_one({"_id": oid})
    return {"success": True, "guest": serialize_doc(doc)}


@app.delete("/api/guests/{guest_id}")
async def delete_guest(guest_id: str):
    """Delete a guest"""
    try:
        oid = ObjectId(guest_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid guest ID")
    
    result = await guests_col.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Guest not found")
    return {"success": True}


@app.post("/api/guests/{guest_id}/checkin")
async def checkin_guest(guest_id: str):
    """Check-in a guest"""
    try:
        oid = ObjectId(guest_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid guest ID")
    
    now = datetime.now(timezone.utc)
    result = await guests_col.update_one(
        {"_id": oid},
        {"$set": {"status": "checked_in", "check_in_at": now, "updated_at": now}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Guest not found")
    
    doc = await guests_col.find_one({"_id": oid})
    return {"success": True, "guest": serialize_doc(doc)}


@app.post("/api/guests/{guest_id}/checkout")
async def checkout_guest(guest_id: str):
    """Check-out a guest"""
    try:
        oid = ObjectId(guest_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid guest ID")
    
    now = datetime.now(timezone.utc)
    result = await guests_col.update_one(
        {"_id": oid},
        {"$set": {"status": "checked_out", "check_out_at": now, "updated_at": now}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Guest not found")
    
    doc = await guests_col.find_one({"_id": oid})
    return {"success": True, "guest": serialize_doc(doc)}


# --- Dashboard Stats ---
@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    """Get dashboard overview stats"""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    total_guests = await guests_col.count_documents({})
    
    today_checkins = await guests_col.count_documents({
        "status": "checked_in",
        "check_in_at": {"$gte": today_start}
    })
    
    today_checkouts = await guests_col.count_documents({
        "status": "checked_out",
        "check_out_at": {"$gte": today_start}
    })
    
    pending_reviews = await guests_col.count_documents({"status": "pending"})
    
    currently_checked_in = await guests_col.count_documents({"status": "checked_in"})
    
    total_scans = await scans_col.count_documents({})
    today_scans = await scans_col.count_documents({
        "created_at": {"$gte": today_start}
    })
    
    # Recent scans (last 5)
    recent_cursor = scans_col.find({}).sort("created_at", -1).limit(5)
    recent_scans = [serialize_doc(doc) async for doc in recent_cursor]
    
    # Recent guests (last 5)
    recent_guests_cursor = guests_col.find({}).sort("created_at", -1).limit(5)
    recent_guests = [serialize_doc(doc) async for doc in recent_guests_cursor]
    
    # Weekly stats (last 7 days)
    from datetime import timedelta
    weekly_stats = []
    for i in range(6, -1, -1):
        day_start = (datetime.now(timezone.utc) - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        count = await guests_col.count_documents({
            "created_at": {"$gte": day_start, "$lt": day_end}
        })
        weekly_stats.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "day": day_start.strftime("%a"),
            "count": count
        })
    
    return {
        "total_guests": total_guests,
        "today_checkins": today_checkins,
        "today_checkouts": today_checkouts,
        "pending_reviews": pending_reviews,
        "currently_checked_in": currently_checked_in,
        "total_scans": total_scans,
        "today_scans": today_scans,
        "recent_scans": recent_scans,
        "recent_guests": recent_guests,
        "weekly_stats": weekly_stats
    }


# --- Export ---
@app.get("/api/exports/guests.json")
async def export_guests_json(
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
):
    """Export guests as JSON"""
    query = {}
    if status:
        query["status"] = status
    if date_from:
        try:
            query.setdefault("created_at", {})["$gte"] = datetime.fromisoformat(date_from)
        except ValueError:
            pass
    if date_to:
        try:
            query.setdefault("created_at", {})["$lte"] = datetime.fromisoformat(date_to)
        except ValueError:
            pass
    
    cursor = guests_col.find(query).sort("created_at", -1)
    guests = [serialize_doc(doc) async for doc in cursor]
    return {"guests": guests, "total": len(guests), "exported_at": datetime.now(timezone.utc).isoformat()}


@app.get("/api/exports/guests.csv")
async def export_guests_csv(
    status: Optional[str] = None
):
    """Export guests as CSV"""
    from fastapi.responses import StreamingResponse
    import io
    import csv
    
    query = {}
    if status:
        query["status"] = status
    
    cursor = guests_col.find(query).sort("created_at", -1)
    guests = [serialize_doc(doc) async for doc in cursor]
    
    output = io.StringIO()
    writer = csv.writer(output)
    headers = ["Ad", "Soyad", "Kimlik No", "Dogum Tarihi", "Cinsiyet", "Uyruk", "Belge Turu", "Durum", "Check-in", "Check-out", "Olusturma"]
    writer.writerow(headers)
    
    for g in guests:
        writer.writerow([
            g.get("first_name", ""),
            g.get("last_name", ""),
            g.get("id_number", ""),
            g.get("birth_date", ""),
            g.get("gender", ""),
            g.get("nationality", ""),
            g.get("document_type", ""),
            g.get("status", ""),
            g.get("check_in_at", ""),
            g.get("check_out_at", ""),
            g.get("created_at", "")
        ])
    
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=misafirler.csv"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
