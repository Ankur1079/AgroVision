import os
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from app.farm_modules import router as farm_modules_router
from app.module_j import router as module_j_router
import httpx
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    UploadFile,
    File,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.config import settings
from app.database import Base, engine, get_db
from app import models, schemas
from app.security import (
    create_access_token,
    get_current_user,
    hash_password,
    require_roles,
    verify_password,
)

# Bootstrap convenience for the first local milestone. Replace with Alembic-managed
# migrations before production deployment.
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(farm_modules_router)
app.include_router(module_j_router)
_upload_root = Path(os.getenv("AGROVISION_UPLOAD_DIR", "uploads/crop-photos")).parent
_upload_root.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_upload_root)), name="uploads")

@app.get("/health")
def health():
    return {"status": "ok", "service": "agrovision-api"}

@app.post("/api/v1/auth/register", response_model=schemas.UserOut, status_code=201)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.scalar(select(models.User).where(models.User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = models.User(email=email, full_name=payload.full_name.strip(), password_hash=hash_password(payload.password), role="farmer")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@app.post("/api/v1/auth/login", response_model=schemas.TokenOut)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(models.User).where(
            models.User.email == form.username.lower()
        )
    )

    if not user or not verify_password(
        form.password, user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="This account has been deactivated",
        )

    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
    }

@app.get("/api/v1/auth/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user

@app.get("/api/v1/farms", response_model=list[schemas.FarmOut])
def list_farms(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.scalars(select(models.Farm).where(models.Farm.owner_id == user.id).order_by(models.Farm.created_at.desc())).all()

@app.post("/api/v1/farms", response_model=schemas.FarmOut, status_code=201)
def create_farm(payload: schemas.FarmCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    farm = models.Farm(owner_id=user.id, **payload.model_dump())
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return farm

@app.get("/api/v1/farms/{farm_id}/fields", response_model=list[schemas.FieldOut])
def list_fields(farm_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    farm = db.scalar(select(models.Farm).where(models.Farm.id == farm_id, models.Farm.owner_id == user.id))
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    return db.scalars(select(models.Field).where(models.Field.farm_id == farm_id).order_by(models.Field.id)).all()

@app.post("/api/v1/farms/{farm_id}/fields", response_model=schemas.FieldOut, status_code=201)
def create_field(farm_id: int, payload: schemas.FieldCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    farm = db.scalar(select(models.Farm).where(models.Farm.id == farm_id, models.Farm.owner_id == user.id))
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    field = models.Field(farm_id=farm_id, **payload.model_dump())
    db.add(field)
    db.commit()
    db.refresh(field)
    return field

@app.get("/api/v1/fields/{field_id}/crop-cycles", response_model=list[schemas.CropCycleOut])
def list_crop_cycles(field_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    field = db.scalar(select(models.Field).join(models.Farm).where(models.Field.id == field_id, models.Farm.owner_id == user.id))
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    return db.scalars(select(models.CropCycle).where(models.CropCycle.field_id == field_id).order_by(models.CropCycle.planting_date.desc())).all()

@app.post("/api/v1/fields/{field_id}/crop-cycles", response_model=schemas.CropCycleOut, status_code=201)
def create_crop_cycle(field_id: int, payload: schemas.CropCycleCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    field = db.scalar(select(models.Field).join(models.Farm).where(models.Field.id == field_id, models.Farm.owner_id == user.id))
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    cycle = models.CropCycle(field_id=field_id, **payload.model_dump())
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle

@app.get("/api/v1/crop-cycles/{cycle_id}/tasks", response_model=list[schemas.TaskOut])
def list_tasks(cycle_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    cycle = db.scalar(select(models.CropCycle).join(models.Field).join(models.Farm).where(models.CropCycle.id == cycle_id, models.Farm.owner_id == user.id))
    if not cycle:
        raise HTTPException(status_code=404, detail="Crop cycle not found")
    return db.scalars(select(models.FarmTask).where(models.FarmTask.crop_cycle_id == cycle_id).order_by(models.FarmTask.due_date)).all()

@app.post("/api/v1/crop-cycles/{cycle_id}/tasks", response_model=schemas.TaskOut, status_code=201)
def create_task(cycle_id: int, payload: schemas.TaskCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    cycle = db.scalar(select(models.CropCycle).join(models.Field).join(models.Farm).where(models.CropCycle.id == cycle_id, models.Farm.owner_id == user.id))
    if not cycle:
        raise HTTPException(status_code=404, detail="Crop cycle not found")
    task = models.FarmTask(crop_cycle_id=cycle_id, **payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


@app.get("/api/v1/farms/{farm_id}/weather")
def get_farm_weather(
    farm_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    farm = db.scalar(
        select(models.Farm).where(
            models.Farm.id == farm_id,
            models.Farm.owner_id == user.id,
        )
    )

    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    if farm.latitude is None or farm.longitude is None:
        raise HTTPException(
            status_code=400,
            detail="Add latitude and longitude to this farm before requesting weather",
        )

    params = {
        "latitude": farm.latitude,
        "longitude": farm.longitude,
        "current": (
            "temperature_2m,relative_humidity_2m,apparent_temperature,"
            "precipitation,weather_code,wind_speed_10m"
        ),
        "daily": (
            "weather_code,temperature_2m_max,temperature_2m_min,"
            "precipitation_sum,precipitation_probability_max,"
            "et0_fao_evapotranspiration"
        ),
        "forecast_days": 7,
        "timezone": "auto",
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(OPEN_METEO_URL, params=params)
            response.raise_for_status()
            weather_data = response.json()

    except (httpx.HTTPError, ValueError):
        raise HTTPException(
            status_code=502,
            detail="Weather provider is temporarily unavailable or returned invalid data",
        )

    if not isinstance(weather_data, dict) or not isinstance(
        weather_data.get("current"), dict
    ) or not isinstance(weather_data.get("daily"), dict):
        raise HTTPException(
            status_code=502,
            detail="Weather provider returned an unexpected response",
        )

    snapshot = models.WeatherSnapshot(
        farm_id=farm.id,
        provider="open-meteo",
        fetched_at=datetime.utcnow(),
        payload=weather_data,
    )

    try:
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Weather was retrieved, but the snapshot could not be saved",
        )

    return {
        "farm_id": farm.id,
        "farm_name": farm.name,
        "provider": "Open-Meteo",
        "attribution": "Weather data by Open-Meteo, CC BY 4.0",
        "fetched_at": snapshot.fetched_at,
        "forecast": weather_data,
    }


@app.get("/api/v1/farms/{farm_id}/weather/history")
def get_farm_weather_history(
    farm_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    farm = db.scalar(
        select(models.Farm).where(
            models.Farm.id == farm_id,
            models.Farm.owner_id == user.id,
        )
    )

    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    snapshots = db.scalars(
        select(models.WeatherSnapshot)
        .where(models.WeatherSnapshot.farm_id == farm_id)
        .order_by(models.WeatherSnapshot.fetched_at.desc())
        .limit(20)
    ).all()

    return {
        "farm_id": farm.id,
        "provider": "Open-Meteo",
        "count": len(snapshots),
        "snapshots": [
            {
                "id": item.id,
                "fetched_at": item.fetched_at,
                "payload": item.payload,
            }
            for item in snapshots
        ],
    }

@app.get(
    "/api/v1/fields/{field_id}/soil-tests",
    response_model=list[schemas.SoilTestOut],
)
def list_soil_tests(
    field_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    field = db.scalar(
        select(models.Field)
        .join(models.Farm)
        .where(
            models.Field.id == field_id,
            models.Farm.owner_id == user.id,
        )
    )

    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    return db.scalars(
        select(models.SoilTest)
        .where(models.SoilTest.field_id == field_id)
        .order_by(
            models.SoilTest.test_date.desc(),
            models.SoilTest.id.desc(),
        )
    ).all()


@app.post(
    "/api/v1/fields/{field_id}/soil-tests",
    response_model=schemas.SoilTestOut,
    status_code=201,
)
def create_soil_test(
    field_id: int,
    payload: schemas.SoilTestCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    field = db.scalar(
        select(models.Field)
        .join(models.Farm)
        .where(
            models.Field.id == field_id,
            models.Farm.owner_id == user.id,
        )
    )

    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    soil_test = models.SoilTest(
        field_id=field_id,
        **payload.model_dump(),
    )

    db.add(soil_test)
    db.commit()
    db.refresh(soil_test)

    return soil_test


PLANT_HEALTH_API_URL = "http://127.0.0.1:8003/predict"
MAX_PLANT_IMAGE_BYTES = 10 * 1024 * 1024


@app.post("/api/v1/plant-health/predict")
async def predict_plant_health(
    file: UploadFile = File(...),
    user: models.User = Depends(get_current_user),
):
    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/bmp",
    }

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail="Upload a JPEG, PNG, WEBP, or BMP image.",
        )

    try:
        image_bytes = await file.read(MAX_PLANT_IMAGE_BYTES + 1)

        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail="The uploaded image is empty.",
            )

        if len(image_bytes) > MAX_PLANT_IMAGE_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Image must be 10 MB or smaller.",
            )

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    PLANT_HEALTH_API_URL,
                    files={
                        "file": (
                            file.filename or "plant-image",
                            image_bytes,
                            file.content_type,
                        )
                    },
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Plant disease inference is unavailable. "
                    "Make sure the inference service is running on port 8003."
                ),
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="The plant disease model could not process this image.",
            )

        try:
            prediction = response.json()
        except ValueError:
            raise HTTPException(
                status_code=502,
                detail="The inference service returned an invalid response.",
            )

        required_keys = {
            "predicted_class",
            "confidence",
            "confidence_percent",
            "top_predictions",
        }

        if not isinstance(prediction, dict) or not required_keys.issubset(
            prediction.keys()
        ):
            raise HTTPException(
                status_code=502,
                detail="The inference service returned an unexpected response.",
            )

        # Do not persist uploaded images or predictions in the database.
        return prediction

    finally:
        await file.close()


@app.get("/api/v1/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    farm_ids = select(models.Farm.id).where(models.Farm.owner_id == user.id)
    field_ids = select(models.Field.id).where(models.Field.farm_id.in_(farm_ids))
    cycle_ids = select(models.CropCycle.id).where(models.CropCycle.field_id.in_(field_ids))
    return {
        "farms": db.scalar(select(func.count()).select_from(models.Farm).where(models.Farm.owner_id == user.id)) or 0,
        "fields": db.scalar(select(func.count()).select_from(models.Field).where(models.Field.farm_id.in_(farm_ids))) or 0,
        "active_crop_cycles": db.scalar(select(func.count()).select_from(models.CropCycle).where(models.CropCycle.field_id.in_(field_ids), models.CropCycle.status == "active")) or 0,
        "pending_tasks": db.scalar(select(func.count()).select_from(models.FarmTask).where(models.FarmTask.crop_cycle_id.in_(cycle_ids), models.FarmTask.status == "pending")) or 0,
        "data_note": "Counts are calculated from records stored for the authenticated user. No seed records are created."
    }


# ---------------------------------------------------------
# Shared authorization helpers
# ---------------------------------------------------------

def get_owned_farm(
    db: Session,
    farm_id: int,
    user_id: int,
) -> models.Farm:
    farm = db.scalar(
        select(models.Farm).where(
            models.Farm.id == farm_id,
            models.Farm.owner_id == user_id,
        )
    )
    if farm is None:
        raise HTTPException(status_code=404, detail="Farm not found")
    return farm


def get_advisor_assignment(
    db: Session,
    farm_id: int,
    advisor_id: int,
) -> models.FarmAdvisorAssignment:
    assignment = db.scalar(
        select(models.FarmAdvisorAssignment).where(
            models.FarmAdvisorAssignment.farm_id == farm_id,
            models.FarmAdvisorAssignment.advisor_id == advisor_id,
            models.FarmAdvisorAssignment.active.is_(True),
        )
    )
    if assignment is None:
        raise HTTPException(
            status_code=403,
            detail="You are not assigned to this farm",
        )
    return assignment


def write_audit_log(
    db: Session,
    actor_user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        models.AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
    )


# ---------------------------------------------------------
# Admin portal
# ---------------------------------------------------------

@app.get("/api/v1/admin/summary")
def admin_summary(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_roles("admin")),
):
    return {
        "total_users": db.scalar(select(func.count(models.User.id))) or 0,
        "farmers": db.scalar(
            select(func.count(models.User.id)).where(
                models.User.role == "farmer"
            )
        ) or 0,
        "advisors": db.scalar(
            select(func.count(models.User.id)).where(
                models.User.role == "advisor"
            )
        ) or 0,
        "admins": db.scalar(
            select(func.count(models.User.id)).where(
                models.User.role == "admin"
            )
        ) or 0,
        "farms": db.scalar(select(func.count(models.Farm.id))) or 0,
        "advisory_requests": db.scalar(
            select(func.count(models.AdvisoryRequest.id))
        ) or 0,
    }


@app.get("/api/v1/admin/users")
def admin_list_users(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_roles("admin")),
):
    users = db.scalars(
        select(models.User).order_by(models.User.created_at.desc())
    ).all()

    return [
        {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at,
        }
        for user in users
    ]


@app.patch("/api/v1/admin/users/{user_id}/role")
def admin_update_user_role(
    user_id: int,
    payload: schemas.RoleUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_roles("admin")),
):
    target = db.get(models.User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    if target.id == admin.id and payload.role != "admin":
        raise HTTPException(
            status_code=400,
            detail="You cannot remove your own administrator role",
        )

    if target.role == "admin" and payload.role != "admin":
        active_admin_count = db.scalar(
            select(func.count(models.User.id)).where(
                models.User.role == "admin",
                models.User.is_active.is_(True),
            )
        ) or 0
        if target.is_active and active_admin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove the last administrator",
            )

    old_role = target.role
    target.role = payload.role
    write_audit_log(
        db,
        admin.id,
        "user.role_updated",
        "user",
        target.id,
        {"old_role": old_role, "new_role": payload.role},
    )
    db.commit()

    return {
        "id": target.id,
        "email": target.email,
        "full_name": target.full_name,
        "role": target.role,
        "is_active": target.is_active,
    }


@app.post("/api/v1/admin/farms/{farm_id}/advisor")
def admin_assign_advisor(
    farm_id: int,
    payload: schemas.AdvisorAssign,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_roles("admin")),
):
    farm = db.get(models.Farm, farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail="Farm not found")

    advisor = db.get(models.User, payload.advisor_id)
    if advisor is None or advisor.role != "advisor":
        raise HTTPException(
            status_code=400,
            detail="The selected user is not an advisor",
        )

    assignment = db.scalar(
        select(models.FarmAdvisorAssignment).where(
            models.FarmAdvisorAssignment.farm_id == farm_id,
            models.FarmAdvisorAssignment.advisor_id == advisor.id,
        )
    )
    if assignment is None:
        assignment = models.FarmAdvisorAssignment(
            farm_id=farm_id,
            advisor_id=advisor.id,
            assigned_by_id=admin.id,
            active=True,
        )
        db.add(assignment)
    else:
        assignment.active = True
        assignment.assigned_by_id = admin.id

    write_audit_log(
        db,
        admin.id,
        "advisor.assigned",
        "farm",
        farm_id,
        {"advisor_id": advisor.id},
    )
    db.commit()

    return {
        "message": "Advisor assigned successfully",
        "farm_id": farm_id,
        "advisor_id": advisor.id,
        "status": "active",
    }


@app.get("/api/v1/admin/audit-logs")
def admin_audit_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_roles("admin")),
):
    limit = max(1, min(limit, 500))
    logs = db.scalars(
        select(models.AuditLog)
        .order_by(models.AuditLog.created_at.desc())
        .limit(limit)
    ).all()

    return [
        {
            "id": log.id,
            "actor_user_id": log.actor_user_id,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "created_at": log.created_at,
        }
        for log in logs
    ]


# ---------------------------------------------------------
# Farmer advisory requests and recommendations
# ---------------------------------------------------------

@app.post("/api/v1/advisory/requests", status_code=201)
def create_advisory_request(
    payload: schemas.AdvisoryRequestCreate,
    db: Session = Depends(get_db),
    farmer: models.User = Depends(require_roles("farmer")),
):
    get_owned_farm(db, payload.farm_id, farmer.id)

    advisory_request = models.AdvisoryRequest(
        farm_id=payload.farm_id,
        farmer_id=farmer.id,
        subject=payload.subject,
        description=payload.description,
        category=payload.category,
        priority=payload.priority,
        status="open",
    )
    db.add(advisory_request)
    db.flush()
    write_audit_log(
        db,
        farmer.id,
        "advisory.created",
        "advisory_request",
        advisory_request.id,
    )
    db.commit()
    db.refresh(advisory_request)

    return schemas.AdvisoryRequestOut.model_validate(advisory_request)


@app.get("/api/v1/advisory/requests")
def farmer_advisory_requests(
    db: Session = Depends(get_db),
    farmer: models.User = Depends(require_roles("farmer")),
):
    requests = db.scalars(
        select(models.AdvisoryRequest)
        .where(models.AdvisoryRequest.farmer_id == farmer.id)
        .order_by(models.AdvisoryRequest.created_at.desc())
    ).all()
    return [
        schemas.AdvisoryRequestOut.model_validate(item)
        for item in requests
    ]


@app.get("/api/v1/advisory/requests/{request_id}/recommendations")
def farmer_recommendations(
    request_id: int,
    db: Session = Depends(get_db),
    farmer: models.User = Depends(require_roles("farmer")),
):
    advisory_request = db.scalar(
        select(models.AdvisoryRequest).where(
            models.AdvisoryRequest.id == request_id,
            models.AdvisoryRequest.farmer_id == farmer.id,
        )
    )
    if advisory_request is None:
        raise HTTPException(status_code=404, detail="Request not found")

    recommendations = db.scalars(
        select(models.AdvisorRecommendation)
        .where(models.AdvisorRecommendation.request_id == request_id)
        .order_by(models.AdvisorRecommendation.created_at.desc())
    ).all()
    return [
        schemas.AdvisorRecommendationOut.model_validate(item)
        for item in recommendations
    ]


# ---------------------------------------------------------
# Advisor portal
# ---------------------------------------------------------

@app.get("/api/v1/advisor/farms")
def advisor_assigned_farms(
    db: Session = Depends(get_db),
    advisor: models.User = Depends(require_roles("advisor")),
):
    assigned_farms = db.execute(
        select(models.FarmAdvisorAssignment, models.Farm)
        .join(
            models.Farm,
            models.Farm.id == models.FarmAdvisorAssignment.farm_id,
        )
        .where(
            models.FarmAdvisorAssignment.advisor_id == advisor.id,
            models.FarmAdvisorAssignment.active.is_(True),
        )
    ).all()
    return [
        {
            "assignment_id": assignment.id,
            "farm_id": farm.id,
            "farm_name": farm.name,
            "location": farm.location,
            "area": farm.area,
            "area_unit": farm.area_unit,
            "owner_id": farm.owner_id,
        }
        for assignment, farm in assigned_farms
    ]


@app.get("/api/v1/advisor/requests")
def advisor_requests(
    db: Session = Depends(get_db),
    advisor: models.User = Depends(require_roles("advisor")),
):
    assigned_farm_ids = select(
        models.FarmAdvisorAssignment.farm_id
    ).where(
        models.FarmAdvisorAssignment.advisor_id == advisor.id,
        models.FarmAdvisorAssignment.active.is_(True),
    )
    requests = db.scalars(
        select(models.AdvisoryRequest)
        .where(models.AdvisoryRequest.farm_id.in_(assigned_farm_ids))
        .order_by(models.AdvisoryRequest.created_at.desc())
    ).all()
    return [
        schemas.AdvisoryRequestOut.model_validate(item)
        for item in requests
    ]


@app.patch("/api/v1/advisor/requests/{request_id}/status")
def advisor_update_request_status(
    request_id: int,
    payload: schemas.AdvisoryStatusUpdate,
    db: Session = Depends(get_db),
    advisor: models.User = Depends(require_roles("advisor")),
):
    advisory_request = db.get(models.AdvisoryRequest, request_id)
    if advisory_request is None:
        raise HTTPException(status_code=404, detail="Request not found")

    get_advisor_assignment(db, advisory_request.farm_id, advisor.id)
    advisory_request.status = payload.status
    advisory_request.advisor_id = advisor.id
    write_audit_log(
        db,
        advisor.id,
        "advisory.status_updated",
        "advisory_request",
        advisory_request.id,
        {"status": payload.status},
    )
    db.commit()
    db.refresh(advisory_request)
    return schemas.AdvisoryRequestOut.model_validate(advisory_request)


@app.post(
    "/api/v1/advisor/requests/{request_id}/recommendations",
    status_code=201,
)
def advisor_create_recommendation(
    request_id: int,
    payload: schemas.AdvisorRecommendationCreate,
    db: Session = Depends(get_db),
    advisor: models.User = Depends(require_roles("advisor")),
):
    advisory_request = db.get(models.AdvisoryRequest, request_id)
    if advisory_request is None:
        raise HTTPException(status_code=404, detail="Request not found")

    get_advisor_assignment(db, advisory_request.farm_id, advisor.id)
    recommendation = models.AdvisorRecommendation(
        request_id=advisory_request.id,
        advisor_id=advisor.id,
        recommendation=payload.recommendation,
        action_items=payload.action_items,
    )
    advisory_request.advisor_id = advisor.id
    if advisory_request.status == "open":
        advisory_request.status = "in_progress"

    db.add(recommendation)
    db.flush()
    write_audit_log(
        db,
        advisor.id,
        "advisory.recommendation_created",
        "advisory_request",
        advisory_request.id,
    )
    db.commit()
    db.refresh(recommendation)
    return schemas.AdvisorRecommendationOut.model_validate(recommendation)

@app.get("/api/v1/admin/farms")
def admin_list_farms(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_roles("admin")),
):
    farms = db.scalars(
        select(models.Farm).order_by(models.Farm.id.desc())
    ).all()

    return [
        {
            "id": farm.id,
            "name": farm.name,
            "location": farm.location,
            "area": farm.area,
            "area_unit": farm.area_unit,
            "owner_id": farm.owner_id,
        }
        for farm in farms
    ]