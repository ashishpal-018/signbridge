# Air-Writing / Finger-Tracking Blueprint

## User Flow
1. Learner selects **Sign / air-writing mode** without authentication.
2. Learner starts tracking and grants webcam permission.
3. MediaPipe Hands identifies one hand; the UI samples index fingertip landmark 8 and draws its path over the mirrored video.
4. A 1.2-second pause finalizes the current stroke. The learner can also stop tracking, clear the canvas, or explicitly request recognition.
5. Tesseract.js OCR proposes editable English text from the stroke. The learner reviews or corrects the topic before submission.
6. React sends `{ username, topic }` to `POST /api/air-writing-lesson`.
7. FastAPI validates the topic, calls the sign-mode Groq lesson generator, stores the lesson in anonymous history, and returns `{ username, topic, lesson }`.

## Implementation Tasks

### Browser capture and drawing
- [x] Add `AirWriter.jsx` as an isolated React component.
- [x] Lazy-load version-pinned `@mediapipe/hands` and `@mediapipe/camera_utils` CDN globals when tracking begins.
- [x] Draw landmark 8 onto a transparent HTML canvas, mirrored to match the selfie video.
- [x] Preserve strokes on hand loss, finalize on pause, and expose start/cancel/stop/clear actions.
- [x] Stop camera, close Hands, clear timers, and terminate OCR worker on unmount.

### Text recognition and topic correction
- [x] Install Tesseract.js and crop/upscale/threshold the written path before English OCR.
- [x] Show OCR output in an editable topic field and require explicit lesson generation.
- [x] Retain manual text entry when OCR is uncertain or fails.
- [ ] Validate OCR accuracy across letters, spacing, writing directions, cameras, and lighting.

### API and lesson generation
- [x] Add `POST /api/air-writing-lesson` with username and topic fields.
- [x] Reject blank topics and topics longer than 120 characters.
- [x] Generate through the Groq-backed `generate_lesson(..., mode="sign")` service.
- [x] Save generated lessons to the learner's anonymous history.

### Verification and release
- [x] Build and lint the React client.
- [ ] Run a FastAPI test for successful topic generation, blank input, overlong input, and profile/history persistence.
- [ ] Test on a physical webcam with camera-denied, camera-unavailable, no-hand, pause, clear, OCR, and submit flows.
- [ ] Evaluate performance and accessibility on supported desktop and mobile browsers.

## Limitations
This feature recognizes an air-written English word through OCR; MediaPipe only tracks the fingertip and does not recognize language itself. Handwriting quality, camera perspective, and motion blur can reduce OCR accuracy, so learners can edit the proposed topic before requesting a lesson. Lesson generation uses the project's Groq configuration (`GROQ_API_KEY`, `GROQ_MODEL`).
