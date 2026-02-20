# Quick ID Reader (Hotel) — Updated Development Plan

## 1. Objectives
- ✅ **Core workflow proven & delivered:** **Camera image → OpenAI GPT-4o Vision → structured guest JSON**.
- ✅ Deliver a production-ready **V1 web app** (React + FastAPI) to **scan IDs**, **review/correct extracted fields**, and **save scan history** in MongoDB.
- ✅ Support **all ID types** (TC kimlik new/old, passport, driver’s license) via prompt-driven extraction.
- ✅ Enable **bulk scanning** (scan many guests sequentially) with fast operator UX.
- ✅ Provide **clean REST APIs** to support future **Syroce PMS** integration.
- ✅ Basic **guest management** implemented (CRUD + check-in/check-out).
- ▶️ **Current objective (Phase 3):** Prepare and implement **PMS integration layer** (adapter), strengthen bulk scanning ergonomics, and enhance exports/auditing for front-desk operations.

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

### Phase 3 — Feature Expansion: PMS-Ready Integration + Bulk Improvements ▶️ NEXT
**User stories (Expansion)**
1. As an operator, I can scan multiple guests faster with fewer clicks and optional automation.
2. As a manager, I can export data in PMS-friendly formats (CSV schemas, JSON mapping).
3. As a developer, I can push a guest record to **Syroce PMS** via a configurable adapter (once API details exist).
4. As an operator, I can detect and merge duplicate guests (same ID number).
5. As a manager, I can audit what was extracted vs what was manually corrected.

**Implementation steps**
- **Syroce PMS integration readiness**
  - Confirm Syroce PMS integration method:
    - REST API? SOAP? Database sync? File import? Webhook?
    - Auth method (API key, OAuth2, Basic)
    - Required payload schema for guest/check-in
  - Implement adapter pattern (disabled by default):
    - `POST /api/integrations/syroce/push/{guestId}`
    - Add integration config storage (env + optional DB table)
    - Persist integration status on guest: `integration_status: pending|sent|failed`, `last_error`, `last_sent_at`
  - Add retry & queue behavior:
    - Manual retry button
    - Background job (optional) for pending/failed

- **Export improvements**
  - Provide multiple CSV templates (e.g., “PMS Import”, “Police/Legal report” if needed)
  - Add field mapping/alias layer (e.g., `TCKN` vs `IdentityNo`)
  - Add filtering options on export endpoints (status/date/nationality)

- **Bulk scan enhancements (operator ergonomics)**
  - Optional auto-extract after capture
  - Keyboard shortcuts (Save, Retake, Next)
  - Required-field validation policy per document type
  - Batch review queue for `is_valid=false` / warnings

- **Data quality & duplicates**
  - Duplicate detection by `id_number` (primary), fallback composite match (name + birthdate)
  - Merge flow (choose canonical record, append scan history)

- **Audit trail**
  - Store operator corrections:
    - Track `original_extracted_data` vs `final_saved_data`
    - Persist diffs per field (who/when — operator identity later)

**Phase 3 testing (end-to-end)**
- Bulk scanning test (10+ sequential saves) with no UI dead-ends.
- Export schema tests (CSV/JSON structure stable).
- Integration adapter tests using mocked Syroce endpoint until real API is available.

---

### Phase 4 — Hardening & Compliance Pass (Before Production Use) ⏳ PLANNED
**User stories (Hardening)**
1. As a business owner, I can configure data retention (auto-delete images after N days).
2. As an operator, I can only view/edit data based on permissions (role-based access).
3. As a manager, I can see failed extraction logs and integration failures.
4. As an operator, I get clear guidance when camera permissions are blocked.
5. As a manager, I can run in “no-image-storage mode” (store only extracted fields + scan metadata).

**Steps**
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

---

## 3. Next Actions (Immediate)
1. Gather **Syroce PMS integration details**:
   - API/base URL, auth, required fields, check-in endpoint(s), and test environment.
2. Decide the **integration mode**:
   - Push guest on save? Push on check-in? Both?
3. Implement the **Syroce adapter scaffolding** + integration status tracking.
4. Enhance **bulk scan UX** (auto-next, keyboard shortcuts, review queue).
5. Add **duplicate detection** by `id_number`.

---

## 4. Success Criteria
- ✅ Core extraction: camera/image → GPT-4o Vision → **parsable structured JSON** with consistent formats.
- ✅ App reliability: scan → edit → save → history; no silent failures.
- ✅ Data integrity: guests saved, editable, check-in/out works, exports available.
- ✅ Bulk scanning: fast sequential workflow with low clicks.
- ▶️ PMS integration: Syroce adapter can reliably send guest data and report status/errors.
- ▶️ Compliance: optional retention/no-image mode and access control before production rollout.
