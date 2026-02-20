from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os
import json
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import uuid
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

load_dotenv()

from auth import (
    hash_password, verify_password, create_token,
    require_auth, require_admin, get_current_user, security, decode_token
)
from kvkk import get_settings, update_settings, run_data_cleanup, anonymize_guest


# --- Rate Limiter Setup ---
def get_user_or_ip(request: Request) -> str:
    """Rate limit key: use authenticated user email if available, else IP."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = decode_token(token)
        if payload and payload.get("email"):
            return payload["email"]
    return get_remote_address(request)

limiter = Limiter(key_func=get_user_or_ip)

app = FastAPI(title="Quick ID Reader")
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "İstek limiti aşıldı. Lütfen biraz bekleyin ve tekrar deneyin.", "retry_after": str(exc.detail)}
    )

# CORS
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
audit_col = db["audit_logs"]
users_col = db["users"]

# Emergent LLM Key
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

# System prompt for ID extraction
ID_EXTRACTION_PROMPT = """You are an expert ID document reader for a hotel check-in system. You analyze images of identity documents (ID cards, passports, driver's licenses) and extract structured information.

CRITICAL: The image may contain ONE or MULTIPLE identity documents. You MUST detect and extract data from ALL visible documents separately.

IMPORTANT RULES:
1. Count ALL visible identity documents in the image
2. Extract ALL visible text fields from EACH document separately
3. Return ONLY valid JSON - no markdown, no extra text, no code blocks
4. If a field is not visible or unclear, set it to null
5. Normalize dates to YYYY-MM-DD format
6. For gender, use "M" (Male/Erkek) or "F" (Female/Kadin)
7. Detect the document type automatically for each document
8. If the image is blurry, cropped, or not an ID document, set "is_valid" to false
9. For Turkish ID cards (TC Kimlik), extract TC Kimlik No
10. For passports, extract passport number and MRZ data if visible
11. For driver's licenses, extract license number

ALWAYS return a JSON object with a "documents" array. Even if there is only 1 document, wrap it in the array.

Return this exact JSON structure (no markdown, no code fences):
{
    "document_count": 1 or 2 or more,
    "documents": [
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
            "raw_extracted_text": "all visible text from this specific document"
        }
    ]
}"""


def serialize_doc(doc):
    if doc is None:
        return None
    result = {}
    for key, value in doc.items():
        if key == "_id":
            result["id"] = str(value)
        elif key == "password_hash":
            continue  # Never expose password hash
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
    original_extracted_data: Optional[dict] = None
    force_create: Optional[bool] = False
    kvkk_consent: Optional[bool] = False

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

class LoginRequest(BaseModel):
    email: str
    password: str

class UserCreate(BaseModel):
    email: str
    password: str
    name: str
    role: str = "reception"  # "admin" or "reception"

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

class PasswordChange(BaseModel):
    current_password: Optional[str] = None
    new_password: str

class SettingsUpdate(BaseModel):
    retention_days_scans: Optional[int] = None
    retention_days_audit: Optional[int] = None
    store_scan_images: Optional[bool] = None
    kvkk_consent_required: Optional[bool] = None
    kvkk_consent_text: Optional[str] = None
    data_processing_purpose: Optional[str] = None
    auto_cleanup_enabled: Optional[bool] = None


async def extract_id_data(image_base64: str) -> dict:
    """Extract data from one or more ID documents in an image using OpenAI Vision"""
    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"scan-{uuid.uuid4().hex[:8]}",
        system_message=ID_EXTRACTION_PROMPT
    )
    chat.with_model("openai", "gpt-4o")
    if "," in image_base64:
        image_base64 = image_base64.split(",")[1]
    image_content = ImageContent(image_base64=image_base64)
    user_message = UserMessage(
        text="Analyze ALL identity documents visible in this image. There may be 1 or more documents. Extract data from EACH document separately and return them in the documents array. Return ONLY the JSON structure, no markdown.",
        file_contents=[image_content]
    )
    response = await chat.send_message(user_message)
    json_str = response.strip()
    if json_str.startswith("```"):
        lines = json_str.split("\n")
        json_str = "\n".join(lines[1:-1]) if len(lines) > 2 else json_str[3:-3]
        json_str = json_str.strip()
    try:
        result = json.loads(json_str)
    except json.JSONDecodeError:
        start = json_str.find("{")
        end = json_str.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(json_str[start:end])
        else:
            raise ValueError(f"Could not parse JSON from response: {json_str[:200]}")
    
    # Normalize: ensure we always have a "documents" array
    if "documents" in result and isinstance(result["documents"], list):
        return result
    else:
        # Old format (single document) - wrap in array
        return {
            "document_count": 1,
            "documents": [result]
        }


# --- Helpers ---
async def find_duplicates(id_number=None, first_name=None, last_name=None, birth_date=None, exclude_id=None):
    duplicates = []
    if id_number and id_number.strip():
        query = {"id_number": id_number.strip(), "anonymized": {"$ne": True}}
        if exclude_id:
            query["_id"] = {"$ne": ObjectId(exclude_id)}
        async for doc in guests_col.find(query):
            duplicates.append({**serialize_doc(doc), "match_type": "id_number", "match_confidence": "high"})
    if first_name and last_name and birth_date:
        query = {
            "first_name": {"$regex": f"^{first_name.strip()}$", "$options": "i"},
            "last_name": {"$regex": f"^{last_name.strip()}$", "$options": "i"},
            "birth_date": birth_date.strip(),
            "anonymized": {"$ne": True}
        }
        if exclude_id:
            query["_id"] = {"$ne": ObjectId(exclude_id)}
        existing_ids = {d["id"] for d in duplicates}
        async for doc in guests_col.find(query):
            s = serialize_doc(doc)
            if s["id"] not in existing_ids:
                duplicates.append({**s, "match_type": "name_birthdate", "match_confidence": "medium"})
    return duplicates


TRACKED_FIELDS = ["first_name", "last_name", "id_number", "birth_date", "gender", "nationality",
                   "document_type", "document_number", "birth_place", "expiry_date", "issue_date",
                   "mother_name", "father_name", "address", "notes", "status"]

async def create_audit_log(guest_id, action, changes=None, old_data=None, new_data=None, metadata=None, user_email=None):
    audit_entry = {
        "guest_id": guest_id,
        "action": action,
        "changes": changes or {},
        "old_data": old_data or {},
        "new_data": new_data or {},
        "metadata": metadata or {},
        "user_email": user_email,
        "created_at": datetime.now(timezone.utc)
    }
    await audit_col.insert_one(audit_entry)

def compute_field_diffs(old_data, new_data):
    diffs = {}
    for field in TRACKED_FIELDS:
        old_val = old_data.get(field)
        new_val = new_data.get(field)
        if old_val != new_val and new_val is not None:
            diffs[field] = {"old": old_val, "new": new_val}
    return diffs


# ===== STARTUP: Create default admin =====
@app.on_event("startup")
async def create_default_admin():
    existing = await users_col.find_one({"email": "admin@quickid.com"})
    if not existing:
        await users_col.insert_one({
            "email": "admin@quickid.com",
            "password_hash": hash_password("admin123"),
            "name": "Admin",
            "role": "admin",
            "is_active": True,
            "created_at": datetime.now(timezone.utc)
        })
    # Also create default reception user
    existing_rec = await users_col.find_one({"email": "resepsiyon@quickid.com"})
    if not existing_rec:
        await users_col.insert_one({
            "email": "resepsiyon@quickid.com",
            "password_hash": hash_password("resepsiyon123"),
            "name": "Resepsiyon",
            "role": "reception",
            "is_active": True,
            "created_at": datetime.now(timezone.utc)
        })


# ===== AUTH ROUTES =====
@app.get("/api/health")
async def health():
    return {"status": "healthy", "service": "Quick ID Reader"}

@app.get("/api/rate-limits")
async def get_rate_limits():
    """Return rate limit configuration for the frontend"""
    return {
        "limits": {
            "scan": {"limit": 15, "window": "dakika", "description": "Kimlik tarama (AI)"},
            "login": {"limit": 5, "window": "dakika", "description": "Giriş denemesi"},
            "guest_create": {"limit": 30, "window": "dakika", "description": "Misafir oluşturma"},
        },
        "note": "Limitler kullanıcı bazında uygulanır. Her kullanıcının kendi limiti vardır."
    }


@app.post("/api/auth/login")
@limiter.limit("5/minute")
async def login(request: Request, req: LoginRequest):
    user = await users_col.find_one({"email": req.email})
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Geçersiz e-posta veya şifre")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Hesap devre dışı")
    token = create_token({"sub": str(user["_id"]), "email": user["email"], "name": user["name"], "role": user["role"]})
    return {
        "token": token,
        "user": {"id": str(user["_id"]), "email": user["email"], "name": user["name"], "role": user["role"]}
    }

@app.get("/api/auth/me")
async def get_me(user=Depends(require_auth)):
    db_user = await users_col.find_one({"email": user["email"]})
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user": serialize_doc(db_user)}

@app.post("/api/auth/change-password")
async def change_password(req: PasswordChange, user=Depends(require_auth)):
    db_user = await users_col.find_one({"email": user["email"]})
    if not db_user:
        raise HTTPException(status_code=404)
    # Admin can change without current password, others need it
    if user.get("role") != "admin" and req.current_password:
        if not verify_password(req.current_password, db_user["password_hash"]):
            raise HTTPException(status_code=400, detail="Mevcut şifre yanlış")
    await users_col.update_one(
        {"email": user["email"]},
        {"$set": {"password_hash": hash_password(req.new_password), "updated_at": datetime.now(timezone.utc)}}
    )
    return {"success": True, "message": "Şifre güncellendi"}


# ===== USER MANAGEMENT (Admin Only) =====
@app.get("/api/users")
async def list_users(user=Depends(require_admin)):
    cursor = users_col.find({}).sort("created_at", -1)
    users = [serialize_doc(doc) async for doc in cursor]
    return {"users": users, "total": len(users)}

@app.post("/api/users")
async def create_user(req: UserCreate, user=Depends(require_admin)):
    existing = await users_col.find_one({"email": req.email})
    if existing:
        raise HTTPException(status_code=400, detail="Bu e-posta zaten kayıtlı")
    if req.role not in ("admin", "reception"):
        raise HTTPException(status_code=400, detail="Geçersiz rol")
    user_doc = {
        "email": req.email,
        "password_hash": hash_password(req.password),
        "name": req.name,
        "role": req.role,
        "is_active": True,
        "created_at": datetime.now(timezone.utc)
    }
    result = await users_col.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id
    return {"success": True, "user": serialize_doc(user_doc)}

@app.patch("/api/users/{user_id}")
async def update_user(user_id: str, req: UserUpdate, user=Depends(require_admin)):
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if "role" in updates and updates["role"] not in ("admin", "reception"):
        raise HTTPException(status_code=400, detail="Geçersiz rol")
    updates["updated_at"] = datetime.now(timezone.utc)
    result = await users_col.update_one({"_id": oid}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404)
    doc = await users_col.find_one({"_id": oid})
    return {"success": True, "user": serialize_doc(doc)}

@app.delete("/api/users/{user_id}")
async def delete_user(user_id: str, user=Depends(require_admin)):
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    # Don't allow deleting yourself
    if user_id == user.get("sub"):
        raise HTTPException(status_code=400, detail="Kendi hesabınızı silemezsiniz")
    result = await users_col.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404)
    return {"success": True}

@app.post("/api/users/{user_id}/reset-password")
async def reset_user_password(user_id: str, req: PasswordChange, user=Depends(require_admin)):
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400)
    await users_col.update_one({"_id": oid}, {"$set": {"password_hash": hash_password(req.new_password)}})
    return {"success": True, "message": "Şifre sıfırlandı"}


# ===== KVKK / SETTINGS =====
@app.get("/api/settings/kvkk")
async def get_kvkk_settings(user=Depends(require_auth)):
    settings = await get_settings(db)
    return {"settings": settings}

@app.patch("/api/settings/kvkk")
async def update_kvkk_settings(req: SettingsUpdate, user=Depends(require_admin)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    settings = await update_settings(db, updates)
    return {"success": True, "settings": settings}

@app.post("/api/settings/cleanup")
async def trigger_cleanup(user=Depends(require_admin)):
    results = await run_data_cleanup(db)
    return {"success": True, "results": results}

@app.post("/api/guests/{guest_id}/anonymize")
async def anonymize_guest_endpoint(guest_id: str, user=Depends(require_admin)):
    success = await anonymize_guest(db, guest_id)
    if not success:
        raise HTTPException(status_code=404, detail="Misafir bulunamadı")
    await create_audit_log(guest_id, "anonymized", metadata={"kvkk": True}, user_email=user.get("email"))
    return {"success": True, "message": "Misafir verileri KVKK kapsamında anonimleştirildi"}


# ===== SCAN ENDPOINTS =====
@app.post("/api/scan")
@limiter.limit("15/minute")
async def scan_id(request: Request, scan_req: ScanRequest, user=Depends(require_auth)):
    try:
        extracted = await extract_id_data(scan_req.image_base64)
        scan_doc = {
            "extracted_data": extracted,
            "is_valid": extracted.get("is_valid", False),
            "document_type": extracted.get("document_type", "other"),
            "created_at": datetime.now(timezone.utc),
            "status": "completed",
            "warnings": extracted.get("warnings", []),
            "scanned_by": user.get("email")
        }
        result = await scans_col.insert_one(scan_doc)
        scan_doc["_id"] = result.inserted_id
        return {"success": True, "scan": serialize_doc(scan_doc), "extracted_data": extracted}
    except Exception as e:
        scan_doc = {"status": "failed", "error": str(e), "created_at": datetime.now(timezone.utc), "scanned_by": user.get("email")}
        await scans_col.insert_one(scan_doc)
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")

@app.get("/api/scans")
async def get_scans(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), user=Depends(require_auth)):
    skip = (page - 1) * limit
    total = await scans_col.count_documents({})
    cursor = scans_col.find({}).sort("created_at", -1).skip(skip).limit(limit)
    scans = [serialize_doc(doc) async for doc in cursor]
    return {"scans": scans, "total": total, "page": page, "limit": limit}


# ===== GUEST ENDPOINTS =====
@app.get("/api/guests/check-duplicate")
async def check_duplicate(
    id_number: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    birth_date: Optional[str] = None,
    user=Depends(require_auth)
):
    duplicates = await find_duplicates(id_number, first_name, last_name, birth_date)
    return {"has_duplicates": len(duplicates) > 0, "duplicates": duplicates, "count": len(duplicates)}

@app.post("/api/guests")
@limiter.limit("30/minute")
async def create_guest(request: Request, guest: GuestCreate, user=Depends(require_auth)):
    if not guest.force_create:
        duplicates = await find_duplicates(guest.id_number, guest.first_name, guest.last_name, guest.birth_date)
        if duplicates:
            return {"success": False, "duplicate_detected": True, "duplicates": duplicates, "message": "Mükerrer misafir tespit edildi."}
    
    guest_data = guest.model_dump(exclude_none=True)
    original_extracted = guest_data.pop("original_extracted_data", None)
    guest_data.pop("force_create", None)
    scan_id = guest_data.pop("scan_id", None)
    kvkk_consent = guest_data.pop("kvkk_consent", False)
    
    guest_doc = {
        **guest_data,
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "check_in_at": None,
        "check_out_at": None,
        "scan_ids": [scan_id] if scan_id else [],
        "original_extracted_data": original_extracted,
        "kvkk_consent": kvkk_consent,
        "kvkk_consent_at": datetime.now(timezone.utc) if kvkk_consent else None,
        "created_by": user.get("email"),
    }
    
    result = await guests_col.insert_one(guest_doc)
    guest_doc["_id"] = result.inserted_id
    guest_id = str(result.inserted_id)
    
    audit_changes = compute_field_diffs(original_extracted or {}, guest_data) if original_extracted else {}
    await create_audit_log(guest_id, "created", audit_changes, original_extracted or {}, guest_data,
                           {"scan_id": scan_id, "had_manual_edits": bool(audit_changes), "kvkk_consent": kvkk_consent},
                           user.get("email"))
    
    return {"success": True, "guest": serialize_doc(guest_doc)}

@app.get("/api/guests")
async def get_guests(
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None, status: Optional[str] = None,
    nationality: Optional[str] = None, document_type: Optional[str] = None,
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    user=Depends(require_auth)
):
    query = {}
    if search:
        query["$or"] = [
            {"first_name": {"$regex": search, "$options": "i"}},
            {"last_name": {"$regex": search, "$options": "i"}},
            {"id_number": {"$regex": search, "$options": "i"}},
            {"document_number": {"$regex": search, "$options": "i"}}
        ]
    if status: query["status"] = status
    if nationality: query["nationality"] = {"$regex": nationality, "$options": "i"}
    if document_type: query["document_type"] = document_type
    if date_from:
        try: query.setdefault("created_at", {})["$gte"] = datetime.fromisoformat(date_from)
        except ValueError: pass
    if date_to:
        try: query.setdefault("created_at", {})["$lte"] = datetime.fromisoformat(date_to)
        except ValueError: pass
    
    skip = (page - 1) * limit
    total = await guests_col.count_documents(query)
    cursor = guests_col.find(query).sort("created_at", -1).skip(skip).limit(limit)
    guests = [serialize_doc(doc) async for doc in cursor]
    return {"guests": guests, "total": total, "page": page, "limit": limit}

@app.get("/api/guests/{guest_id}")
async def get_guest(guest_id: str, user=Depends(require_auth)):
    try: doc = await guests_col.find_one({"_id": ObjectId(guest_id)})
    except Exception: raise HTTPException(status_code=400, detail="Invalid guest ID")
    if not doc: raise HTTPException(status_code=404, detail="Guest not found")
    return {"guest": serialize_doc(doc)}

@app.patch("/api/guests/{guest_id}")
async def update_guest(guest_id: str, update: GuestUpdate, user=Depends(require_auth)):
    try: oid = ObjectId(guest_id)
    except Exception: raise HTTPException(status_code=400)
    old_doc = await guests_col.find_one({"_id": oid})
    if not old_doc: raise HTTPException(status_code=404)
    old_data = serialize_doc(old_doc)
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc)
    await guests_col.update_one({"_id": oid}, {"$set": update_data})
    doc = await guests_col.find_one({"_id": oid})
    diffs = compute_field_diffs(old_data, update_data)
    if diffs:
        await create_audit_log(guest_id, "updated", diffs, {k: old_data.get(k) for k in diffs}, {k: update_data.get(k) for k in diffs}, user_email=user.get("email"))
    return {"success": True, "guest": serialize_doc(doc)}

@app.delete("/api/guests/{guest_id}")
async def delete_guest(guest_id: str, user=Depends(require_auth)):
    try: oid = ObjectId(guest_id)
    except Exception: raise HTTPException(status_code=400)
    doc = await guests_col.find_one({"_id": oid})
    if not doc: raise HTTPException(status_code=404)
    await create_audit_log(guest_id, "deleted", old_data=serialize_doc(doc), user_email=user.get("email"))
    await guests_col.delete_one({"_id": oid})
    return {"success": True}

@app.post("/api/guests/{guest_id}/checkin")
async def checkin_guest(guest_id: str, user=Depends(require_auth)):
    try: oid = ObjectId(guest_id)
    except Exception: raise HTTPException(status_code=400)
    old_doc = await guests_col.find_one({"_id": oid})
    if not old_doc: raise HTTPException(status_code=404)
    now = datetime.now(timezone.utc)
    await guests_col.update_one({"_id": oid}, {"$set": {"status": "checked_in", "check_in_at": now, "updated_at": now}})
    await create_audit_log(guest_id, "checked_in", {"status": {"old": old_doc.get("status"), "new": "checked_in"}}, metadata={"check_in_at": now.isoformat()}, user_email=user.get("email"))
    doc = await guests_col.find_one({"_id": oid})
    return {"success": True, "guest": serialize_doc(doc)}

@app.post("/api/guests/{guest_id}/checkout")
async def checkout_guest(guest_id: str, user=Depends(require_auth)):
    try: oid = ObjectId(guest_id)
    except Exception: raise HTTPException(status_code=400)
    old_doc = await guests_col.find_one({"_id": oid})
    if not old_doc: raise HTTPException(status_code=404)
    now = datetime.now(timezone.utc)
    await guests_col.update_one({"_id": oid}, {"$set": {"status": "checked_out", "check_out_at": now, "updated_at": now}})
    await create_audit_log(guest_id, "checked_out", {"status": {"old": old_doc.get("status"), "new": "checked_out"}}, metadata={"check_out_at": now.isoformat()}, user_email=user.get("email"))
    doc = await guests_col.find_one({"_id": oid})
    return {"success": True, "guest": serialize_doc(doc)}


# ===== AUDIT =====
@app.get("/api/guests/{guest_id}/audit")
async def get_guest_audit(guest_id: str, user=Depends(require_auth)):
    cursor = audit_col.find({"guest_id": guest_id}).sort("created_at", -1)
    logs = [serialize_doc(doc) async for doc in cursor]
    return {"audit_logs": logs, "total": len(logs)}

@app.get("/api/audit/recent")
async def get_recent_audit(limit: int = Query(50, ge=1, le=200), user=Depends(require_auth)):
    cursor = audit_col.find({}).sort("created_at", -1).limit(limit)
    logs = [serialize_doc(doc) async for doc in cursor]
    return {"audit_logs": logs, "total": len(logs)}


# ===== DASHBOARD =====
@app.get("/api/dashboard/stats")
async def get_dashboard_stats(user=Depends(require_auth)):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    total_guests = await guests_col.count_documents({})
    today_checkins = await guests_col.count_documents({"status": "checked_in", "check_in_at": {"$gte": today_start}})
    today_checkouts = await guests_col.count_documents({"status": "checked_out", "check_out_at": {"$gte": today_start}})
    pending_reviews = await guests_col.count_documents({"status": "pending"})
    currently_checked_in = await guests_col.count_documents({"status": "checked_in"})
    total_scans = await scans_col.count_documents({})
    today_scans = await scans_col.count_documents({"created_at": {"$gte": today_start}})
    recent_cursor = scans_col.find({}).sort("created_at", -1).limit(5)
    recent_scans = [serialize_doc(doc) async for doc in recent_cursor]
    recent_guests_cursor = guests_col.find({}).sort("created_at", -1).limit(5)
    recent_guests = [serialize_doc(doc) async for doc in recent_guests_cursor]
    weekly_stats = []
    for i in range(6, -1, -1):
        day_start = (datetime.now(timezone.utc) - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        count = await guests_col.count_documents({"created_at": {"$gte": day_start, "$lt": day_end}})
        weekly_stats.append({"date": day_start.strftime("%Y-%m-%d"), "day": day_start.strftime("%a"), "count": count})
    return {
        "total_guests": total_guests, "today_checkins": today_checkins, "today_checkouts": today_checkouts,
        "pending_reviews": pending_reviews, "currently_checked_in": currently_checked_in,
        "total_scans": total_scans, "today_scans": today_scans,
        "recent_scans": recent_scans, "recent_guests": recent_guests, "weekly_stats": weekly_stats
    }


# ===== EXPORT =====
@app.get("/api/exports/guests.json")
async def export_guests_json(status: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None, user=Depends(require_auth)):
    query = {}
    if status: query["status"] = status
    if date_from:
        try: query.setdefault("created_at", {})["$gte"] = datetime.fromisoformat(date_from)
        except ValueError: pass
    if date_to:
        try: query.setdefault("created_at", {})["$lte"] = datetime.fromisoformat(date_to)
        except ValueError: pass
    cursor = guests_col.find(query).sort("created_at", -1)
    guests = [serialize_doc(doc) async for doc in cursor]
    return {"guests": guests, "total": len(guests), "exported_at": datetime.now(timezone.utc).isoformat()}

@app.get("/api/exports/guests.csv")
async def export_guests_csv(status: Optional[str] = None, user=Depends(require_auth)):
    from fastapi.responses import StreamingResponse
    import io, csv
    query = {}
    if status: query["status"] = status
    cursor = guests_col.find(query).sort("created_at", -1)
    guests = [serialize_doc(doc) async for doc in cursor]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Ad", "Soyad", "Kimlik No", "Dogum Tarihi", "Cinsiyet", "Uyruk", "Belge Turu", "Durum", "Check-in", "Check-out", "Olusturma"])
    for g in guests:
        writer.writerow([g.get("first_name",""), g.get("last_name",""), g.get("id_number",""), g.get("birth_date",""),
                         g.get("gender",""), g.get("nationality",""), g.get("document_type",""), g.get("status",""),
                         g.get("check_in_at",""), g.get("check_out_at",""), g.get("created_at","")])
    output.seek(0)
    return StreamingResponse(io.BytesIO(output.getvalue().encode("utf-8-sig")), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=misafirler.csv"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
