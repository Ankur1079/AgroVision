import json
import re
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.security import get_current_user, require_roles

router = APIRouter(prefix="/api/v1", tags=["Module J - Governance"])


def _audit(db: Session, actor_id: int | None, action: str, entity_type: str,
           entity_id: int | None = None, details: dict | None = None) -> None:
    db.add(models.AuditLog(
        actor_user_id=actor_id, action=action, entity_type=entity_type,
        entity_id=entity_id, details=details,
    ))


def record_system_event(db: Session, event_type: str, source: str, message: str,
                        severity: str = "error", details: dict | None = None) -> models.SystemEvent:
    """Record a model, background-job, or integration event in the current transaction."""
    event = models.SystemEvent(
        event_type=event_type[:100], source=source[:120], message=message,
        severity=severity, status="open",
        details_json=json.dumps(details, default=str) if details is not None else None,
    )
    db.add(event)
    return event


def _active_assignment(db: Session, farm_id: int, advisor_id: int) -> models.FarmAdvisorAssignment:
    assignment = db.scalar(select(models.FarmAdvisorAssignment).where(
        models.FarmAdvisorAssignment.farm_id == farm_id,
        models.FarmAdvisorAssignment.advisor_id == advisor_id,
        models.FarmAdvisorAssignment.active.is_(True),
    ))
    if assignment is None:
        raise HTTPException(status_code=403, detail="You are not assigned to this farm")
    return assignment


class ReviewCreate(BaseModel):
    farm_id: int = Field(gt=0)
    subject: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10, max_length=5000)
    category: str = Field(default="general", min_length=1, max_length=50)
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")


class ReviewResponseCreate(BaseModel):
    comments: str = Field(min_length=3, max_length=10000)
    recommendations: str | None = Field(default=None, max_length=10000)
    action_items: list[str] = Field(default_factory=list, max_length=50)
    status: str = Field(default="reviewed", pattern="^(reviewed|follow_up_required)$")
    follow_up_date: date | None = None


class UserActiveUpdate(BaseModel):
    is_active: bool


class AssignmentCreate(BaseModel):
    farm_id: int = Field(gt=0)
    advisor_id: int = Field(gt=0)
    active: bool = True


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    active: bool = True


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    active: bool | None = None


class ModelClassCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    model_name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    active: bool = True


class ModelClassUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    model_name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    active: bool | None = None


class IntegrationCreate(BaseModel):
    provider_type: str = Field(min_length=2, max_length=80)
    provider_name: str = Field(min_length=2, max_length=160)
    enabled: bool = False
    settings: dict[str, Any] = Field(default_factory=dict)
    secret_env_var: str | None = Field(default=None, max_length=160)


class SystemEventCreate(BaseModel):
    event_type: str = Field(min_length=2, max_length=100)
    severity: str = Field(default="error", pattern="^(debug|info|warning|error|critical)$")
    source: str = Field(min_length=2, max_length=120)
    message: str = Field(min_length=2, max_length=5000)
    details: dict[str, Any] | None = None


def _reject_secret_values(settings: dict[str, Any]) -> None:
    forbidden = re.compile(r"(secret|password|token|api[_-]?key|credential|authorization)", re.I)
    for key, value in settings.items():
        if forbidden.search(str(key)):
            raise HTTPException(
                status_code=422,
                detail=f"Sensitive setting '{key}' is not accepted. Store secret values in environment variables.",
            )
        if isinstance(value, dict):
            _reject_secret_values(value)


def _integration_out(item: models.IntegrationConfig) -> dict:
    try:
        settings = json.loads(item.settings_json) if item.settings_json else {}
    except (TypeError, json.JSONDecodeError):
        settings = {}
    return {
        "id": item.id, "provider_type": item.provider_type,
        "provider_name": item.provider_name, "enabled": item.enabled,
        "settings": settings, "secret_configured": bool(item.secret_env_var),
        "secret_env_var": item.secret_env_var, "updated_by": item.updated_by,
        "updated_at": item.updated_at,
    }


# Farmer review requests use the existing advisory_requests table; no duplicate
# advisory_review_requests table is required.
@router.post("/advisory/reviews", status_code=201)
def create_review_request(payload: ReviewCreate, db: Session = Depends(get_db),
                          farmer: models.User = Depends(require_roles("farmer"))):
    farm = db.scalar(select(models.Farm).where(
        models.Farm.id == payload.farm_id, models.Farm.owner_id == farmer.id
    ))
    if farm is None:
        raise HTTPException(status_code=404, detail="Farm not found")
    item = models.AdvisoryRequest(
        farm_id=farm.id, farmer_id=farmer.id, subject=payload.subject,
        description=payload.description, category=payload.category,
        priority=payload.priority, status="open",
    )
    db.add(item)
    db.flush()
    _audit(db, farmer.id, "advisory.review_requested", "advisory_request", item.id,
           {"farm_id": farm.id, "category": payload.category})
    db.commit()
    db.refresh(item)
    return {"id": item.id, "farm_id": item.farm_id, "farmer_id": item.farmer_id,
            "advisor_id": item.advisor_id, "subject": item.subject,
            "description": item.description, "category": item.category,
            "priority": item.priority, "status": item.status,
            "created_at": item.created_at, "updated_at": item.updated_at}


@router.get("/advisory/reviews")
def list_review_requests(db: Session = Depends(get_db),
                         user: models.User = Depends(get_current_user)):
    if user.role == "farmer":
        statement = select(models.AdvisoryRequest).where(models.AdvisoryRequest.farmer_id == user.id)
    elif user.role == "advisor":
        assigned = select(models.FarmAdvisorAssignment.farm_id).where(
            models.FarmAdvisorAssignment.advisor_id == user.id,
            models.FarmAdvisorAssignment.active.is_(True))
        statement = select(models.AdvisoryRequest).where(models.AdvisoryRequest.farm_id.in_(assigned))
    elif user.role == "admin":
        statement = select(models.AdvisoryRequest)
    else:
        raise HTTPException(status_code=403, detail="Not permitted to view advisory reviews")
    items = db.scalars(statement.order_by(models.AdvisoryRequest.created_at.desc())).all()
    result = []
    for item in items:
        latest = db.scalar(select(models.AdvisorReview).where(
            models.AdvisorReview.request_id == item.id
        ).order_by(models.AdvisorReview.created_at.desc()))
        result.append({
            "id": item.id, "farm_id": item.farm_id, "farmer_id": item.farmer_id,
            "advisor_id": item.advisor_id, "subject": item.subject,
            "category": item.category, "priority": item.priority,
            "description": item.description, "status": item.status,
            "created_at": item.created_at, "updated_at": item.updated_at,
            "latest_review": ({
                "id": latest.id, "advisor_id": latest.advisor_id,
                "comments": latest.comments, "recommendations": latest.recommendations,
                "status": latest.status, "follow_up_date": latest.follow_up_date,
                "created_at": latest.created_at,
            } if latest else None),
        })
    return result


@router.get("/advisory/reviews/{review_id}/context")
def review_context(review_id: int, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    request = db.get(models.AdvisoryRequest, review_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Review request not found")
    if user.role == "farmer":
        if request.farmer_id != user.id:
            raise HTTPException(status_code=404, detail="Review request not found")
    elif user.role == "advisor":
        _active_assignment(db, request.farm_id, user.id)
        _audit(db, user.id, "advisory.context_accessed", "advisory_request", request.id,
               {"farm_id": request.farm_id})
        db.commit()
    elif user.role != "admin":
        raise HTTPException(status_code=403, detail="Not permitted")
    farm = db.get(models.Farm, request.farm_id)
    fields = db.scalars(select(models.Field).where(models.Field.farm_id == farm.id)).all()
    field_context = []
    for field in fields:
        cycles = db.scalars(select(models.CropCycle).where(models.CropCycle.field_id == field.id)).all()
        soils = db.scalars(select(models.SoilTest).where(models.SoilTest.field_id == field.id)
                           .order_by(models.SoilTest.test_date.desc()).limit(5)).all()
        field_context.append({
            "id": field.id, "name": field.name, "area": field.area,
            "soil_type": field.soil_type, "irrigation_method": field.irrigation_method,
            "crop_cycles": [{"id": c.id, "crop_name": c.crop_name, "variety": c.variety,
                             "planting_date": c.planting_date, "status": c.status,
                             "expected_harvest_date": c.expected_harvest_date} for c in cycles],
            "recent_soil_tests": [{"id": s.id, "test_date": s.test_date, "ph": s.ph,
                                   "nitrogen": s.nitrogen, "phosphorus": s.phosphorus,
                                   "potassium": s.potassium, "npk_unit": s.npk_unit,
                                   "notes": s.notes} for s in soils],
        })
    return {
        "request": {"id": request.id, "subject": request.subject,
                    "description": request.description, "category": request.category,
                    "priority": request.priority, "status": request.status,
                    "created_at": request.created_at},
        "farm": {"id": farm.id, "name": farm.name, "location": farm.location,
                 "area": farm.area, "area_unit": farm.area_unit},
        "fields": field_context,
    }


@router.post("/advisory/reviews/{review_id}/responses", status_code=201)
def submit_review_response(review_id: int, payload: ReviewResponseCreate,
                           db: Session = Depends(get_db),
                           advisor: models.User = Depends(require_roles("advisor"))):
    request = db.get(models.AdvisoryRequest, review_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Review request not found")
    _active_assignment(db, request.farm_id, advisor.id)
    review = models.AdvisorReview(
        request_id=request.id, advisor_id=advisor.id, comments=payload.comments,
        recommendations=payload.recommendations or "", status=payload.status,
        follow_up_date=payload.follow_up_date,
    )
    db.add(review)
    if payload.recommendations:
        db.add(models.AdvisorRecommendation(
            request_id=request.id, advisor_id=advisor.id,
            recommendation=payload.recommendations, action_items=payload.action_items,
        ))
    request.advisor_id = advisor.id
    request.status = "in_progress" if payload.status == "follow_up_required" else "resolved"
    _audit(db, advisor.id, "advisory.review_submitted", "advisory_request", request.id,
           {"review_status": payload.status, "follow_up_date": str(payload.follow_up_date) if payload.follow_up_date else None})
    db.commit()
    db.refresh(review)
    return {"id": review.id, "request_id": review.request_id, "advisor_id": review.advisor_id,
            "comments": review.comments, "recommendations": review.recommendations,
            "status": review.status, "follow_up_date": review.follow_up_date,
            "created_at": review.created_at}


# Admin user activation
@router.patch("/admin/users/{user_id}/active")
def set_user_active(user_id: int, payload: UserActiveUpdate,
                    db: Session = Depends(get_db),
                    admin: models.User = Depends(require_roles("admin"))):
    target = db.get(models.User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id and not payload.is_active:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    if target.role == "admin" and target.is_active and not payload.is_active:
        active_admins = db.scalar(select(func.count(models.User.id)).where(
            models.User.role == "admin", models.User.is_active.is_(True))) or 0
        if active_admins <= 1:
            raise HTTPException(status_code=400, detail="Cannot deactivate the last active administrator")
    old = target.is_active
    target.is_active = payload.is_active
    _audit(db, admin.id, "user.active_updated", "user", target.id,
           {"old_is_active": old, "new_is_active": target.is_active})
    db.commit()
    return {"id": target.id, "email": target.email, "role": target.role, "is_active": target.is_active}


# Assignment administration
@router.get("/admin/assignments")
def list_assignments(db: Session = Depends(get_db),
                     admin: models.User = Depends(require_roles("admin"))):
    rows = db.execute(select(models.FarmAdvisorAssignment, models.Farm, models.User)
                      .join(models.Farm, models.Farm.id == models.FarmAdvisorAssignment.farm_id)
                      .join(models.User, models.User.id == models.FarmAdvisorAssignment.advisor_id)
                      .order_by(models.FarmAdvisorAssignment.id.desc())).all()
    return [{"id": a.id, "farm_id": f.id, "farm_name": f.name, "advisor_id": u.id,
             "advisor_name": u.full_name, "active": a.active, "assigned_by_id": a.assigned_by_id,
             "created_at": a.created_at} for a, f, u in rows]


@router.post("/admin/assignments", status_code=201)
def create_assignment(payload: AssignmentCreate, db: Session = Depends(get_db),
                      admin: models.User = Depends(require_roles("admin"))):
    farm = db.get(models.Farm, payload.farm_id)
    advisor = db.get(models.User, payload.advisor_id)
    if farm is None:
        raise HTTPException(status_code=404, detail="Farm not found")
    if advisor is None or advisor.role != "advisor" or not advisor.is_active:
        raise HTTPException(status_code=400, detail="Select an active advisor account")
    item = db.scalar(select(models.FarmAdvisorAssignment).where(
        models.FarmAdvisorAssignment.farm_id == farm.id,
        models.FarmAdvisorAssignment.advisor_id == advisor.id))
    if item is None:
        item = models.FarmAdvisorAssignment(farm_id=farm.id, advisor_id=advisor.id,
                                            assigned_by_id=admin.id, active=payload.active)
        db.add(item)
    else:
        item.active = payload.active
        item.assigned_by_id = admin.id
    _audit(db, admin.id, "advisor.assignment_updated", "farm", farm.id,
           {"advisor_id": advisor.id, "active": payload.active})
    db.commit()
    db.refresh(item)
    return {"id": item.id, "farm_id": item.farm_id, "advisor_id": item.advisor_id,
            "active": item.active, "assigned_by_id": item.assigned_by_id}


@router.get("/admin/crop-categories")
def list_categories(db: Session = Depends(get_db),
                    admin: models.User = Depends(require_roles("admin"))):
    return db.scalars(select(models.CropCategory).order_by(models.CropCategory.name)).all()


@router.post("/admin/crop-categories", status_code=201)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db),
                    admin: models.User = Depends(require_roles("admin"))):
    if db.scalar(select(models.CropCategory).where(func.lower(models.CropCategory.name) == payload.name.lower())):
        raise HTTPException(status_code=409, detail="Crop category already exists")
    item = models.CropCategory(**payload.model_dump())
    db.add(item)
    db.flush()
    _audit(db, admin.id, "crop_category.created", "crop_category", item.id, {"name": item.name})
    db.commit()
    db.refresh(item)
    return item


@router.patch("/admin/crop-categories/{category_id}")
def update_category(category_id: int, payload: CategoryUpdate, db: Session = Depends(get_db),
                    admin: models.User = Depends(require_roles("admin"))):
    item = db.get(models.CropCategory, category_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Crop category not found")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and db.scalar(select(models.CropCategory).where(
        func.lower(models.CropCategory.name) == changes["name"].lower(),
        models.CropCategory.id != category_id)):
        raise HTTPException(status_code=409, detail="Crop category already exists")
    for key, value in changes.items():
        setattr(item, key, value)
    _audit(db, admin.id, "crop_category.updated", "crop_category", item.id, changes)
    db.commit()
    db.refresh(item)
    return item


@router.get("/admin/model-classes")
def list_model_classes(db: Session = Depends(get_db),
                       admin: models.User = Depends(require_roles("admin"))):
    return db.scalars(select(models.SupportedModelClass).order_by(models.SupportedModelClass.name)).all()


@router.post("/admin/model-classes", status_code=201)
def create_model_class(payload: ModelClassCreate, db: Session = Depends(get_db),
                       admin: models.User = Depends(require_roles("admin"))):
    item = models.SupportedModelClass(**payload.model_dump())
    db.add(item)
    db.flush()
    _audit(db, admin.id, "model_class.created", "supported_model_class", item.id,
           {"name": item.name, "model_name": item.model_name})
    db.commit()
    db.refresh(item)
    return item


@router.patch("/admin/model-classes/{model_class_id}")
def update_model_class(model_class_id: int, payload: ModelClassUpdate,
                       db: Session = Depends(get_db),
                       admin: models.User = Depends(require_roles("admin"))):
    item = db.get(models.SupportedModelClass, model_class_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Model class not found")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(item, key, value)
    _audit(db, admin.id, "model_class.updated", "supported_model_class", item.id, changes)
    db.commit()
    db.refresh(item)
    return item


@router.get("/admin/integrations")
def list_integrations(db: Session = Depends(get_db),
                      admin: models.User = Depends(require_roles("admin"))):
    return [_integration_out(item) for item in db.scalars(
        select(models.IntegrationConfig).order_by(models.IntegrationConfig.provider_type,
                                                  models.IntegrationConfig.provider_name)).all()]


@router.post("/admin/integrations", status_code=201)
def create_integration(payload: IntegrationCreate, db: Session = Depends(get_db),
                       admin: models.User = Depends(require_roles("admin"))):
    _reject_secret_values(payload.settings)
    if payload.secret_env_var and not re.fullmatch(r"[A-Z][A-Z0-9_]{1,159}", payload.secret_env_var):
        raise HTTPException(status_code=422, detail="secret_env_var must be an uppercase environment-variable name")
    item = models.IntegrationConfig(
        provider_type=payload.provider_type, provider_name=payload.provider_name,
        enabled=payload.enabled, settings_json=json.dumps(payload.settings),
        secret_env_var=payload.secret_env_var, updated_by=admin.id,
    )
    db.add(item)
    db.flush()
    _audit(db, admin.id, "integration.created", "integration_config", item.id,
           {"provider_type": item.provider_type, "provider_name": item.provider_name,
            "enabled": item.enabled, "secret_env_var": item.secret_env_var})
    db.commit()
    db.refresh(item)
    return _integration_out(item)


@router.get("/admin/system-events")
def list_system_events(limit: int = Query(default=100, ge=1, le=500),
                       status_filter: str | None = Query(default=None, alias="status"),
                       db: Session = Depends(get_db),
                       admin: models.User = Depends(require_roles("admin"))):
    statement = select(models.SystemEvent)
    if status_filter:
        statement = statement.where(models.SystemEvent.status == status_filter)
    items = db.scalars(statement.order_by(models.SystemEvent.created_at.desc()).limit(limit)).all()
    result = []
    for item in items:
        try:
            details = json.loads(item.details_json) if item.details_json else None
        except json.JSONDecodeError:
            details = None
        result.append({"id": item.id, "event_type": item.event_type, "severity": item.severity,
                       "source": item.source, "status": item.status, "message": item.message,
                       "details": details, "created_at": item.created_at,
                       "resolved_at": item.resolved_at, "resolved_by": item.resolved_by})
    return result


@router.post("/admin/system-events", status_code=201)
def create_system_event(payload: SystemEventCreate, db: Session = Depends(get_db),
                        admin: models.User = Depends(require_roles("admin"))):
    item = record_system_event(db, payload.event_type, payload.source, payload.message,
                               payload.severity, payload.details)
    db.flush()
    _audit(db, admin.id, "system_event.created", "system_event", item.id,
           {"event_type": item.event_type, "severity": item.severity})
    db.commit()
    db.refresh(item)
    return {"id": item.id, "event_type": item.event_type, "severity": item.severity,
            "source": item.source, "status": item.status, "message": item.message,
            "created_at": item.created_at}


@router.patch("/admin/system-events/{event_id}/resolve")
def resolve_system_event(event_id: int, db: Session = Depends(get_db),
                         admin: models.User = Depends(require_roles("admin"))):
    item = db.get(models.SystemEvent, event_id)
    if item is None:
        raise HTTPException(status_code=404, detail="System event not found")
    if item.status != "resolved":
        item.status = "resolved"
        item.resolved_at = datetime.utcnow()
        item.resolved_by = admin.id
        _audit(db, admin.id, "system_event.resolved", "system_event", item.id)
        db.commit()
        db.refresh(item)
    return {"id": item.id, "status": item.status, "resolved_at": item.resolved_at,
            "resolved_by": item.resolved_by}


@router.get("/admin/audit-logs")
def module_j_audit_logs(limit: int = Query(default=100, ge=1, le=500),
                        db: Session = Depends(get_db),
                        admin: models.User = Depends(require_roles("admin"))):
    logs = db.scalars(select(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(limit)).all()
    return [{"id": x.id, "actor_user_id": x.actor_user_id, "action": x.action,
             "entity_type": x.entity_type, "entity_id": x.entity_id,
             "details": x.details, "created_at": x.created_at} for x in logs]
