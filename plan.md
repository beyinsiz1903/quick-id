# Quick ID Reader (Hotel) — Development Plan

## 1. Objectives
- Prove the **core workflow** works reliably: **Camera image → OpenAI GPT-4o Vision → structured guest JSON**.
- Build a V1 web app (React + FastAPI) to **scan IDs**, **review/correct extracted fields**, and **save scan history** in MongoDB.
- Support **all ID types** (TC kimlik new/old, passport, driver’s license) via prompt + validation.
- Enable **bulk scanning** (scan many guests sequentially) with a fast operator UX.
- Provide **clean REST APIs** to make future **Syroce PMS** integration straightforward.
- Add basic **guest management** (check-in/check-out) around the scan records.

---

## 2. Implementation Steps (Phased)

### Phase 1 — Core POC (Isolation): Vision Extraction Works End-to-End
**Goal:** Do not proceed until extraction is accurate + consistent for real ID photos.

**User stories (POC)**
1. As an operator, I can send a single ID image to the backend and receive structured JSON fields.
2. As an operator, I can see the model’s confidence/notes when a field is uncertain.
3. As an operator, I can test multiple ID types (TC new/old, passport, license) and compare results.
4. As an operator, I can detect when the image is unusable (blurry/glare/cropped) and get a retry message.
5. As a developer, I can rerun the same test set and get stable JSON schema output.

**Steps**
- Web search: best practices for **OpenAI Vision structured extraction** (JSON schema/response_format), image size limits, and common failure modes.
- Create a minimal **Python POC script**:
  - Input: local image file(s)
  - Output: strict JSON with fields: `first_name, last_name, id_number, birth_date, gender, nationality, id_type`
  - Include `raw_text` (optional) + `warnings` array
- Iterate prompt + response constraints until:
  - JSON always parses
  - Field formats are consistent (date normalization, gender mapping)
  - Handles at least a small set of real-world sample images per ID type
- Define validation rules (backend-side):
  - `birth_date` ISO format or null
  - `id_number` basic length/character sanity checks (TC numeric, passport alphanumeric)
  - If validation fails → mark as `needs_review=true`

**Exit criteria (must meet)**
- ≥90% correct extraction on the sample set after manual verification.
- 100% valid JSON responses (no free-form).
- Clear failure behavior for low-quality images.

---

### Phase 2 — V1 App Development (MVP): Scan → Review → Save → History
**User stories (V1)**
1. As an operator, I can open the web app and start the camera to scan an ID.
2. As an operator, I can capture a photo, see the preview, and re-take if needed.
3. As an operator, I can review/edit extracted fields before saving.
4. As an operator, I can scan guests one-by-one in a fast “next scan” flow (bulk mode).
5. As a manager, I can view scan history and open a guest record to see details.

**Backend (FastAPI)**
- Implement endpoints:
  - `POST /api/scan` (image base64/multipart) → returns extracted + validated JSON
  - `POST /api/guests` → persist guest + scan metadata
  - `GET /api/guests?query=&dateFrom=&dateTo=` → list/history
  - `GET /api/guests/{id}` → detail
  - `PATCH /api/guests/{id}` → edit fields
  - `POST /api/guests/{id}/checkin` and `/checkout`
- MongoDB collections:
  - `guests` (current profile fields)
  - `scans` (immutable scan events: image hash, timestamps, model output, operator corrections)
- Integrate Emergent LLM key for GPT-4o Vision based on POC-proven prompt.

**Frontend (React + shadcn/ui)**
- Pages/views:
  - **Scan**: camera start/stop, capture, preview, “Extract”, form edit, save
  - **Bulk Scan Mode**: auto-return to camera after save; counter of completed scans
  - **History**: table with filters; status chips (needs_review, checked_in)
  - **Guest Detail**: scan timeline + edit + check-in/out actions
- UX states: loading, extraction failed (retry), validation warnings, offline/permission errors.

**Phase 2 testing (end-to-end)**
- Run one full E2E pass: camera capture → extract → edit → save → history → check-in/out.
- Verify image upload/display + DB persistence + API error handling.

---

### Phase 3 — Feature Expansion: PMS-Ready Integration + Bulk Improvements
**User stories (Expansion)**
1. As an operator, I can queue multiple scans and save them with minimal clicks.
2. As a manager, I can export selected guest records as JSON/CSV for PMS import.
3. As a developer, I can push a guest record to an external PMS endpoint via a single API call.
4. As an operator, I can merge duplicate guests when the same person is scanned twice.
5. As a manager, I can audit what was extracted vs what was manually corrected.

**Steps**
- Define a **PMS adapter interface** in backend (disabled by default):
  - `POST /api/integrations/syroce/push/{guestId}` (placeholder)
  - Store integration status per guest (`pending/sent/failed`) + last error.
- Add export endpoints:
  - `GET /api/exports/guests.csv` (filtered)
  - `GET /api/exports/guests.json`
- Improve bulk mode:
  - keyboard shortcuts, “auto-extract after capture”, configurable required fields.
- Add duplicate detection: match on `id_number` + name + birth_date.

**Phase 3 testing (end-to-end)**
- Bulk scanning of 10+ samples; verify performance and no data loss.
- Export correctness and schema stability for integration.

---

### Phase 4 — Hardening & Compliance Pass (Before Production Use)
**User stories (Hardening)**
1. As a business owner, I can configure data retention (auto-delete images after N days).
2. As an operator, I cannot accidentally view or edit past scans without proper permissions (if auth is added).
3. As a manager, I can see system health and failed extraction logs.
4. As an operator, I get clear guidance when camera permissions are blocked.
5. As a manager, I can run in “no-image-storage mode” (store only extracted text).

**Steps**
- Decide with user: add auth/roles now? (note: auth slows iterative testing)
- Add security: at-rest protection strategy, redaction, retention policies.
- Add observability: structured logs, request IDs, basic admin diagnostics.

---

## 3. Next Actions (Immediate)
1. Collect 10–20 representative ID images (cover all ID types; varying lighting/angles).
2. Run Phase 1 web research + implement Python POC script.
3. Lock the extraction prompt + strict JSON schema + validation rules.
4. After POC exit criteria passes, start Phase 2 V1 app build (frontend+backend+MongoDB).

---

## 4. Success Criteria
- Core: camera/image → GPT-4o Vision → **parsable structured JSON** with consistent formats.
- Accuracy: operator reports minimal manual correction for standard-quality images.
- Reliability: failed captures give actionable retry guidance; no silent failures.
- Data: all scans saved with history; guest records editable; check-in/out works.
- Bulk: scanning multiple guests is fast (low-click) and stable.
- Integration-ready: REST endpoints + export formats stable enough for Syroce PMS adapter once their API details are available.
