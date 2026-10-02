# SignBridge Accessibility Modernization

## Goal
Provide three direct-entry learning pathways without requiring registration, while preserving learner history and routing sign gestures into accessible lessons.

## Task Breakdown

### 1. Anonymous profile and SQLite compatibility
- [x] Make profile creation passwordless while satisfying legacy `NOT NULL` hash and salt columns.
- [x] Migrate legacy `users.role` checks from `blind`/`deaf` to `blind`/`deaf`/`sign`/`non_speaking`, preserving existing rows and progress.
- [x] Verify initialization is repeatable against the migrated database.
- Acceptance: a first-time learner can open any pathway, and existing profile/history rows remain readable after startup migration.

### 2. React direct-entry experience
- [x] Replace the login/register gate in `client/src/App.jsx` with a mode selector and optional display name.
- [x] Persist anonymous mode selection through `POST /api/profile`, load learner history, and support changing pathways without a password or session cookie.
- [x] Add topic generation and quiz flows for all modes using the existing `/api` routes.
- Acceptance: the first screen offers Deaf, Blind, and Sign / Non-Speaking modes and no authentication form.

### 3. Mode-specific accessible learning flows
- [x] Deaf: present generated content as readable visual modules and keep quiz actions/results visible.
- [x] Blind: provide speech start, pause/resume, and stop controls, with companion/mentor-friendly prompts and keyboard-accessible buttons.
- [x] Sign / Non-Speaking: provide camera start/stop, recognition status, confidence, a lesson result, and a typed-topic fallback.
- Acceptance: each pathway has distinct interaction and presentation without blocking access to generated text.

### 4. Sign inference and local Ollama lesson integration
- [x] Reuse MediaPipe Hand Landmarker in the browser to produce 21 normalized hand landmarks.
- [x] Add `POST /api/sign/lesson`: classify landmarks with `analyze_landmarks`, select a catalog topic, generate a sign-mode lesson with Ollama, and save it to the anonymous profile.
- [ ] Verify camera permission denial, no-hand detection, and successful landmark submission in a browser.
- [ ] Evaluate the limited gesture catalog against representative users and improve confidence/confirmation handling.
- Acceptance: a supported handshape produces a named catalog gesture and associated lesson; missing/unsupported landmarks return a clear validation error.

### 5. Verification and production readiness
- [x] Run Python compilation and FastAPI route checks, including migration repeatability and sign-profile creation.
- [x] Run `npm run build` and `npm run lint` in `client/`.
- [ ] Exercise all mode entry points, lesson and quiz generation, history persistence, camera lifecycle, and narrow/mobile layouts.
- [ ] Before production sign-language claims, replace or supplement handshape heuristics with a validated, language-specific temporal sign model and representative consented data.

## Current Inference Boundary
The browser performs camera capture and MediaPipe hand-landmark extraction. The backend currently uses a small rule-based landmark classifier over a fixed catalog; this is a useful gesture-to-topic prototype, not general sign-language translation. Lesson and quiz text is generated locally by Ollama using `OLLAMA_MODEL` (default `qwen2.5:3b`). Full language recognition needs a temporal model, language/dialect definition, representative evaluation data, and explicit user confirmation for uncertain predictions.

## Validation Snapshot
- Python compilation passed for the changed backend modules.
- FastAPI smoke passed for direct landing, anonymous profile selection, landmark-to-lesson generation, history persistence, no-hand rejection, and removed `/login` route.
- Client production build and oxlint passed.
- Browser confirmed the direct mode chooser, sign screen, typed-topic API proxy, and cancellable camera setup; physical-device hand inference remains unverified.
- Local Ollama lesson generation, quiz generation, and live FastAPI `/api/generate` passed with the installed `qwen2.5:3b` model.
