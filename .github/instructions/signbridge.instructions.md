---
applyTo: |
  BACKEND/**/*.py
  FRONTEND/**/*.py
  run.py
  client/src/**/*.{js,jsx,ts,tsx}
  client/*.json
---

# SignBridge repository instructions

## Project structure
- Keep the app split into three layers:
  - `BACKEND/` for Python business logic, database access, AI features, and shared ML/tts utilities.
  - `FRONTEND/` for the FastAPI web app and HTML-rendered portal routes.
  - `client/` for the React + Vite frontend experience.
- Treat `run.py` as the local startup entry point; do not move or duplicate server bootstrap logic into the React app.
- Preserve the repo’s import pattern: backend modules are loaded via `sys.path` adjustments and are not expected to be packaged as a full Python package.

## Coding expectations
- Favor small, explicit changes that match the existing code style and naming patterns.
- Prefer FastAPI/Pydantic patterns already used in `FRONTEND/main.py` for request validation, routes, and HTML responses.
- Keep accessibility and inclusion goals in mind: the product supports both blind and deaf learner flows, so route names, messages, and UI content should remain clear and role-aware.
- When changing a feature, preserve the existing user-facing behavior for both roles unless the task specifically asks for a new flow.

## Backend rules
- Use Python functions and route handlers that are easy to trace from the HTTP layer to the database/AI logic.
- Keep database helpers, authentication, lesson generation, quiz generation, and TTS/AI integrations in their current backend modules instead of scattering them across route files.
- If a new API endpoint is added, align it with the existing FastAPI route conventions and Pydantic payloads already used in the app.

## Frontend rules
- For React code under `client/src`, keep the app component-driven and Vite-friendly.
- Prefer minimal, maintainable UI changes that fit the current styling patterns and do not rewrite the app structure unnecessarily.
- When wiring API calls, follow the existing backend URL conventions and avoid introducing a second, inconsistent API layer.

## Validation before completion
- Before declaring a fix complete, verify the changed behavior with the smallest relevant check available:
  - run the relevant Python startup or route-level validation for backend changes,
  - run the Vite build or lint check for frontend changes when applicable,
  - ensure imports and startup paths still work under the repo’s current structure.
- Do not claim a task is complete if the change has not been checked against the local project setup.

## Change management
- Keep edits scoped to the problem at hand.
- Do not refactor unrelated modules or re-architect the project structure without a clear need.
- Preserve compatibility with the existing `BACKEND`, `FRONTEND`, and `client` separation unless the task explicitly requires integrating them.
