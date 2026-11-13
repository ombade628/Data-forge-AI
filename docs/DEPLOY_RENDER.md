# Deploying the free DataForge demo on Render

This configuration deploys a portfolio/demo version with no paid LLM API. It uses the project's local prompt-analysis and synthetic-data provider.

## What the Blueprint creates

- `dataforge-web`: a free Render Static Site hosting the Next.js UI.
- `dataforge-api`: a free Render Web Service hosting FastAPI.
- `dataforge-db`: a free Render Postgres database.

The API uses inline jobs instead of Celery because Render does not offer free background workers. Keep demos small (around 10–100 records) so a request completes before the free web-service timeout.

## Deploy

1. Push this repository to a GitHub repository. Never commit `.env`.
2. In Render, select **New** → **Blueprint** and authorize GitHub.
3. Select the repository and confirm `render.yaml`.
4. Click **Apply**. Render creates the database and both public services.
5. Open the `dataforge-web` URL after both deploys complete.
6. Register a new user, analyze a prompt, then generate a small dataset.

The Blueprint generates `JWT_SECRET_KEY`, connects the API to the database privately, sends the API URL into the static-site build, and permits requests from only the generated frontend URL.

## Free-tier limits

- The API sleeps after 15 minutes without traffic; its first later request can take about a minute.
- Free Render Postgres expires after 30 days. Export any demo data before expiration.
- The API filesystem is temporary. Users should download exports immediately; do not treat it as long-term file storage.
- There is no Redis/Celery worker in this free architecture.

## When adding a real LLM

Add its secret key in Render's API service environment settings, create a provider adapter under `backend/app/ai/providers`, and change `LLM_PROVIDER`. This is optional and should happen only when you have a provider account/budget.
