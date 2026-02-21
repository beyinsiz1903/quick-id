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
from kvkk_compliance import (
    create_rights_request, list_rights_requests, process_rights_request,
    get_guest_data_for_access, export_guest_data_portable,
    generate_verbis_report, get_data_inventory, get_retention_warnings,
    calculate_confidence_score, VALID_REQUEST_TYPES, VALID_REQUEST_STATUSES
)
from tc_kimlik import validate_tc_kimlik, generate_emniyet_bildirimi, is_foreign_guest
from biometric import compare_faces, check_liveness, get_liveness_challenge
from multi_property import (
    create_property, list_properties, get_property, update_property,
    create_kiosk_session, update_kiosk_activity, get_kiosk_sessions,
    store_offline_data, get_pending_syncs, process_sync,
    create_precheckin_token, get_precheckin_token, use_precheckin_token, list_precheckin_tokens,
)
import qrcode
import io


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

app = FastAPI(
    title="Quick ID Reader API",
    description="""
## Otel Kimlik Okuyucu Sistemi API

Quick ID Reader, otel resepsiyon operasyonları için geliştirilmiş kimlik tarama ve misafir yönetim sistemidir.

### Özellikler:
- **AI Kimlik Tarama**: GPT-4o Vision ile kimlik belgelerinden otomatik bilgi çıkarımı
- **Misafir Yönetimi**: CRUD, check-in/check-out, toplu tarama
- **KVKK Uyumluluğu**: Tam 6698 sayılı kanun uyumluluğu
- **Güvenlik**: JWT auth, RBAC, rate limiting, denetim izi

### Kimlik Doğrulama:
Tüm korumalı endpoint'ler Bearer token gerektirir:
```
Authorization: Bearer <jwt_token>
```

### Varsayılan Hesaplar:
- **Admin**: admin@quickid.com / admin123
- **Resepsiyon**: resepsiyon@quickid.com / resepsiyon123
    """,
    version="3.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    openapi_tags=[
        {"name": "Sağlık", "description": "Sistem sağlık kontrolleri"},
        {"name": "Kimlik Doğrulama", "description": "Giriş, token yönetimi"},
        {"name": "Kullanıcı Yönetimi", "description": "Admin kullanıcı CRUD işlemleri"},
        {"name": "Tarama", "description": "AI kimlik tarama ve inceleme kuyruğu"},
        {"name": "Misafirler", "description": "Misafir CRUD, check-in/check-out"},
        {"name": "Biyometrik", "description": "Yüz eşleştirme ve canlılık testi"},
        {"name": "TC Kimlik", "description": "TC Kimlik No doğrulama ve Emniyet bildirimi"},
        {"name": "Ön Check-in", "description": "QR kod ile misafir ön check-in"},
        {"name": "Multi-Property", "description": "Çoklu tesis/otel yönetimi"},
        {"name": "Kiosk", "description": "Self-servis kiosk modu"},
        {"name": "Offline Sync", "description": "Çevrimdışı senkronizasyon"},
        {"name": "Denetim İzi", "description": "Audit trail ve değişiklik geçmişi"},
        {"name": "Dashboard", "description": "İstatistikler ve genel bakış"},
        {"name": "Dışa Aktarım", "description": "CSV/JSON veri dışa aktarımı"},
        {"name": "KVKK Ayarları", "description": "KVKK/GDPR yapılandırma"},
        {"name": "KVKK Uyumluluk", "description": "Hak talepleri, VERBİS, veri envanteri"},
        {"name": "API Rehberi", "description": "Entegrasyon rehberi ve dokümantasyon"},
    ]
)
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

class RightsRequestCreate(BaseModel):
    request_type: str  # access, rectification, erasure, portability, objection
    guest_id: Optional[str] = None
    requester_name: str
    requester_email: str
    requester_id_number: Optional[str] = None
    description: str

class RightsRequestProcess(BaseModel):
    status: str  # in_progress, completed, rejected
    response_note: str
    response_data: Optional[dict] = None

class FaceCompareRequest(BaseModel):
    document_image_base64: str
    selfie_image_base64: str

class LivenessCheckRequest(BaseModel):
    image_base64: str
    challenge_id: str
    session_id: str

class TcKimlikValidateRequest(BaseModel):
    tc_no: str

class EmniyetBildirimiRequest(BaseModel):
    guest_id: str

class PropertyCreate(BaseModel):
    name: str
    address: Optional[str] = ""
    phone: Optional[str] = ""
    tax_no: Optional[str] = ""
    city: Optional[str] = ""

class PropertyUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    tax_no: Optional[str] = None
    city: Optional[str] = None
    is_active: Optional[bool] = None
    settings: Optional[dict] = None

class KioskSessionCreate(BaseModel):
    property_id: str
    kiosk_name: Optional[str] = "Lobby Kiosk"

class PreCheckinCreate(BaseModel):
    property_id: str
    reservation_ref: Optional[str] = ""
    guest_name: Optional[str] = ""

class PreCheckinScanRequest(BaseModel):
    image_base64: str
    kvkk_consent: Optional[bool] = False

class OfflineSyncRequest(BaseModel):
    property_id: str
    data_type: str  # scans, guests
    data: list
    device_id: Optional[str] = None


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
@app.get("/api/health", tags=["Sağlık"], summary="Sistem sağlık kontrolü")
async def health():
    return {"status": "healthy", "service": "Quick ID Reader", "version": "3.0.0"}

@app.get("/api/rate-limits", tags=["Sağlık"], summary="Rate limit bilgileri")
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
@app.post("/api/scan", tags=["Tarama"], summary="Kimlik belgesi tara",
          description="AI (GPT-4o Vision) ile kimlik belgesini tarayıp bilgi çıkarır. Confidence score ile güvenilirlik puanı hesaplar.")
@limiter.limit("15/minute")
async def scan_id(request: Request, scan_req: ScanRequest, user=Depends(require_auth)):
    try:
        extracted = await extract_id_data(scan_req.image_base64)
        documents = extracted.get("documents", [])
        document_count = extracted.get("document_count", len(documents))

        # Calculate confidence score
        confidence = calculate_confidence_score(extracted)

        scan_doc = {
            "extracted_data": extracted,
            "document_count": document_count,
            "is_valid": any(d.get("is_valid", False) for d in documents),
            "document_type": documents[0].get("document_type", "other") if documents else "other",
            "created_at": datetime.now(timezone.utc),
            "status": "completed",
            "warnings": [],
            "scanned_by": user.get("email"),
            "confidence_score": confidence.get("overall_score", 0),
            "confidence_level": confidence.get("confidence_level", "low"),
            "review_status": "needs_review" if confidence.get("review_needed") else "auto_approved",
        }
        for doc in documents:
            scan_doc["warnings"].extend(doc.get("warnings", []))

        result = await scans_col.insert_one(scan_doc)
        scan_doc["_id"] = result.inserted_id

        return {
            "success": True,
            "scan": serialize_doc(scan_doc),
            "extracted_data": extracted,
            "document_count": document_count,
            "documents": documents,
            "confidence": confidence,
        }
    except Exception as e:
        error_str = str(e)
        # Fallback: AI başarısız olursa kullanıcıya rehberlik
        fallback_guidance = []
        if "timeout" in error_str.lower() or "connection" in error_str.lower():
            fallback_guidance = [
                "Bağlantı hatası oluştu. Lütfen tekrar deneyin.",
                "İnternet bağlantınızı kontrol edin.",
            ]
        elif "rate" in error_str.lower() or "limit" in error_str.lower():
            fallback_guidance = [
                "İstek limiti aşıldı. Lütfen biraz bekleyin.",
            ]
        else:
            fallback_guidance = [
                "Kimlik belgesi okunamadı. Lütfen şunları deneyin:",
                "1. Belgeyi düz bir yüzeye yerleştirin",
                "2. Flaş kullanarak fotoğraf çekin",
                "3. Belgenin tamamının görünür olduğundan emin olun",
                "4. Parlama ve gölge olmadığından emin olun",
                "5. Daha iyi aydınlatma altında tekrar deneyin",
                "6. Belge yıpranmışsa elle giriş yapabilirsiniz",
            ]
        scan_doc = {
            "status": "failed", 
            "error": error_str, 
            "created_at": datetime.now(timezone.utc), 
            "scanned_by": user.get("email"),
            "fallback_guidance": fallback_guidance,
        }
        await scans_col.insert_one(scan_doc)
        raise HTTPException(status_code=500, detail={
            "message": f"Tarama başarısız: {error_str}",
            "fallback_guidance": fallback_guidance,
            "can_retry": True,
        })

@app.get("/api/scans", tags=["Tarama"], summary="Tarama geçmişi")
async def get_scans(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), user=Depends(require_auth)):
    skip = (page - 1) * limit
    total = await scans_col.count_documents({})
    cursor = scans_col.find({}).sort("created_at", -1).skip(skip).limit(limit)
    scans = [serialize_doc(doc) async for doc in cursor]
    return {"scans": scans, "total": total, "page": page, "limit": limit}

@app.get("/api/scans/review-queue", tags=["Tarama"], summary="İnceleme kuyruğu",
         description="Düşük güvenilirlik puanlı taramaları listeler")
async def get_review_queue(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    review_status: Optional[str] = Query(None, description="needs_review, auto_approved, reviewed"),
    user=Depends(require_auth)
):
    query = {}
    if review_status:
        query["review_status"] = review_status
    else:
        query["review_status"] = "needs_review"

    skip = (page - 1) * limit
    total = await scans_col.count_documents(query)
    cursor = scans_col.find(query).sort("created_at", -1).skip(skip).limit(limit)
    scans = [serialize_doc(doc) async for doc in cursor]
    return {"scans": scans, "total": total, "page": page, "limit": limit}

@app.patch("/api/scans/{scan_id}/review", tags=["Tarama"], summary="Tarama inceleme durumu güncelle")
async def update_scan_review(scan_id: str, review_status: str = Query(..., description="reviewed, needs_review"), user=Depends(require_auth)):
    try:
        oid = ObjectId(scan_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz tarama ID")
    if review_status not in ("reviewed", "needs_review", "auto_approved"):
        raise HTTPException(status_code=400, detail="Geçersiz inceleme durumu")
    result = await scans_col.update_one(
        {"_id": oid},
        {"$set": {"review_status": review_status, "reviewed_at": datetime.now(timezone.utc), "reviewed_by": user.get("email")}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404)
    doc = await scans_col.find_one({"_id": oid})
    return {"success": True, "scan": serialize_doc(doc)}


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


# ===== KVKK COMPLIANCE (Tam Uyumluluk) =====

@app.post("/api/kvkk/rights-request", tags=["KVKK Uyumluluk"], summary="KVKK hak talebi oluştur",
          description="Misafir veya ilgili kişi adına KVKK hak talebi oluşturur (erişim, düzeltme, silme, taşıma, itiraz)")
async def create_kvkk_request(req: RightsRequestCreate, user=Depends(require_auth)):
    try:
        result = await create_rights_request(
            db,
            request_type=req.request_type,
            guest_id=req.guest_id,
            requester_name=req.requester_name,
            requester_email=req.requester_email,
            requester_id_number=req.requester_id_number,
            description=req.description,
            created_by=user.get("email")
        )
        return {"success": True, "request": serialize_doc(result)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/kvkk/rights-requests", tags=["KVKK Uyumluluk"], summary="KVKK hak taleplerini listele")
async def get_kvkk_requests(
    status: Optional[str] = None,
    request_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user=Depends(require_admin)
):
    result = await list_rights_requests(db, status=status, request_type=request_type, page=page, limit=limit)
    return result

@app.patch("/api/kvkk/rights-requests/{request_id}", tags=["KVKK Uyumluluk"], summary="KVKK hak talebini işle")
async def process_kvkk_request(request_id: str, req: RightsRequestProcess, user=Depends(require_admin)):
    try:
        result = await process_rights_request(
            db,
            request_id=request_id,
            new_status=req.status,
            response_note=req.response_note,
            response_data=req.response_data,
            processed_by=user.get("email")
        )
        if not result:
            raise HTTPException(status_code=404, detail="Talep bulunamadı")
        return {"success": True, "request": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/kvkk/guest-data/{guest_id}", tags=["KVKK Uyumluluk"], summary="Misafir veri erişim raporu",
         description="KVKK erişim hakkı kapsamında misafirin tüm kişisel verilerini derler")
async def get_guest_kvkk_data(guest_id: str, user=Depends(require_admin)):
    data = await get_guest_data_for_access(db, guest_id)
    if not data:
        raise HTTPException(status_code=404, detail="Misafir bulunamadı")
    return data

@app.get("/api/kvkk/guest-data/{guest_id}/portable", tags=["KVKK Uyumluluk"], summary="Veri taşınabilirlik dışa aktarımı",
         description="KVKK veri taşıma hakkı kapsamında misafir verilerini taşınabilir formatta dışa aktarır")
async def export_guest_portable(guest_id: str, user=Depends(require_admin)):
    data = await export_guest_data_portable(db, guest_id)
    if not data:
        raise HTTPException(status_code=404, detail="Misafir bulunamadı")
    return data

@app.get("/api/kvkk/verbis-report", tags=["KVKK Uyumluluk"], summary="VERBİS uyumluluk raporu",
         description="KVKK Madde 16 kapsamında VERBİS uyumluluk raporu üretir")
async def get_verbis_report(user=Depends(require_admin)):
    report = await generate_verbis_report(db)
    return report

@app.get("/api/kvkk/data-inventory", tags=["KVKK Uyumluluk"], summary="Veri işleme envanteri",
         description="Sistemdeki tüm veri koleksiyonları ve işleme detaylarının envanterini sunar")
async def get_kvkk_data_inventory(user=Depends(require_admin)):
    inventory = await get_data_inventory(db)
    return inventory

@app.get("/api/kvkk/retention-warnings", tags=["KVKK Uyumluluk"], summary="Saklama süresi uyarıları",
         description="Saklama süresine yaklaşan veya aşan veriler için uyarılar üretir")
async def get_kvkk_retention_warnings(user=Depends(require_admin)):
    warnings = await get_retention_warnings(db)
    return warnings


# ===== API GUIDE =====
@app.get("/api/guide", tags=["API Rehberi"], summary="API Entegrasyon Rehberi",
         description="PMS entegrasyonu ve dış sistemler için kapsamlı API rehberi")
async def get_api_guide():
    return {
        "title": "Quick ID Reader - API Entegrasyon Rehberi",
        "version": "3.0.0",
        "base_url": "Deployment'a göre değişir",
        "authentication": {
            "type": "Bearer Token (JWT)",
            "login_endpoint": "POST /api/auth/login",
            "request_body": {"email": "string", "password": "string"},
            "response": {"token": "jwt_token_string", "user": {"id": "...", "email": "...", "role": "admin|reception"}},
            "header_format": "Authorization: Bearer <token>",
            "token_expiry": "24 saat (varsayılan)"
        },
        "endpoints": {
            "kimlik_tarama": {
                "scan": {
                    "method": "POST",
                    "path": "/api/scan",
                    "description": "AI ile kimlik belgesi tarama (GPT-4o Vision)",
                    "request": {"image_base64": "base64_encoded_image_string"},
                    "response_fields": ["success", "scan", "extracted_data", "documents", "confidence"],
                    "rate_limit": "15/dakika",
                    "fallback": "AI başarısız olursa kullanıcıya yeniden çekim rehberliği"
                },
                "scans_list": {"method": "GET", "path": "/api/scans", "params": {"page": "int", "limit": "int"}},
                "review_queue": {"method": "GET", "path": "/api/scans/review-queue", "description": "Düşük güvenilirlik puanlı taramalar"},
            },
            "misafir_yonetimi": {
                "list": {"method": "GET", "path": "/api/guests", "params": ["page", "limit", "search", "status", "nationality", "document_type", "date_from", "date_to"]},
                "create": {"method": "POST", "path": "/api/guests", "body_fields": ["first_name", "last_name", "id_number", "birth_date", "gender", "nationality", "document_type", "kvkk_consent"]},
                "get": {"method": "GET", "path": "/api/guests/{id}"},
                "update": {"method": "PATCH", "path": "/api/guests/{id}"},
                "delete": {"method": "DELETE", "path": "/api/guests/{id}"},
                "checkin": {"method": "POST", "path": "/api/guests/{id}/checkin"},
                "checkout": {"method": "POST", "path": "/api/guests/{id}/checkout"},
                "duplicate_check": {"method": "GET", "path": "/api/guests/check-duplicate"},
            },
            "biyometrik": {
                "face_compare": {"method": "POST", "path": "/api/biometric/face-compare", "description": "Belge fotoğrafı vs canlı yüz karşılaştırma"},
                "liveness_challenge": {"method": "GET", "path": "/api/biometric/liveness-challenge", "description": "Canlılık testi sorusu al"},
                "liveness_check": {"method": "POST", "path": "/api/biometric/liveness-check", "description": "Canlılık testi doğrulama"},
            },
            "tc_kimlik": {
                "validate": {"method": "POST", "path": "/api/tc-kimlik/validate", "description": "TC Kimlik No doğrulama"},
                "emniyet_bildirimi": {"method": "POST", "path": "/api/tc-kimlik/emniyet-bildirimi", "description": "Yabancı misafir Emniyet bildirimi"},
            },
            "on_checkin": {
                "create_token": {"method": "POST", "path": "/api/precheckin/create", "description": "QR ön check-in token oluştur"},
                "get_token_info": {"method": "GET", "path": "/api/precheckin/{token_id}", "description": "Token bilgisi (public)"},
                "scan_with_token": {"method": "POST", "path": "/api/precheckin/{token_id}/scan", "description": "QR ile kimlik tara (public)"},
                "qr_code": {"method": "GET", "path": "/api/precheckin/{token_id}/qr", "description": "QR kod görüntüsü"},
                "list_tokens": {"method": "GET", "path": "/api/precheckin/list", "description": "Token listesi"},
            },
            "multi_property": {
                "list": {"method": "GET", "path": "/api/properties"},
                "create": {"method": "POST", "path": "/api/properties"},
                "get": {"method": "GET", "path": "/api/properties/{property_id}"},
                "update": {"method": "PATCH", "path": "/api/properties/{property_id}"},
            },
            "kiosk": {
                "create_session": {"method": "POST", "path": "/api/kiosk/session"},
                "list_sessions": {"method": "GET", "path": "/api/kiosk/sessions"},
            },
            "offline_sync": {
                "upload": {"method": "POST", "path": "/api/sync/upload"},
                "pending": {"method": "GET", "path": "/api/sync/pending"},
                "process": {"method": "POST", "path": "/api/sync/{sync_id}/process"},
            },
            "kvkk_uyumluluk": {
                "consent_info": {"method": "GET", "path": "/api/kvkk/consent-info", "description": "KVKK bilgilendirme metni (public)"},
                "settings": {"method": "GET/PATCH", "path": "/api/settings/kvkk"},
                "rights_request": {"method": "POST", "path": "/api/kvkk/rights-request"},
                "rights_list": {"method": "GET", "path": "/api/kvkk/rights-requests"},
                "verbis_report": {"method": "GET", "path": "/api/kvkk/verbis-report"},
                "data_inventory": {"method": "GET", "path": "/api/kvkk/data-inventory"},
                "retention_warnings": {"method": "GET", "path": "/api/kvkk/retention-warnings"},
            },
            "denetim": {
                "guest_audit": {"method": "GET", "path": "/api/guests/{id}/audit"},
                "recent_audit": {"method": "GET", "path": "/api/audit/recent"},
            },
            "dashboard": {"stats": {"method": "GET", "path": "/api/dashboard/stats"}},
            "disa_aktarim": {
                "json": {"method": "GET", "path": "/api/exports/guests.json"},
                "csv": {"method": "GET", "path": "/api/exports/guests.csv"},
            },
        },
        "pms_integration_guide": {
            "title": "PMS Entegrasyon Rehberi",
            "steps": [
                "1. POST /api/auth/login ile token alın",
                "2. POST /api/scan ile kimlik tarayın (base64 görüntü gönderin)",
                "3. POST /api/tc-kimlik/validate ile TC Kimlik doğrulayın (Türkiye vatandaşları)",
                "4. POST /api/biometric/face-compare ile yüz doğrulama yapın (opsiyonel)",
                "5. Dönen extracted_data ile POST /api/guests ile misafir oluşturun",
                "6. POST /api/guests/{id}/checkin ile check-in yapın",
                "7. Yabancı misafirler için POST /api/tc-kimlik/emniyet-bildirimi ile bildirim oluşturun",
                "8. POST /api/guests/{id}/checkout ile check-out yapın",
            ],
            "webhook_support": "Henüz desteklenmiyor - gelecek sürümde planlanıyor",
            "batch_operations": "Toplu tarama için /api/scan endpoint'ini ardışık çağırın",
        },
        "error_codes": {
            "400": "Geçersiz istek (eksik/hatalı parametre)",
            "401": "Kimlik doğrulama gerekli (token eksik/geçersiz)",
            "403": "Yetki yetersiz (admin yetkisi gerekli)",
            "404": "Kaynak bulunamadı",
            "429": "İstek limiti aşıldı (retry-after header'ına bakın)",
            "500": "Sunucu hatası (AI tarama hatası durumunda fallback_guidance alanını kontrol edin)",
        }
    }


# ===== KVKK PUBLIC CONSENT INFO =====
@app.get("/api/kvkk/consent-info", tags=["KVKK Uyumluluk"], summary="KVKK bilgilendirme metni (public)",
         description="Misafirlerin görmesi gereken KVKK aydınlatma metni. Kimlik doğrulama gerektirmez.")
async def get_kvkk_consent_info():
    """KVKK bilgilendirme ve açık rıza metni - herkes erişebilir"""
    settings = await get_settings(db)
    return {
        "consent_required": settings.get("kvkk_consent_required", True),
        "consent_text": settings.get("kvkk_consent_text", """
KVKK AYDINLATMA METNİ

6698 Sayılı Kişisel Verilerin Korunması Kanunu kapsamında, otelimizde konaklama hizmeti alırken aşağıdaki kişisel verileriniz işlenmektedir:

İŞLENEN VERİLER:
• Kimlik Bilgileri: Ad, soyad, TC kimlik no/pasaport no, doğum tarihi, cinsiyet, uyruk
• Belge Bilgileri: Kimlik belgesi türü, belge numarası, geçerlilik tarihi
• Konaklama Bilgileri: Giriş-çıkış tarihleri
• Biyometrik Veri: Kimlik belgesi görüntüsü (sadece tarama amacıyla, saklanmaz*)

İŞLEME AMACI:
1. Konaklama hizmeti sunumu (Yasal zorunluluk - 1774 sayılı Kimlik Bildirme Kanunu)
2. Emniyet Müdürlüğü bildirimi (Yasal zorunluluk - 5682 sayılı Pasaport Kanunu)
3. Kimlik doğrulama (AI destekli belge okuma)

HUKUKİ DAYANAK:
• KVKK Madde 5/2-ç: Veri sorumlusunun hukuki yükümlülüğü
• KVKK Madde 5/2-c: Sözleşmenin ifası

VERİ AKTARIMI:
• Emniyet Müdürlüğü (yasal zorunluluk)
• OpenAI API (kimlik tarama işleme, veri saklanmaz)

SAKLAMA SÜRESİ:
• Kişisel veriler: Konaklama süresi + yasal saklama süresi
• Kimlik görüntüleri: Tarama sonrası saklanmaz*

HAKLARINIZ (KVKK Madde 11):
1. Kişisel verilerinizin işlenip işlenmediğini öğrenme
2. Kişisel verileriniz işlenmişse bilgi talep etme
3. İşlenme amacını öğrenme
4. Yurt içinde/dışında aktarıldığı kişileri bilme
5. Eksik/yanlış işlenmişse düzeltme talep etme
6. Silinme/yok edilme talep etme
7. Düzeltme/silinme işlemlerinin aktarıldığı kişilere bildirilmesini talep etme
8. İtiraz etme
9. Zarar halinde tazminat talep etme

Haklarınızı kullanmak için resepsiyon yetkilisine başvurabilirsiniz.
        """),
        "data_processing_purpose": settings.get("data_processing_purpose", "Konaklama hizmeti kapsamında yasal zorunluluk"),
        "data_controller": {
            "title": "Veri Sorumlusu",
            "note": "Otel İşletmesi"
        },
        "rights": [
            {"code": "access", "title": "Erişim Hakkı", "description": "Kişisel verilerinize erişim talep edebilirsiniz"},
            {"code": "rectification", "title": "Düzeltme Hakkı", "description": "Yanlış/eksik verilerin düzeltilmesini talep edebilirsiniz"},
            {"code": "erasure", "title": "Silme Hakkı", "description": "Verilerinizin silinmesini talep edebilirsiniz"},
            {"code": "portability", "title": "Taşıma Hakkı", "description": "Verilerinizi taşınabilir formatta alabilirsiniz"},
            {"code": "objection", "title": "İtiraz Hakkı", "description": "Veri işlemeye itiraz edebilirsiniz"},
        ],
    }


# ===== BIOMETRIC FACE MATCHING =====
@app.post("/api/biometric/face-compare", tags=["Biyometrik"], summary="Yüz eşleştirme",
          description="Kimlik belgesindeki fotoğraf ile canlı selfie karşılaştırması. Güven skoru (0-100) döner.")
@limiter.limit("10/minute")
async def biometric_face_compare(request: Request, req: FaceCompareRequest, user=Depends(require_auth)):
    try:
        result = await compare_faces(req.document_image_base64, req.selfie_image_base64)
        
        # Store result
        match_doc = {
            "match_id": str(uuid.uuid4()),
            "result": result,
            "match": result.get("match", False),
            "confidence_score": result.get("confidence_score", 0),
            "created_at": datetime.now(timezone.utc),
            "created_by": user.get("email"),
        }
        await db["biometric_matches"].insert_one(match_doc)
        
        return {
            "success": True,
            "match": result.get("match", False),
            "confidence_score": result.get("confidence_score", 0),
            "confidence_level": result.get("confidence_level", "low"),
            "analysis": result.get("analysis", {}),
            "notes": result.get("notes", ""),
            "warnings": result.get("warnings", []),
            "image_quality": result.get("image_quality", {}),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Yüz eşleştirme hatası: {str(e)}")


@app.get("/api/biometric/liveness-challenge", tags=["Biyometrik"], summary="Canlılık testi sorusu",
         description="Spoofing önleme için rastgele canlılık testi sorusu döner")
async def get_liveness_challenge_endpoint():
    """Kimlik doğrulama gerektirmez - ön check-in'de de kullanılabilir"""
    challenge = get_liveness_challenge()
    return challenge


@app.post("/api/biometric/liveness-check", tags=["Biyometrik"], summary="Canlılık testi doğrulama",
          description="Gönderilen fotoğrafın canlı kişiye ait olup olmadığını kontrol eder")
@limiter.limit("10/minute")
async def biometric_liveness_check(request: Request, req: LivenessCheckRequest, user=Depends(require_auth)):
    try:
        result = await check_liveness(req.image_base64, req.challenge_id)
        
        # Store result
        liveness_doc = {
            "session_id": req.session_id,
            "challenge_id": req.challenge_id,
            "result": result,
            "is_live": result.get("is_live", False),
            "confidence_score": result.get("confidence_score", 0),
            "created_at": datetime.now(timezone.utc),
            "created_by": user.get("email"),
        }
        await db["liveness_checks"].insert_one(liveness_doc)
        
        return {
            "success": True,
            "is_live": result.get("is_live", False),
            "challenge_completed": result.get("challenge_completed", False),
            "confidence_score": result.get("confidence_score", 0),
            "spoof_indicators": result.get("spoof_indicators", []),
            "notes": result.get("notes", ""),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Canlılık testi hatası: {str(e)}")


# ===== TC KIMLIK VALIDATION =====
@app.post("/api/tc-kimlik/validate", tags=["TC Kimlik"], summary="TC Kimlik No doğrulama",
          description="TC Kimlik No'nun geçerliliğini matematiksel algoritma ile kontrol eder")
async def validate_tc(req: TcKimlikValidateRequest, user=Depends(require_auth)):
    result = validate_tc_kimlik(req.tc_no)
    return result


@app.post("/api/tc-kimlik/emniyet-bildirimi", tags=["TC Kimlik"], summary="Emniyet bildirimi oluştur",
          description="Yabancı uyruklu misafir için Emniyet Müdürlüğü bildirim formu otomatik doldurur")
async def create_emniyet_bildirimi(req: EmniyetBildirimiRequest, user=Depends(require_auth)):
    try:
        guest = await guests_col.find_one({"_id": ObjectId(req.guest_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz misafir ID")
    if not guest:
        raise HTTPException(status_code=404, detail="Misafir bulunamadı")
    
    guest_data = serialize_doc(guest)
    
    # Check if foreign guest
    if not is_foreign_guest(guest_data.get("nationality", "")):
        raise HTTPException(status_code=400, detail="Bu misafir yabancı uyruklu değil. Emniyet bildirimi sadece yabancı misafirler için gereklidir.")
    
    # Get property/hotel data if available
    hotel_data = None
    properties = await list_properties(db, is_active=True)
    if properties:
        hotel_data = {
            "hotel_name": properties[0].get("name", ""),
            "hotel_address": properties[0].get("address", ""),
            "hotel_phone": properties[0].get("phone", ""),
            "hotel_tax_no": properties[0].get("tax_no", ""),
        }
    
    form = generate_emniyet_bildirimi(guest_data, hotel_data)
    
    # Store the form
    form["guest_id"] = req.guest_id
    form["created_by"] = user.get("email")
    await db["emniyet_bildirimleri"].insert_one(form)
    
    # Create audit log
    await create_audit_log(req.guest_id, "emniyet_bildirimi_created", 
                           metadata={"form_id": form["form_id"]}, 
                           user_email=user.get("email"))
    
    return {"success": True, "form": form}


@app.get("/api/tc-kimlik/emniyet-bildirimleri", tags=["TC Kimlik"], summary="Emniyet bildirimleri listesi")
async def list_emniyet_bildirimleri(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user=Depends(require_auth)
):
    query = {}
    if status:
        query["status"] = status
    total = await db["emniyet_bildirimleri"].count_documents(query)
    skip = (page - 1) * limit
    cursor = db["emniyet_bildirimleri"].find(query).sort("created_at", -1).skip(skip).limit(limit)
    forms = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        forms.append(doc)
    return {"forms": forms, "total": total, "page": page, "limit": limit}


# ===== PRE-CHECKIN (QR) =====
@app.post("/api/precheckin/create", tags=["Ön Check-in"], summary="QR ön check-in token oluştur",
          description="Misafirin varıştan önce telefonundan kimlik taraması yapabilmesi için QR token oluşturur")
async def create_precheckin(req: PreCheckinCreate, user=Depends(require_auth)):
    token = await create_precheckin_token(
        db, property_id=req.property_id,
        reservation_ref=req.reservation_ref,
        guest_name=req.guest_name,
        created_by=user.get("email")
    )
    return {"success": True, "token": serialize_doc(token)}


@app.get("/api/precheckin/list", tags=["Ön Check-in"], summary="Ön check-in tokenlarını listele")
async def list_precheckin(
    property_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user=Depends(require_auth)
):
    result = await list_precheckin_tokens(db, property_id=property_id, status=status, page=page, limit=limit)
    return result


@app.get("/api/precheckin/{token_id}", tags=["Ön Check-in"], summary="Token bilgisi (public)",
         description="QR kod ile erişilen token bilgisi. Kimlik doğrulama gerektirmez.")
async def get_precheckin_info(token_id: str):
    """Public endpoint - QR ile erişim"""
    token = await get_precheckin_token(db, token_id)
    if not token:
        raise HTTPException(status_code=404, detail="Geçersiz veya süresi dolmuş QR kod")
    if token.get("status") != "active":
        raise HTTPException(status_code=400, detail="Bu QR kod zaten kullanılmış")
    
    # Get property info
    prop = await get_property(db, token.get("property_id", ""))
    
    return {
        "token_id": token["token_id"],
        "status": token["status"],
        "property_name": prop.get("name", "Otel") if prop else "Otel",
        "reservation_ref": token.get("reservation_ref", ""),
        "guest_name": token.get("guest_name", ""),
    }


@app.post("/api/precheckin/{token_id}/scan", tags=["Ön Check-in"], summary="QR ile kimlik tara (public)",
          description="Misafirin kendi telefonundan kimlik belgesi taraması. Kimlik doğrulama gerektirmez.")
@limiter.limit("5/minute")
async def precheckin_scan(request: Request, token_id: str, req: PreCheckinScanRequest):
    """Public endpoint - Misafir kendi telefonundan tarar"""
    token = await get_precheckin_token(db, token_id)
    if not token:
        raise HTTPException(status_code=404, detail="Geçersiz QR kod")
    if token.get("status") != "active":
        raise HTTPException(status_code=400, detail="Bu QR kod zaten kullanılmış")
    
    try:
        extracted = await extract_id_data(req.image_base64)
        documents = extracted.get("documents", [])
        confidence = calculate_confidence_score(extracted)
        
        scan_doc = {
            "extracted_data": extracted,
            "document_count": extracted.get("document_count", len(documents)),
            "is_valid": any(d.get("is_valid", False) for d in documents),
            "created_at": datetime.now(timezone.utc),
            "status": "completed",
            "source": "precheckin",
            "token_id": token_id,
            "confidence_score": confidence.get("overall_score", 0),
            "confidence_level": confidence.get("confidence_level", "low"),
            "kvkk_consent": req.kvkk_consent,
        }
        await scans_col.insert_one(scan_doc)
        
        # Update token with scan data
        await use_precheckin_token(db, token_id, extracted)
        
        return {
            "success": True,
            "extracted_data": extracted,
            "documents": documents,
            "confidence": confidence,
            "message": "Kimlik taramanız başarılı! Otele vardığınızda hızlı check-in yapabilirsiniz.",
        }
    except Exception as e:
        fallback = [
            "Kimlik belgesi okunamadı. Lütfen şunları deneyin:",
            "1. Belgeyi düz bir yüzeye yerleştirin",
            "2. Flaş kullanarak fotoğraf çekin",
            "3. İyi aydınlatma altında tekrar deneyin",
        ]
        raise HTTPException(status_code=500, detail={
            "message": f"Tarama başarısız: {str(e)}",
            "fallback_guidance": fallback,
            "can_retry": True,
        })


@app.get("/api/precheckin/{token_id}/qr", tags=["Ön Check-in"], summary="QR kod görüntüsü",
         description="Ön check-in QR kodunu PNG olarak döndürür")
async def get_precheckin_qr(token_id: str, user=Depends(require_auth)):
    """QR kod oluştur ve döndür"""
    from fastapi.responses import StreamingResponse
    
    token = await get_precheckin_token(db, token_id)
    if not token:
        raise HTTPException(status_code=404, detail="Token bulunamadı")
    
    # QR code URL - frontend precheckin page
    frontend_url = os.environ.get("FRONTEND_URL", "")
    qr_url = f"{frontend_url}/precheckin/{token_id}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    
    return StreamingResponse(buf, media_type="image/png",
                             headers={"Content-Disposition": f"inline; filename=precheckin-{token_id}.png"})


# ===== MULTI-PROPERTY =====
@app.get("/api/properties", tags=["Multi-Property"], summary="Tesisleri listele")
async def get_properties(is_active: Optional[bool] = None, user=Depends(require_auth)):
    properties = await list_properties(db, is_active=is_active)
    return {"properties": properties, "total": len(properties)}


@app.post("/api/properties", tags=["Multi-Property"], summary="Yeni tesis oluştur")
async def create_new_property(req: PropertyCreate, user=Depends(require_admin)):
    prop = await create_property(
        db, name=req.name, address=req.address, phone=req.phone,
        tax_no=req.tax_no, city=req.city, created_by=user.get("email")
    )
    return {"success": True, "property": serialize_doc(prop)}


@app.get("/api/properties/{property_id}", tags=["Multi-Property"], summary="Tesis detayı")
async def get_property_detail(property_id: str, user=Depends(require_auth)):
    prop = await get_property(db, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Tesis bulunamadı")
    return {"property": prop}


@app.patch("/api/properties/{property_id}", tags=["Multi-Property"], summary="Tesis güncelle")
async def update_property_endpoint(property_id: str, req: PropertyUpdate, user=Depends(require_admin)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    prop = await update_property(db, property_id, updates)
    if not prop:
        raise HTTPException(status_code=404, detail="Tesis bulunamadı")
    return {"success": True, "property": prop}


# ===== KIOSK MODE =====
@app.post("/api/kiosk/session", tags=["Kiosk"], summary="Kiosk oturumu başlat")
async def start_kiosk_session(req: KioskSessionCreate, user=Depends(require_admin)):
    session = await create_kiosk_session(db, property_id=req.property_id, kiosk_name=req.kiosk_name)
    return {"success": True, "session": serialize_doc(session)}


@app.get("/api/kiosk/sessions", tags=["Kiosk"], summary="Kiosk oturumları listele")
async def list_kiosk_sessions(
    property_id: Optional[str] = None,
    status: Optional[str] = None,
    user=Depends(require_auth)
):
    sessions = await get_kiosk_sessions(db, property_id=property_id, status=status)
    return {"sessions": sessions, "total": len(sessions)}


@app.post("/api/kiosk/scan", tags=["Kiosk"], summary="Kiosk kimlik tarama",
          description="Kiosk modunda kimlik tarama - session_id ile çalışır")
@limiter.limit("20/minute")
async def kiosk_scan(request: Request, scan_req: ScanRequest, 
                     session_id: str = Query(..., description="Kiosk session ID")):
    """Kiosk taraması - basic auth yeterli, session bazlı"""
    try:
        extracted = await extract_id_data(scan_req.image_base64)
        documents = extracted.get("documents", [])
        confidence = calculate_confidence_score(extracted)
        
        scan_doc = {
            "extracted_data": extracted,
            "document_count": extracted.get("document_count", len(documents)),
            "is_valid": any(d.get("is_valid", False) for d in documents),
            "created_at": datetime.now(timezone.utc),
            "status": "completed",
            "source": "kiosk",
            "session_id": session_id,
            "confidence_score": confidence.get("overall_score", 0),
            "confidence_level": confidence.get("confidence_level", "low"),
        }
        await scans_col.insert_one(scan_doc)
        
        # Update kiosk activity
        await update_kiosk_activity(db, session_id, scan_increment=1)
        
        return {
            "success": True,
            "scan": serialize_doc(scan_doc),
            "extracted_data": extracted,
            "documents": documents,
            "confidence": confidence,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "message": f"Kiosk tarama hatası: {str(e)}",
            "fallback_guidance": [
                "Belgeyi düz yerleştirin", "Flaş kullanın", "Tekrar deneyin"
            ],
        })


# ===== OFFLINE SYNC =====
@app.post("/api/sync/upload", tags=["Offline Sync"], summary="Çevrimdışı veri yükle",
          description="Internet kesintisinde biriktirilen verileri sunucuya yükler")
async def upload_offline_data(req: OfflineSyncRequest, user=Depends(require_auth)):
    if req.data_type not in ("scans", "guests"):
        raise HTTPException(status_code=400, detail="Geçersiz veri tipi. scans veya guests olmalı.")
    sync = await store_offline_data(
        db, property_id=req.property_id, data_type=req.data_type,
        data=req.data, device_id=req.device_id
    )
    return {"success": True, "sync": serialize_doc(sync)}


@app.get("/api/sync/pending", tags=["Offline Sync"], summary="Bekleyen senkronizasyonlar")
async def get_pending_sync(property_id: Optional[str] = None, user=Depends(require_auth)):
    syncs = await get_pending_syncs(db, property_id=property_id)
    return {"syncs": syncs, "total": len(syncs)}


@app.post("/api/sync/{sync_id}/process", tags=["Offline Sync"], summary="Senkronizasyonu işle")
async def process_sync_data(sync_id: str, user=Depends(require_admin)):
    """Offline verilerini gerçek DB'ye işle"""
    col = db["offline_sync"]
    sync_doc = await col.find_one({"sync_id": sync_id})
    if not sync_doc:
        raise HTTPException(status_code=404, detail="Senkronizasyon bulunamadı")
    
    errors = []
    processed = 0
    
    for item in sync_doc.get("data", []):
        try:
            if sync_doc["data_type"] == "guests":
                guest_doc = {
                    **item,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                    "status": "pending",
                    "source": "offline_sync",
                    "sync_id": sync_id,
                }
                await guests_col.insert_one(guest_doc)
                processed += 1
            elif sync_doc["data_type"] == "scans":
                scan_doc = {
                    **item,
                    "created_at": datetime.now(timezone.utc),
                    "source": "offline_sync",
                    "sync_id": sync_id,
                }
                await scans_col.insert_one(scan_doc)
                processed += 1
        except Exception as e:
            errors.append(f"Kayıt işleme hatası: {str(e)}")
    
    status = "processed" if not errors else "partial"
    result = await process_sync(db, sync_id, status=status, errors=errors)
    
    return {
        "success": True,
        "processed_count": processed,
        "error_count": len(errors),
        "errors": errors,
        "sync": result,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
