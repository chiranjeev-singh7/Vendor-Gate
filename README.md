# VendorGate

Vendor onboarding review with a FastAPI API, SQLite audit history, deterministic checks, and a single-page browser interface. The pipeline runs without an LLM key. The current implementation uses demo sanctions data and should be treated as a case-study application.

## Local run

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. Set `STAGE_DELAY_MS` to adjust the SSE display delay. SQLite data is stored in `vendorgate.db`.

## UI overview

The browser app uses a responsive, light operations workspace with sample-first vendor submission, a form and advanced JSON editor, and a live SSE verification stepper. The dashboard summarizes decisions with inline SVG charts, search/filter/sort, and a run-details drawer with resubmission comparisons. The Rules page explains the deterministic decision policy. Use **Reset demo data** to clear run history and restore the seeded vendor master before repeating the demo.

## Demo

Choose a sample and select **Run process**. **Run all samples** pre-populates the dashboard. Each run saves stage evidence, output messages, and a decision trace. See [DEMO_SCRIPT.md](DEMO_SCRIPT.md).

## Deploy to Render

This repository includes a Render Blueprint in `render.yaml`. Push the project to GitHub, then in Render choose **New > Blueprint**, connect the repository and deploy the Blueprint. It creates a free Docker web service, checks `/health`, and enables sample auto-seeding. The Docker command listens on Render's `PORT` value. The service URL is shown on the Render dashboard after the deploy completes.

## Deploying on Render free tier

The free web service filesystem is ephemeral: SQLite history can reset when the service is restarted or redeployed. Enable `VENDORGATE_AUTOSEED=true` in the Render environment to repopulate the dashboard with sample runs after a reset. Auto-seeding runs only when the runs table is empty and does not add duplicate sample runs to a non-empty history. Use a paid persistent disk/service plan if you need durable vendor and audit history; auto-seed is demo data, not a backup.

The seeded set includes the six original cases, the corrected resubmission, and the contact-domain warning case. Turn auto-seed off by removing the environment variable or setting it to `false`.

## API

- `GET /health`
- `GET /api/samples`, `GET /api/runs`, `GET /api/runs/{id}`
- `POST /api/runs` with a JSON submission
- `POST /api/upload` with JSON file
- `POST /api/run-samples`
- `GET /api/runs/{id}/events` for stage event streaming

## Checks

```powershell
pytest
```

## Browser verification

Install the development dependencies and Chromium in the active virtual environment before running the local Playwright check:

```powershell
pip install -r requirements-dev.txt
python -m playwright install chromium
python verification\live_run_consistency.py
```
