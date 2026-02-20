# Quick ID Reader (Hotel) — Updated Development Plan (Phase 3 Completed)

## 1. Objectives
- ✅ **Core workflow proven & delivered:** **Camera image → OpenAI GPT-4o Vision → structured guest JSON**.
- ✅ Deliver a production-ready **V1 web app** (React + FastAPI) to **scan IDs**, **review/correct extracted fields**, and **save scan history** in MongoDB.
- ✅ Support **all ID types** (TC kimlik new/old, passport, driver’s license) via prompt-driven extraction.
- ✅ Enable **bulk scanning** (scan many guests sequentially) with fast operator UX.
- ✅ Provide **clean REST APIs** to support future **Syroce PMS** integration.
- ✅ Basic **guest management** implemented (CRUD + check-in/check-out).
- ✅ **Phase 3 enhancements delivered:**
  - **Bulk scan ergonomics:** auto-extract toggle + keyboard shortcuts (Ctrl+S, Ctrl+R, Esc)
  - **Duplicate detection:** by `id_number` (high confidence) + name+birthdate (medium confidence)
  - **Audit trail:** field-level diffs on create/update/check-in/check-out/delete; store original AI extraction vs final saved edits
- ▶️ **Current objective (Phase 4):** Hardening, privacy/compliance controls, and **Syroce PMS adapter implementation** once integration details are available.

---

## 2. Implementation Steps (Phased)

### Phase 1 — Core POC (Isolation): Vision Extraction Works End-to-End ✅ COMPLETED
**Goal:** Validate extraction reliability before building the full app.

**User stories (POC)**
1. ✅ As an operator, I can send a single ID image to the backend and receive structured JSON fields.
2. ✅ As an operator, I can see model notes via warnings when fields are uncertain.
3. ✅ As an operator, I can test multiple ID types and compare results.
4. ✅ As an operator, I can detect when the image is unusable and get a retry message.
5. ✅ As a developer, I can rerun the same test set and get stable JSON schema output.

**What was built**
- Python POC script validating:
  - Base64 image flow
  - Consistent JSON parsing
  - Invalid/non-ID image handling
- Emergent universal key (`EMERGENT_LLM_KEY`) integration for OpenAI access.

**Exit criteria (met)**
- ✅ Stable structured JSON responses
- ✅ Clear failure behavior for low-quality/irrelevant images
- ✅ 4/4 POC tests passing

---

### Phase 2 — V1 App Development (MVP): Scan → Review → Save → History ✅ COMPLETED
**User stories (V1)**
1. ✅ As an operator, I can open the web app and start the camera to scan an ID.
2. ✅ As an operator, I can capture a photo, see preview, and re-take if needed.
3. ✅ As an operator, I can review/edit extracted fields before saving.
4. ✅ As an operator, I can scan guests one-by-one in a fast “next scan” flow (bulk mode).
5. ✅ As a manager, I can view scan history and open guest record details.

**Backend (FastAPI) — implemented**
- Endpoints implemented:
  - `GET /api/health`
  - `POST /api/scan` (base64 image) → extracted JSON + scan record
  - `GET /api/scans` (pagination)
  - `POST /api/guests`
  - `GET /api/guests` (pagination + search + status filter)
  - `GET /api/guests/{id}`
  - `PATCH /api/guests/{id}`
  - `DELETE /api/guests/{id}`
  - `POST /api/guests/{id}/checkin`
  - `POST /api/guests/{id}/checkout`
  - `GET /api/dashboard/stats`
  - `GET /api/exports/guests.json`
  - `GET /api/exports/guests.csv`
- MongoDB collections implemented:
  - `guests` (profile + status + timestamps)
  - `scans` (scan events + extracted payload + warnings)
- AI integration:
  - OpenAI `gpt-4o` via Emergent LLM key
  - Strict JSON extraction prompt, warnings included

**Frontend (React + shadcn/ui) — implemented**
- Pages delivered (Turkish UI):
  - **Dashboard**: KPI cards, weekly chart, recent guests/scans, quick actions
  - **Scan**: camera capture + extraction + editable form + save
  - **Bulk Scan**: sequential scanning with counter + undo last
  - **Guests**: searchable/filterable table + pagination + actions
  - **Guest Detail**: edit fields, check-in/out, timeline
- UX states:
  - Camera permission/not found handling
  - Loading/extracting skeletons
  - Toast feedback (sonner)
- Design:
  - Professional hotel PMS-style light theme, shadcn tokens applied

**Phase 2 testing (met)**
- ✅ Testing agent: 100% pass rate backend + frontend + integration
- Minor: low-priority accessibility warning around mobile sheet title/description (addressed/improved)

---

### Phase 3 — Feature Expansion: PMS-Ready Integration + Bulk Improvements ✅ COMPLETED
**User stories (Expansion)**
1. ✅ As an operator, I can scan multiple guests faster with fewer clicks and optional automation.
2. ✅ As a manager, I can export data in PMS-friendly formats (CSV schemas, JSON mapping). *(baseline export already present)*
3. ▶️ As a developer, I can push a guest record to **Syroce PMS** via a configurable adapter (requires Syroce API details).
4. ✅ As an operator, I can detect duplicates (same ID number) during creation.
5. ✅ As a manager, I can audit what was extracted vs what was manually corrected.

**What was implemented in Phase 3**

#### 3.1 Bulk scan enhancements (operator ergonomics) ✅
- ✅ **Auto-extract toggle** (bulk scan): operator can enable/disable automatic extraction on capture.
- ✅ **Keyboard shortcuts** (bulk scan):
  - `Ctrl/Cmd + S` → Save
  - `Ctrl/Cmd + R` → Next scan / reset
  - `Esc` → Cancel dialog / reset
- ✅ UX messaging updated to guide operators (e.g., “Ctrl+S ile kaydedin”).

#### 3.2 Data quality & duplicates ✅
- ✅ Duplicate detection on guest creation:
  - **Primary match:** exact `id_number` → `match_confidence: high`
  - **Secondary match:** `first_name + last_name + birth_date` → `match_confidence: medium`
- ✅ New endpoint:
  - `GET /api/guests/check-duplicate`
- ✅ Create guest behavior:
  - If duplicate found → returns `duplicate_detected: true` + list of matches
  - Supports override: `force_create: true`
- ✅ Frontend flow:
  - Duplicate warning dialog listing matches; allows “Mevcut Kaydı Gör” or “Yine de Kaydet”.

#### 3.3 Audit trail ✅
- ✅ New MongoDB collection: `audit_logs`
- ✅ Stored on guest record: `original_extracted_data` (AI’s original extraction snapshot)
- ✅ Audit recorded for:
  - `created`, `updated`, `checked_in`, `checked_out`, `deleted`
- ✅ Field-level diffs recorded (old/new values) for tracked fields.
- ✅ New endpoints:
  - `GET /api/guests/{guest_id}/audit`
  - `GET /api/audit/recent`
- ✅ Frontend:
  - Guest detail page shows **Denetim İzi** timeline + field changes.
  - Shows **AI Çıkarım Verileri** panel to compare AI extraction vs final saved data.

**Phase 3 testing (end-to-end) ✅**
- ✅ Testing agent: **100% pass rate** for Phase 3 backend + frontend + integration.
- ✅ Validated:
  - Duplicate detection responses + force create bypass
  - Audit logs created for CRUD + check-in/out
  - Bulk scan UI controls render correctly

---

### Phase 4 — Hardening & Syroce PMS Integration (Before Production Rollout) ▶️ NEXT
**User stories (Hardening & Integration)**
1. As a business owner, I can configure data retention (auto-delete images after N days).
2. As an operator, I can only view/edit data based on permissions (role-based access).
3. As a manager, I can see failed extraction logs and integration failures.
4. As an operator, I get clear guidance when camera permissions are blocked.
5. As a manager, I can run in “no-image-storage mode” (store only extracted fields + scan metadata).
6. As a developer, I can reliably sync/push guest info into **Syroce PMS**.

**Implementation steps**

#### 4.1 Syroce PMS integration readiness (adapter) ▶️
- Confirm Syroce PMS integration method:
  - REST API? SOAP? Database sync? File import? Webhook?
  - Auth method (API key, OAuth2, Basic)
  - Required payload schema for guest/check-in
- Implement adapter pattern:
  - `POST /api/integrations/syroce/push/{guestId}`
  - Config storage (env + optional DB)
  - Persist integration status on guest:
    - `integration_status: pending|sent|failed`, `last_error`, `last_sent_at`
- Add retry & queue behavior:
  - Manual retry button
  - Background job (optional) for pending/failed

#### 4.2 Privacy, retention, and compliance ▶️
- Add authentication & roles (Admin / Reception).
- Add privacy controls:
  - Optional image storage toggle
  - Retention policy + scheduled deletion
- Add observability:
  - Request IDs
  - Structured logs
  - Integration failure dashboard
- Security review:
  - CORS tightening
  - Rate limiting on scan endpoint
  - Field-level redaction for exports (optional)

#### 4.3 Export improvements (PMS-friendly templates) ▶️
- Provide multiple CSV templates (e.g., “PMS Import”, “Police/Legal report” if needed)
- Add field mapping/alias layer (e.g., `TCKN` vs `IdentityNo`)
- Add more filtering options on export endpoints (status/date/nationality)

---

## 3. Next Actions (Immediate)
1. Gather **Syroce PMS integration details**:
   - API/base URL, auth, required fields, check-in endpoint(s), test environment.
2. Decide the **integration mode**:
   - Push guest on save? Push on check-in? Both?
3. Implement the **Syroce adapter scaffolding** + integration status tracking.
4. Add hardening items:
   - Authentication/roles
   - Retention + optional no-image mode
   - Rate limiting + tighter CORS

---

## 4. Success Criteria
- ✅ Core extraction: camera/image → GPT-4o Vision → **parsable structured JSON** with consistent formats.
- ✅ App reliability: scan → edit → save → history; no silent failures.
- ✅ Data integrity: guests saved, editable, check-in/out works, exports available.
- ✅ Bulk scanning: fast sequential workflow with low clicks (**plus shortcuts + auto-extract**).
- ✅ Data quality: **duplicate detection** prevents accidental duplicate records.
- ✅ Auditability: **denetim izi** available for create/update/status changes, including AI vs manual diffs.
- ▶️ PMS integration: Syroce adapter can reliably send guest data and report status/errors.
- ▶️ Compliance: retention/no-image mode and access control before production rollout.
