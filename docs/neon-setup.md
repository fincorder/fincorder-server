# Neon database and profile-image storage

## Database connection

The backend and Alembic use one connection setting. Put the connection string for the intended Neon branch in the backend's ignored `.env.local`:

```dotenv
DATABASE_URL="postgresql://<user>:<password>@<host>/<database>?sslmode=require"
```

Use the direct connection string from Neon for migrations. The same setting is used by the application; if its hostname contains `-pooler.`, the backend enables a pooler-compatible SQLAlchemy configuration. A local PostgreSQL database can also use this same setting. PostgreSQL URLs are normalized to `postgresql+asyncpg`, and the unsupported `channel_binding` parameter is removed while TLS settings are retained.

## Profile-image storage

Create an S3-compatible bucket in Neon Object Storage and set the storage values in `.env.local`:

```dotenv
AWS_ENDPOINT_URL_S3="<Neon Object Storage endpoint>"
AWS_ACCESS_KEY_ID="<storage access key>"
AWS_SECRET_ACCESS_KEY="<storage secret key>"
AWS_REGION="<bucket region>"
S3_BUCKET="<bucket name>"
S3_AVATAR_URL_EXPIRY_SECONDS=604800
```

The bucket can remain private. The API accepts JPEG, PNG, and WebP profile images up to 5 MB, uploads the bytes to object storage, and saves only the object's key in `users.avatar_key`. Auth responses include a time-limited signed `avatar_url`; replaced and removed images are deleted from storage. Do not store image bytes or expiring signed URLs in PostgreSQL.

## Apply the schema

After setting the rotated Neon connection string:

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
```

This upgrades the schema; it does not copy rows from a local database. Import local records separately only after confirming the target Neon branch and deciding that existing data should be transferred.

## Credential hygiene

Never commit `.env.local` or paste connection strings and storage secrets into source code. `.env.example` contains placeholders only. A database credential was previously exposed in a tracked example and credentials appeared in a configuration error; rotate the database password and any storage keys that may have been exposed before connecting.
