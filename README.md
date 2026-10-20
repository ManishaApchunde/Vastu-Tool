# Vastu Plan Analyzer — MVP

Upload a floor plan, let AI suggest rooms, doors and windows, verify the plan yourself, set true North, and get a transparent, rule-based Vastu assessment with a score, findings, remedies and a PDF report.

Vastu is treated here as a traditional methodology, not a science. Every finding says which rule set it comes from, and nothing is analysed until a person has verified the plan.

```
Upload ─► AI detection ─► User verification ─► Set North ─► Centre + 3×3 zones ─► Rules ─► Score ─► Remedies ─► Dashboard / PDF
 (JPG/PNG/PDF)  (suggestions only)   (source of truth)    (north_angle)   (geometry engine)   (DB)    (config)   (approved DB)
```

## Project structure

```
vastu-ai/
├── docker-compose.yml          Postgres, Redis, MinIO, API, Celery worker, web
├── backend/                    Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · Celery
│   ├── app/
│   │   ├── main.py             App factory: lifespan (create tables + seed), CORS, rate limit, /health
│   │   ├── core/               config (env settings), db, errors (uniform error JSON), security (bcrypt, JWT,
│   │   │                       signed file URLs), ratelimit, deps (auth + ownership checks)
│   │   ├── models/             16 tables: users, projects, properties, floor_plans, rooms, openings,
│   │   │                       north_orientations, vastu_zones, rule_sets, vastu_rules, remedies,
│   │   │                       scoring_configs, analyses, findings, reports, processing_jobs
│   │   ├── schemas/            Request validation (Pydantic)
│   │   ├── api/                auth · projects · floor_plans · misc (reports, jobs, signed files)
│   │   ├── ai/                 FloorPlanAnalyzer interface, MockFloorPlanAnalyzer, vision-LLM analyzer,
│   │   │                       factory, preprocessing (type sniffing, PDF rasterising, quality checks)
│   │   ├── geometry/           Pure geometry: centre, North rotation, zone systems (3×3 registered), overlaps
│   │   ├── vastu/              Rule engine + canonical room types
│   │   ├── scoring/            Score engine (weights from the scoring config table)
│   │   ├── remedies/           Remedy lookup (approved catalogue only)
│   │   ├── reports/            Plan overlay renderer (Pillow) + PDF builder (ReportLab) + report job
│   │   ├── insights/           Customer tools: FitCheck, trust passport, mistake catcher, explain score, change
│   │   │                       history, daily-life conflicts, family priority, construction stage, post-move
│   │   │                       verification, expert review handoff, voice explainer (see CHECKLIST.md)
│   │   ├── videos/             Video report: script (scenes), slides (ReportLab → PNG), tts (edge-tts / gTTS /
│   │   │                       captions only), compose (ffmpeg), service (job)
│   │   ├── services/           pipeline (workflow + status machine), jobs (retry), storage (local/S3), serializers
│   │   ├── workers/            Celery app + task
│   │   └── seed/               rules.json, remedies.json, scoring.json, demo plan drawing, seed script
│   ├── alembic/                Migrations (0001 … 0005_action_plan_and_video)
│   └── tests/                  68 tests: geometry, engines, full API workflow, reports, insight tools, video
└── frontend/                   Next.js 15 (App Router) · React 19 · TypeScript · Tailwind
    ├── app/                    login, (app)/dashboard, projects, projects/new, projects/[id]/{upload,verify,north,analysis,report}
    ├── components/             AppShell, PlanCanvas (SVG overlay), ui (badges, stepper, errors), useProject
    ├── features/               verify/Editor, north/CompassDial, analysis/Dashboard, ProjectHeader, ProjectRow
    ├── services/api.ts         Typed API client (auth header, error mapping, upload progress)
    └── types/api.ts            Response types
```

## Quick start (local, no Docker)

Needs Python 3.12+ and Node 20+. SQLite, local file storage, inline jobs and the mock AI are the defaults, so nothing else has to be running.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # optional; defaults work
uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install
cp .env.example .env.local      # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                     # http://localhost:3000
```

On first start the API creates the tables and seeds the rule set, remedies, scoring config and a demo account. Sign in with **demo@example.com / demo12345**, then click **Open demo project** for a finished analysis, or create a project and upload a plan.

API docs: http://localhost:8000/docs

## Full stack with Docker

```bash
docker compose up --build
```

This runs PostgreSQL, Redis, MinIO (S3-compatible, private bucket created automatically), the API (runs `alembic upgrade head` on start), a Celery worker and the web app on http://localhost:3000. Its settings are in `backend/.env.docker`; change `SECRET_KEY` before exposing it anywhere.

## Environment variables

Backend (`backend/.env`, or plain env vars; see `backend/.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./vastu_dev.db` | Use `postgresql+psycopg2://…` outside local dev |
| `AUTO_CREATE_TABLES` | `true` | Dev convenience. Set `false` and use Alembic in production |
| `AUTO_SEED` | `true` | Seed rules, remedies, scoring config and demo user when empty |
| `SECRET_KEY` | insecure placeholder | Signs JWTs and local file URLs. **Must** be changed |
| `ACCESS_TOKEN_MINUTES` | `720` | Login lifetime |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated list |
| `STORAGE_BACKEND` | `local` | `local` or `s3` |
| `LOCAL_STORAGE_DIR` | `./storage` | Where local files go |
| `PUBLIC_API_URL` | `http://localhost:8000` | Base for signed local file URLs |
| `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION` | — | S3 or MinIO |
| `S3_PUBLIC_ENDPOINT_URL` | — | Host browsers use for presigned URLs, if different from the internal one |
| `SIGNED_URL_TTL_SECONDS` | `600` | File link lifetime |
| `MAX_UPLOAD_MB` / `MIN_IMAGE_SIDE` / `MAX_IMAGE_PIXELS` / `BLUR_THRESHOLD` | 15 / 300 / 40M / 40 | Upload validation and quality warnings |
| `JOB_MODE` | `inline` | `inline` (FastAPI background tasks) or `celery` |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker and result backend |
| `JOB_MAX_ATTEMPTS` | `3` | Retry cap for detection and report jobs |
| `AI_PROVIDER` | `mock` | `mock` or `anthropic` |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `AI_TIMEOUT_SECONDS` | —, `claude-sonnet-5`, 90 | Vision analyzer |
| `RATE_LIMIT_PER_MINUTE` / `UPLOAD_RATE_LIMIT_PER_MINUTE` | 240 / 12 | Per client IP |
| `ENVIRONMENT` | `development` | `test` disables rate limiting |
| `REPORT_BRAND` | `Vastu Plan Analyzer` | Name printed on PDF reports |
| `VIDEO_TTS` | `auto` | Video narration: `auto`, `edge`, `gtts` or `silent` (captions only) |
| `VIDEO_VOICE_MR`, `VIDEO_VOICE_EN`, `VIDEO_VOICE_RATE` | `mr-IN-AarohiNeural`, `en-IN-NeerjaNeural`, `-4%` | Narration voices |
| `VIDEO_BURN_CAPTIONS` | `true` | Draw captions on the video |

Frontend: `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). It is baked in at build time.

## Database

SQLite needs no setup. For PostgreSQL:

```bash
createdb vastu
export DATABASE_URL=postgresql+psycopg2://USER:PASS@localhost:5432/vastu AUTO_CREATE_TABLES=false
cd backend && alembic upgrade head
python -m app.seed.seed                 # rules, remedies, scoring config, demo user
python -m app.seed.seed --reset-rules   # reload rules/remedies/scoring from the JSON files
```

New migration after a model change: `alembic revision --autogenerate -m "describe change"`.

Migration `0002_report_fields` adds remedy `kind` / `phase` / `structural_note` and the property's `client_name`. A local dev database created with `AUTO_CREATE_TABLES=true` is upgraded automatically on startup: missing nullable columns are added, and the remedy catalogue fields are back-filled from `remedies.json`. PostgreSQL deployments should run `alembic upgrade head`.

## Running workers

Set `JOB_MODE=celery` and `REDIS_URL`, start Redis, then:

```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info
```

Detection and PDF generation become Celery tasks. Every job is a `processing_jobs` row with status, attempt count and error, so failures show in the UI and can be retried (`POST /jobs/{id}/retry`) up to `JOB_MAX_ATTEMPTS`.

## Tests

```bash
cd backend && python -m pytest -q      # 68 tests
cd frontend && npm run typecheck && npm run build
```

The API tests walk the full workflow and also cover:

- North rotation actually changing zones.
- Ownership isolation between users.
- Upload validation: wrong type, fake extension, oversized, too small, and PDF.
- Invalid room geometry.
- AI failure followed by retry.
- Expired file links.
- The demo endpoint.

## How the modules work

**AI detection (`app/ai`).** Everything talks to the `FloorPlanAnalyzer` interface, which returns a `DetectionResult` with rooms (name, type, polygon, confidence), doors, windows, main entrance, stairs and warnings. `MockFloorPlanAnalyzer` returns a realistic layout scaled to the uploaded image. It deliberately includes one unnamed low-confidence room and an uncertain entrance so the verification flow has something to fix. `VisionLLMFloorPlanAnalyzer` sends the image to Anthropic's Messages API and validates the JSON it gets back. Detection is stored separately from verified data and is never analysed directly.

**Verification.** The editor starts from the AI suggestions, or from the previously verified plan. Each room and opening keeps a `source` of `ai`, `ai_edited` or `user`. `PUT /floor-plans/{id}/verification` replaces the verified rooms and openings after checking the geometry: valid polygons that stay inside the image. It also clears anything derived from them (zones, analysis inputs).

**North.** `north_angle` is degrees clockwise from the top edge of the image to true North. The top of the image is never assumed to be North. The user must confirm an angle before zones can be calculated.

**Geometry (`app/geometry`).** This is pure functions with no UI or database code:

1. The centre (Brahmasthan) is the centroid of the plan boundary. The boundary is derived from the rooms when none is given.
2. The plan is rotated by `-north_angle` so North points up.
3. A zone system splits the North-aligned bounding box. `Grid3x3` is registered in a zone-system registry, so 16, 32 or 45 zones can be added without touching callers.
4. Each room gets the zone it overlaps most, plus every overlap share. Openings get the zone they sit in.
5. Zone coverage (how much of each zone is built) is recorded, and zone polygons are rotated back to image coordinates for display.

**Rules (`app/vastu`).** Rules live in the `vastu_rules` table, grouped by rule set. Each has a JSON `condition`, a status (`draft` or `approved`) and a weight. Only approved rules run. The evaluators are:

- `room_in_zone` (preferred, acceptable or issue by severity)
- `entrance_in_zone`
- `room_overlaps_zone`
- `zone_free_of`
- `zone_coverage` (cut corners)
- `opening_share`
- `element_missing`

Rules match on canonical room types, never free-text labels. Rooms with no matching rule are reported as "not scored" instead of silently passing.

**Scoring (`app/scoring`).** The weights come from the active `scoring_configs` row:

- **Points per finding:** a finding earns `weight × points`. Preferred scores 1.0, acceptable 0.75, and an issue scores 0.5, 0.25 or 0 for low, medium or high severity.
- **Category scores:** each category's score is its earned points divided by its possible points.
- **Overall score:** the weighted mean of the categories: rooms 30%, entrance 20%, zones 20%, layout 15%, directions 15%. Categories with nothing to score are left out.

The full breakdown is stored with each analysis and shown in the UI.

**Remedies (`app/remedies`).** Each issue maps to an entry in the approved `remedies` catalogue:

- Problem
- Explanation
- Recommendation
- Priority
- Visual instruction

If no approved remedy exists, a clearly labelled "consult a practitioner" placeholder is shown instead. Nothing is generated freely. Findings keep a snapshot of their remedy, so old reports don't change when the catalogue does.

**Reports (`app/reports`).** The PDF follows a professional evaluation-report pattern. Its length depends on the property: the demo plan gives 15 pages, a three-room plan 9. Data flows in three steps, and only the first contains logic:

1. `report_data.build_report_data()` turns the stored analysis into a report model: property, assessment, scores, rooms (number, zone, direction, room score, result, introduction, considerations, recommendations), grouped findings, phased remedies, final summary and disclaimer. All wording is assembled from findings, rule explanations, the rule set's preferred zones and the remedy catalogue; no property text is hard-coded.
2. `plan_render.render_report_plan()` draws the verified geometry on the uploaded plan:
   - rooms shaded green/amber/red by result
   - numbered markers that match the tables
   - the 3×3 grid, clipped to the plan outline
   - the Brahmasthan and the main entrance
   - all eight directions at their true bearings
   
   With `highlight=` it draws the per-room thumbnail.
3. `pdf.build_pdf()` lays the model out with ReportLab. Room cards are kept whole on a page; short sections continue on the same page, and the header band always names the section at the top of the page.

**Report language (English / मराठी).** "Download PDF" asks for the language and sends `{"language": "en" | "mr"}` to `POST /projects/{id}/report` (no body = English, as before). The language is stored on the report row (migration `0003_report_language`) and only changes wording; the analysis, scores, findings and remedies are read, never recomputed.
- `reports/i18n.py` holds the wording. `EnglishTexts` reproduces the original English sentences exactly; `MarathiTexts` overrides them.
- `reports/locales/mr.json` translates the catalogue by code: rule finding templates, rule explanations, remedies and the rule-set name/disclaimer. Numbers inside a finding (shares, coverage, counts) are recovered from the stored sentence and re-used. When you add a rule or remedy, add its Marathi entry too; until you do, the Marathi report shows that item's English text and logs a warning.
- Standard room labels (Kitchen, Bedroom 2…) are shown in Marathi. Custom names stay as the user typed them. Room numbering is the same in both languages.
- Fonts: `reports/fonts/` has Noto Sans Devanagari Regular/Bold (SIL OFL), which covers both Devanagari and Latin. It is embedded as a subset in every Marathi PDF. Devanagari needs HarfBuzz shaping (`uharfbuzz` in requirements.txt). Without it, the Marathi job fails with a clear error instead of producing broken text, and it never falls back to English.

Report sections, in order:

1. Cover and executive summary
2. Property layout and directional assessment
3. Room-wise compliance overview, score breakdown and zone summary
4. Room-by-room analysis
5. Positive findings, warnings and major issues
6. Phase-wise remedial plan and remedy details
7. Evaluation summary
8. Disclaimer

Room results are a presentation of the rule outcome:

| Rule outcome | Result label |
|---|---|
| High-severity issue | Unfavourable |
| Other issue | Needs attention |
| Preferred | Highly auspicious |
| Acceptable | Auspicious |
| No matching rule | Not evaluated |

A room score is the room's own findings scored with the same points as the overall score.

Remedy phases come from the catalogue:

- **Phase:** an explicit `phase` on a remedy wins. Otherwise high priority is immediate, medium is short term, low or optional is medium term, and structural is long term.
- **Structural notes:** a remedy's `structural_note` is always a separate long-term item flagged for professional advice.

Set `REPORT_BRAND` to change the name printed on reports.

**Security.** Passwords are hashed with bcrypt and sessions use JWT bearer tokens. Every project, floor plan, report and job lookup checks ownership and returns 404 to anyone else. Uploads are checked in several ways:

- The file type is detected from its content, not the extension.
- Size and pixel limits are enforced, and the upload is read with a hard cap.
- EXIF data is stripped and images are re-encoded.

Storage is private and reached only through expiring signed URLs. Requests are rate-limited per IP, with a tighter limit on uploads. All errors come back as `{"error": {code, message, hint, details}}`.

## API

| Method | Path | |
|---|---|---|
| POST | `/auth/register`, `/auth/login` · GET `/auth/me` | |
| GET/POST | `/projects` · POST `/projects/demo` · GET/DELETE `/projects/{id}` | |
| POST | `/projects/{id}/floor-plan` | multipart upload, starts detection |
| POST | `/floor-plans/{id}/analyze` | (re)run AI detection |
| GET | `/floor-plans/{id}` · `/floor-plans/{id}/detection` · `/room-types` | |
| PUT | `/floor-plans/{id}/verification` | verified rooms and openings |
| PUT | `/floor-plans/{id}/north` | `{north_angle}` |
| POST | `/floor-plans/{id}/calculate-zones` · `/floor-plans/{id}/run-analysis` | |
| GET | `/projects/{id}/analysis` · `/findings?bucket=` · `/remedies` | |
| POST | `/projects/{id}/report` · GET `/projects/{id}/reports` · GET `/reports/{id}` | optional body `{"language": "en" \| "mr", "include_action_plan": true}` |
| GET/POST | `/jobs/{id}` · `/jobs/{id}/retry` | |
| GET/PUT | `/projects/{id}/insights/context` | FitCheck constraints, family profile, construction stage |
| GET | `/projects/{id}/insights/{summary,explain,passport,fitcheck,conflicts,family,stage,history,voice}` | `history/compare?old=&new=`, `voice?language=en\|mr` |
| GET/POST | `/floor-plans/{id}/checks` | AI Mistake Catcher (POST checks an unsaved draft) |
| GET/POST | `/projects/{id}/site-verifications` · POST `…/{sv_id}/apply` | Post-Move Verification |
| GET/POST | `/projects/{id}/expert-reviews` · POST `…/{review_id}/revoke` | Expert Review Handoff (token shown once) |
| GET/POST | `/expert-review/{token}` · `/expert-review/{token}/feedback` | Public, no login |
| POST | `/projects/{id}/video` · GET `/projects/{id}/videos` · GET `/videos/{id}` | `{"language": "en" \| "mr"}`; narrated MP4 + subtitles |
| GET | `/files/{key}?exp=&sig=` | signed local files |

## Customer insight tools

After an analysis, **Insights** offers eleven tools built on the verified analysis; none of them changes the official score or the PDF. See [CHECKLIST.md](CHECKLIST.md) for what each one does and where it lives. Migration `0004_customer_insights` adds the property context columns and the `site_verifications` / `expert_reviews` tables.

## Known limitations

- **Mock AI:** It returns the same layout (scaled) for any image. The vision analyzer is implemented but hasn't been tested against a range of real plans.
- **Unreviewed rules:** The rules and remedies are marked *approved* by the seed script but need review by a Vastu practitioner before real use.
- **Grid on a rotated bounding box:** The 3×3 grid is built on the North-aligned bounding box. When North is at an angle like 30°, a rectangular house shows "cut" corners. Some practitioners align the grid with the plot instead, so this needs an expert decision.
- **No outline editing:** The plan outline is derived from the rooms. There's no separate outline or plot editor.
- **Single floor only:** One floor per project and the 3×3 grid only. There are no 16/32 zones, 45 Devtas or furniture.
- **Dev-only infrastructure:** The rate limiter is in-memory (per process). Inline jobs don't survive a restart, so use Celery in production.
- **Token storage:** The login token is kept in `localStorage`, not an httpOnly cookie.
- **Shorter room write-ups than consultant reports:** Room introductions are factual and drawn from the rule set; they don't include zone lore (elements, deities, planets) because the rule set has no such data. Adding per-zone descriptions to the rule-set data would enrich them without hard-coding text.
- **No expected-benefits section:** The remedy catalogue has no outcome data, so the report doesn't predict improvements or a "score after remedies".
- **Stale analysis:** Re-verifying a plan or changing North makes the old analysis stale. The UI warns and asks you to re-run, but old room links in that analysis may no longer match the new rooms.

## Next steps

1. Expert review of `rules.json` / `remedies.json`, and an admin screen for editing rules and remedies with a draft → approved workflow.
2. Evaluate the vision analyzer on 50–100 real plans. Measure room-detection and entrance accuracy, then tune the prompt or add a dedicated segmentation model behind the same interface.
3. Plot and building outline editing, and grid alignment options.
4. 16-zone system (new `ZoneSystem` class plus rules keyed to it).
5. httpOnly cookie sessions, Redis-backed rate limiting, audit log, and email verification.
6. Multi-floor projects and report branding.
