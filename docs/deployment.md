# Deployment configuration

## Backend (Vercel or Render)

The FastAPI app is exported from `app/main.py`, which Vercel recognizes as an application entrypoint. Keep the Vercel project root at the backend repository root. It installs Python dependencies from `requirements.txt`; no build command or `pyproject.toml` is needed. `.python-version` pins the runtime to Python 3.12.

For Vercel, add the environment variables below under Project Settings → Environment Variables. Vercel does not run Alembic migrations automatically; the current Neon database is already migrated, and future revisions must be applied deliberately before deploying code that requires them.

Alternatively, the Render blueprint runs `pip install -r requirements.txt`, applies Alembic migrations, and starts FastAPI. Set these values in the Render service environment:

- `DATABASE_URL`: Neon direct connection URL for the production branch; used by both the API and Alembic.
- `CORS_ORIGINS`: exact frontend origins, comma-separated, without trailing slashes (for example `https://your-app.vercel.app`). Add any custom domain separately.
- `AWS_ENDPOINT_URL_S3`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, and `S3_BUCKET`: Neon Object Storage connection details.
- `AI_PROVIDER`, `OPENAI_API_KEY`, and `OPENAI_MODEL`: required for capture. Keep provider secrets in Render's environment settings.

The profile-image bucket can be private; the API returns signed image URLs. Render redeploys run `alembic upgrade head`, which is safe after a migration has already reached head.

## Frontend (Vercel)

Import the `fincorder-client` directory as the Vercel project and set:

```dotenv
VITE_API_URL=https://<your-backend-host>
```

The Vite app builds with `npm run build`. The `vercel.json` SPA rewrite keeps React Router pages working on direct navigation and refresh. After deployment, add the final Vercel origin to the backend's `CORS_ORIGINS`, then redeploy the backend if needed.

Do not put database or storage credentials in Vercel frontend variables; Vite exposes `VITE_*` values in the browser bundle.
