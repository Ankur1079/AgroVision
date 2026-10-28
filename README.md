# AgroVision â€” precision farming platform

A real-data-first starter for the AgroVision project requirements. It implements account registration/login, PostgreSQL-backed farm records and farming workflows, role-based admin and advisor endpoints, advisory requests and recommendations, audit logging, and dashboard counts calculated from authenticated users' stored records. It intentionally creates no sample farm, sales, weather, or AI records.

## Stack
- Frontend: React + TypeScript + Vite + Lucide
- API: FastAPI + SQLAlchemy + Pydantic
- Database: PostgreSQL
- Authentication: password hashing with Argon2 and signed JWT access tokens

## Prerequisites
- Python 3.11+
- Node.js 20.19+ or 22.12+
- Docker Desktop with its Linux engine running, or a reachable PostgreSQL 17 instance

## 1. Start PostgreSQL
From the repository root:

```bash
docker compose up -d db
```

Check it:

```bash
docker compose ps
```

## 2. Configure and start API

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux instead: source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env  # Windows PowerShell; on macOS/Linux: cp .env.example .env
```

Edit `backend/.env` and set `DATABASE_URL` to your local database and `JWT_SECRET` to a long random secret. For the local Compose defaults, use:

```env
DATABASE_URL=postgresql+psycopg://agrovision:local-only-change-me@localhost:5434/agrovision
JWT_SECRET=replace-this-with-a-long-random-local-secret
JWT_EXP_MINUTES=60
CORS_ORIGINS=http://localhost:5173
```

Run from `backend/`:

```bash
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs and http://localhost:8000/health.

## 3. Start frontend
Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Register with your own email and a password of at least 10 characters. Sign in, then add actual farm information. The dashboard should show zero counts until you add records.

## Download PlantVillage for ML
The PlantVillage downloader uses the dataset's legacy Hugging Face loader. From `ml/`, install its pinned dependency and run the downloader:

```bash
python -m pip install -r requirements.txt
python download_plantvillage.py
```

The real color dataset is about 2 GB. A Hugging Face token is optional, but can improve download limits.

## 4. Verify real persistence
1. Register and sign in.
2. Add a farm with a real name/location/area from a farm you are authorized to record.
3. Refresh the page: the farm and counts should remain.
4. Register a second account in a private/incognito window: it must not see the first account's farms.
5. Visit `/docs` and exercise field, crop-cycle and task endpoints using the bearer token.

## Current API routes
- `GET /health`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login` (OAuth2 form: username=email, password=password)
- `GET /api/v1/auth/me`
- `GET|POST /api/v1/farms`
- `GET|POST /api/v1/farms/{farm_id}/fields`
- `GET|POST /api/v1/fields/{field_id}/crop-cycles`
- `GET|POST /api/v1/crop-cycles/{cycle_id}/tasks`
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/admin/summary`
- `GET /api/v1/admin/users`
- `PATCH /api/v1/admin/users/{user_id}/role`
- `POST /api/v1/admin/farms/{farm_id}/advisor`
- `GET /api/v1/admin/audit-logs`
- `GET|POST /api/v1/advisory/requests`
- `GET /api/v1/advisory/requests/{request_id}/recommendations`
- `GET /api/v1/advisor/farms`
- `GET /api/v1/advisor/requests`
- `PATCH /api/v1/advisor/requests/{request_id}/status`
- `POST /api/v1/advisor/requests/{request_id}/recommendations`

## Important engineering status
This is a development starter, not yet a production deployment. Run `alembic upgrade head` from `backend/` to apply the advisory-field migration; the API still uses SQLAlchemy `create_all` on startup for local development. Add rate limiting, email verification/password reset, token revocation, secure production CORS, upload storage, and comprehensive tests before real public use. Do not deploy with the example JWT secret or database password.

## No synthetic records policy
The application does not seed demo records. Farm, field, crop-cycle and task records must be entered from real information. Weather, market price and crop-health modules are explicitly shown as not connected until their real integrations are implemented. Do not present screenshots of empty states as evidence of live external integrations.
