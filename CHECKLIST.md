# Customer features checklist (वैशिष्ट्यांची यादी)

All 11 items are built, wired into the UI, and covered by backend tests (`backend/tests/test_insights.py`).
In the app: open a project after the analysis, then go to **Insights** (top-right of the step bar, or the button on the Analysis page).
None of these tools changes the official score or the PDF report. Where a tool shows a different number (family view, "as built" score,
±10° North range, "what-if" gains), it is labelled as a simulation.

## 1. Existing project improvements (सध्याच्या प्रकल्पातील सुधारणा)

- [x] **Vastu FitCheck (Vastu Feasibility Checker)**: घराची परिस्थिती, बजेट आणि बदल करण्याच्या मर्यादेनुसार व्यवहार्य उपाय सुचवणे.
  - Household inputs: owned / rented / being bought, budget, disruption limit, civil work allowed, plumbing/electrical allowed, renovation planned, housing-society limits.
  - Each issue shows the everyday option and the structural option with a verdict (Fits / Needs approval / Outside your limits) and the reasons.
  - Construction stage lowers the cost of early structural work. Tenants get an "owner's permission" condition.
  - Backend: `app/insights/fitcheck.py`, practical metadata per remedy in `app/insights/data/remedy_fit.json`. UI: Insights → Vastu FitCheck.
- [x] **Vastu Trust & Accuracy Passport**: उत्तर दिशा, Room Detection, वापरकर्त्याने केलेल्या दुरुस्त्या आणि विश्लेषणातील अनिश्चितता दाखवणे.
  - North: angle, when it was confirmed, whether it is just the image top, and the on-site compass check (from Post-Move Verification).
  - Detection: rooms kept as the AI drew them, corrected, added by hand, removed; average AI confidence; unreviewed low-confidence rooms.
  - Uncertainty: score range if North is off by ±10°, rooms that would change zone, rooms across two zones, unscored rooms, remedies without an approved entry, rule set pending expert review.
  - Overall level: High / Medium / Low, with the reasons. Backend: `app/insights/passport.py`.
- [x] **AI Mistake Catcher**: चुकीचे Room Detection, अपूर्ण आराखडा आणि संशयास्पद दिशा ओळखणे.
  - Checks: unnamed/"Other" rooms, name vs type mismatch, unreviewed low-confidence AI rooms and entrance, overlapping rooms, tiny or huge rooms, rooms outside the outline, part of the plan with no room, missing kitchen/toilet in a home, stairs detected but missing, several master bedrooms, missing / several / inside main entrance, no windows, door off every wall, North unconfirmed or exactly the image top.
  - Runs live in the Verify editor (debounced, click a check to select the room or door), on the AI detection before verification, and in the Trust Passport. Backend: `app/insights/mistakes.py`. UI: `features/verify/MistakeCatcher.tsx`.
- [x] **Explain the Score**: Vastu Score, लागू केलेले नियम आणि गुणांवर परिणाम करणारे घटक समजावून सांगणे.
  - Step-by-step method, each category's share of the final number (adds up to the exact score), every finding's weight × points, points lost, rules applied out of the rule set, and the findings that pull the score down most with the gain if each rule passed. Backend: `app/insights/explain.py`.
- [x] **Vastu Change History**: आराखड्याच्या वेगवेगळ्या आवृत्त्यांचे स्कोअर आणि निष्कर्ष तुलना करणे.
  - Every analysis run is a version (score chart + table). Compare any two: score and category deltas, findings improved / worse / resolved / new, rooms that changed zone or type, added or removed rooms, North change.
  - Built only from what each analysis stored, so old versions still compare correctly after the plan is edited. Backend: `app/insights/history.py`.

## 2. New customer-focused features (ग्राहक-केंद्रित नवीन वैशिष्ट्ये)

- [x] **Vastu vs Daily-Life Conflict Detector**: वास्तू उपायांमुळे जागेचा वापर किंवा ये-जा करण्यात संभाव्य अडचणी निर्माण होतात का ते तपासणे.
  - Checks each remedy against the room's geometry: furniture placed where a door opens, heavy furniture in front of a window, a room too narrow for the bed or table (when the built-up area is known), "keep the centre open" where the dining table or bed normally goes, and a toilet kept closed with no window.
  - Also lists what a structural option means for daily life. Plan view highlights the affected rooms. Backend: `app/insights/daily_life.py`.
- [x] **Family Priority Mode**: ग्राहकाच्या गरजांनुसार महत्त्वाच्या खोल्यांचे विश्लेषण सानुकूलित करणे.
  - Choose household members (elderly parents, young children, students, work from home, couple, cooks daily, daily worship) and goals (sleep, study, work, kitchen, worship, entrance, open home), or set priority per room.
  - Shows a "family view" score (priority rooms ×2, low ×0.5) next to the unchanged official score, a re-ordered action list and notes per member. Config: `app/insights/data/family.json`.
- [x] **Construction Stage Assistant**: घराच्या बांधकामाच्या टप्प्यानुसार सूचना देणे.
  - Six stages: planning, foundation, walls/structure, plumbing & electrical, finishing, living in.
  - Sorts each remedy into **Act now** (cheap now, expensive after a named stage), **Any time**, or **Costly at this stage**, plus a site checklist for the stage filtered to this plan. Config: `app/insights/data/stages.json`.
- [x] **Post-Move Verification**: प्रत्यक्ष घरातील बदलांची आराखड्याशी पडताळणी करणे.
  - Record a compass reading (typed, or from the phone compass), whether the main entrance is the one on the plan, how each room is actually used or whether it exists, remedy progress and notes.
  - Result: differences, a simulated "as built" score, remedy % done, and **Apply to the plan and re-run** (as-built room types, optionally the site North). The old result stays in Change History. The compass check also feeds the Trust Passport.
- [x] **Expert Review Handoff**: वास्तुविशारद आणि वास्तू सल्लागारांसाठी तपासणी रिपोर्ट तयार करणे.
  - Creates an expiring, unguessable link (shown once, only its hash is stored, can be revoked) to a public review page: plan with zones, every finding with rule and remedy, Trust Passport, open plan checks, household constraints and auto-generated questions for the expert.
  - The expert agrees or disagrees per finding, comments, confirms North, gives a verdict and signs. The reply appears in the project and never changes the analysis by itself. Contact details are shared only if you tick the box.
- [x] **Voice Report Explainer**: रिपोर्टचा सोपा मराठी आणि इंग्रजी ऑडिओ सारांश देणे.
  - Short plain-language script in मराठी or English, built from the analysis with the same Marathi catalogue translations as the Marathi PDF.
  - Played by the browser's speech engine (mr-IN / en-IN) with play, pause, stop, speed and play-from-section. Nothing is uploaded. Download as text. Tells the user when no Marathi voice is installed.

## 3. Report upgrades (अहवालातील सुधारणा)

- [x] **Personal action plan in the PDF** (वैयक्तिक कृती योजना), English and मराठी. A new section before the evaluation summary:
  - Always: what moves the score most (+points if each issue were resolved, and the highest reachable score) and how reliable the result is (Trust Passport level and reasons).
  - Only when set up in Insights: remedies that fit the customer's situation (FitCheck), what to do before it gets expensive at their construction stage plus the site checklist, and their family's priority order.
  - Optional: "Include personal action plan" checkbox in the Download PDF dialog (on by default). Builder: `app/reports/action_plan.py`; layout: `_action_plan_section` in `app/reports/pdf.py`.
- [x] **Video report** (व्हिडिओ अहवाल): a narrated walkthrough of the customer's own report, about 5 to 8 minutes, in मराठी or English. Report page → Video report.
  - Scenes: title card with score, how the plan was read (annotated plan), overall score with category bars, what moves the score, rooms at a glance, one scene per room that needs care (that room highlighted on the plan), well-placed rooms, entrance/zones/windows, remedies by phase, the personal action plan scenes, reliability, next steps.
  - Every sentence comes from the stored analysis and the same catalogue translations as the PDF, so the video never says anything the report doesn't.
  - Voice: free Microsoft neural voices through `edge-tts` (mr-IN-AarohiNeural, en-IN-NeerjaNeural; needs internet). If no voice is reachable, the video is made with on-screen captions only and the page says so.
  - Captions are drawn on screen (works muted, e.g. WhatsApp autoplay) and also included as soft subtitles plus a downloadable .srt.
  - Player with chapters, Download MP4, Share (phone share sheet → WhatsApp), retry on failure. Files: `app/videos/` (script, slides, tts, compose, service), `app/api/videos.py`, `frontend/features/report/VideoReport.tsx`.
- [x] **Fixed: Marathi headings in the PDF.** Section headers, footer and cover text drawn directly on the page put the ि vowel sign in the wrong place and broke conjuncts (e.g. "वैयक्तकि"). They are now shaped the same way as body text.

## What changed

**Backend**
- New package `app/insights/` (one module per tool + `data/*.json` configs), router `app/api/insights.py`.
- Models: `Property.fit_constraints`, `Property.family_profile`, `Property.construction_stage`; new tables `site_verifications`, `expert_reviews` (`app/models/insights.py`). Migration `alembic/versions/0004_customer_insights.py`. Local SQLite dev databases pick up the new columns automatically on start.
- `services/pipeline.py`: `load_rule_context()` split out of `run_analysis()` so tools can re-run the engines in memory; the analysis snapshot now also stores room/opening source and confidence, the North confirmation time and the detector.
- Tests: `tests/test_insights.py` (13 tests), `tests/test_video_and_action_plan.py` (6 tests). Full suite: 68 passed.
- Migration `0005_action_plan_and_video`: `reports.options` and the `report_videos` table.
- New requirements: `imageio-ffmpeg` (bundled ffmpeg, also on Windows) and `edge-tts`. Run `pip install -r requirements.txt` again.

**Frontend**
- `features/insights/*` (one component per tool), `types/insights.ts`, new API calls in `services/api.ts`.
- Routes: `/projects/[id]/insights` (overview) and `/projects/[id]/insights/[tool]`; public `/review/[token]`.
- Verify page: live AI Mistake Catcher panel. Step bar: Insights link. Analysis page: Insights button and quick links. Header fits phone width.

## How to try it
1. `cd backend && pip install -r requirements-dev.txt && uvicorn app.main:app --reload` (if you use PostgreSQL, run `alembic upgrade head` first).
2. `cd frontend && npm install && npm run dev`.
3. Sign in as demo@example.com / demo12345, open **Demo Residence** → **Insights**.
4. Tests: `cd backend && python -m pytest -q`.

## Video settings (backend/.env)
| Variable | Default | |
|---|---|---|
| `VIDEO_TTS` | `auto` | `auto` (edge, then gTTS, then captions only), `edge`, `gtts`, `silent` |
| `VIDEO_VOICE_MR` / `VIDEO_VOICE_EN` | `mr-IN-AarohiNeural` / `en-IN-NeerjaNeural` | e.g. `mr-IN-ManoharNeural` for a male Marathi voice |
| `VIDEO_VOICE_RATE` | `-4%` | speaking speed |
| `VIDEO_BURN_CAPTIONS` | `true` | captions drawn on the video |

## Known limits
- Daily-life checks use door and window positions only; door swing and furniture sizes are not drawn, so results are prompts to measure on site.
- Remedy cost bands and requirements (`remedy_fit.json`), stage rules and family mappings are starter data like the rule set; a practitioner should review them.
- Voice quality depends on the voices installed on the device; Marathi needs a mr-IN voice (Android: Google Text-to-speech).
- The video voice needs internet on the server (edge-tts). It was built and tested here in captions-only mode because this build machine has no internet; run it once on your machine to hear the voice.
- Video length follows the plan: more rooms needing care means more scenes.
- The phone-compass button needs a device with a compass and, on iPhone, permission; typing a compass-app reading always works.
