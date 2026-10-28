from datetime import date, datetime, timedelta
import json, os, uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.security import get_current_user

router = APIRouter()


# ---- Crop observations, photographs, task statuses and reminders ----
def _owned_cycle(db: Session, cycle_id: int, user: models.User):
    cycle = db.scalar(select(models.CropCycle).join(models.Field).join(models.Farm).where(models.CropCycle.id == cycle_id, models.Farm.owner_id == user.id))
    if not cycle:
        raise HTTPException(status_code=404, detail="Crop cycle not found")
    return cycle

def _owned_farm(db: Session, farm_id: int, user: models.User):
    farm = db.scalar(select(models.Farm).where(models.Farm.id == farm_id, models.Farm.owner_id == user.id))
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    return farm

def _owned_field(db: Session, field_id: int, user: models.User):
    field = db.scalar(select(models.Field).join(models.Farm).where(models.Field.id == field_id, models.Farm.owner_id == user.id))
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    return field

@router.post('/api/v1/crop-cycles/{cycle_id}/observations', status_code=201)
def add_crop_observation(cycle_id: int, payload: dict, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _owned_cycle(db, cycle_id, user)
    kind = payload.get('observation_type', 'note')
    if kind not in {'planting', 'germination', 'growth_stage', 'harvest', 'note'}:
        raise HTTPException(status_code=422, detail='Invalid observation_type')
    pct = payload.get('germination_percent')
    if pct is not None and not 0 <= float(pct) <= 100:
        raise HTTPException(status_code=422, detail='Germination percentage must be 0–100')
    row = extra_models.CropObservation(crop_cycle_id=cycle_id, observation_type=kind,
        observed_on=date.fromisoformat(payload['observed_on']) if payload.get('observed_on') else date.today(), growth_stage=payload.get('growth_stage'),
        germination_percent=pct, note=payload.get('note'), photo_path=payload.get('photo_path'))
    db.add(row); db.commit(); db.refresh(row); return row

@router.get('/api/v1/crop-cycles/{cycle_id}/observations')
def list_crop_observations(cycle_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _owned_cycle(db, cycle_id, user)
    return db.scalars(select(extra_models.CropObservation).where(extra_models.CropObservation.crop_cycle_id == cycle_id).order_by(extra_models.CropObservation.observed_on.desc(), extra_models.CropObservation.id.desc())).all()

@router.post('/api/v1/crop-cycles/{cycle_id}/photos', status_code=201)
async def upload_crop_photo(cycle_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _owned_cycle(db, cycle_id, user)
    allowed = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp'}
    if file.content_type not in allowed:
        raise HTTPException(status_code=415, detail='Only JPG, PNG or WEBP photos are supported')
    content = await file.read()
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail='Photo must be 8 MB or smaller')
    folder = Path(os.getenv('AGROVISION_UPLOAD_DIR', 'uploads/crop-photos'))
    folder.mkdir(parents=True, exist_ok=True)
    name = f'{uuid.uuid4().hex}{allowed[file.content_type]}'
    (folder / name).write_bytes(content)
    row = extra_models.CropObservation(crop_cycle_id=cycle_id, observation_type='note', observed_on=date.today(), note=(file.filename or 'Crop photo'), photo_path=f'/uploads/crop-photos/{name}')
    db.add(row); db.commit(); db.refresh(row)
    return row

@router.patch('/api/v1/tasks/{task_id}/status')
def update_task_status(task_id: int, payload: dict, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    task = db.scalar(select(models.FarmTask).join(models.CropCycle).join(models.Field).join(models.Farm).where(models.FarmTask.id == task_id, models.Farm.owner_id == user.id))
    if not task: raise HTTPException(status_code=404, detail='Task not found')
    status_value = payload.get('status')
    if status_value not in {'pending', 'completed', 'postponed', 'cancelled'}: raise HTTPException(status_code=422, detail='Status must be pending, completed, postponed or cancelled')
    task.status = status_value
    if payload.get('due_date'): task.due_date = date.fromisoformat(payload['due_date'])
    db.commit(); db.refresh(task); return task

@router.get('/api/v1/tasks/upcoming')
def upcoming_tasks(days: int = 14, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    days = max(1, min(days, 90))
    owned_cycles = select(models.CropCycle.id).join(models.Field).join(models.Farm).where(models.Farm.owner_id == user.id)
    rows = db.scalars(select(models.FarmTask).where(models.FarmTask.crop_cycle_id.in_(owned_cycles), models.FarmTask.status == 'pending', models.FarmTask.due_date <= date.today() + timedelta(days=days)).order_by(models.FarmTask.due_date)).all()
    return rows

# ---- Irrigation planning: rules are explicit heuristics, not agronomic measurements ----
@router.post('/api/v1/crop-cycles/{cycle_id}/irrigation/recommendations', status_code=201)
def recommend_irrigation(cycle_id: int, payload: dict, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    cycle = _owned_cycle(db, cycle_id, user)
    field = db.get(models.Field, cycle.field_id)
    moisture = payload.get('soil_moisture_percent')
    if moisture is not None and not 0 <= float(moisture) <= 100: raise HTTPException(status_code=422, detail='Soil moisture must be 0–100%')
    stage = payload.get('crop_stage') or 'not recorded'
    method = payload.get('irrigation_method') or field.irrigation_method or 'not recorded'
    source = payload.get('water_source') or 'not recorded'
    area_ha = float(field.area) if payload.get('area_unit') == 'hectare' else None
    # Conservative demonstration rule: low manual reading (<30%) suggests review; no sensor/live data implied.
    low = moisture is not None and float(moisture) < 30
    status_value = 'suggested' if low else 'review'
    depth_mm = float(payload.get('assumed_depth_mm') or 5)
    estimated_liters = round(area_ha * 10000 * depth_mm, 1) if area_ha is not None else None
    assumptions = {'soil_moisture_percent': moisture, 'threshold_percent': 30, 'crop_stage': stage, 'irrigation_method': method, 'water_source': source, 'field_area': field.area, 'area_unit': payload.get('area_unit') or 'unspecified', 'assumed_depth_mm': depth_mm, 'rule_version': 'simple-rule-v1'}
    reason = ('Manual soil-moisture reading is below the illustrative 30% threshold; inspect the field and consider irrigation.' if low else 'No low-moisture trigger was established. Inspect the field and enter a current reading; this rule does not replace agronomic advice.')
    row = extra_models.IrrigationRecommendation(crop_cycle_id=cycle_id, status=status_value, suggested_task='Inspect soil moisture / consider irrigation', reason=reason, inputs_json=json.dumps(assumptions), estimated_water_liters=estimated_liters)
    db.add(row); db.commit(); db.refresh(row); return row

@router.get('/api/v1/crop-cycles/{cycle_id}/irrigation/recommendations')
def list_irrigation_recommendations(cycle_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _owned_cycle(db, cycle_id, user)
    return db.scalars(select(extra_models.IrrigationRecommendation).where(extra_models.IrrigationRecommendation.crop_cycle_id == cycle_id).order_by(extra_models.IrrigationRecommendation.created_at.desc())).all()

@router.patch('/api/v1/irrigation/recommendations/{recommendation_id}')
def decide_irrigation_recommendation(recommendation_id: int, payload: dict, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    row = db.get(extra_models.IrrigationRecommendation, recommendation_id)
    if not row: raise HTTPException(status_code=404, detail='Recommendation not found')
    _owned_cycle(db, row.crop_cycle_id, user)
    decision = payload.get('status')
    if decision not in {'accepted', 'edited', 'postponed', 'rejected'}: raise HTTPException(status_code=422, detail='Invalid recommendation decision')
    row.status = decision; row.decision_note = payload.get('decision_note')
    if decision in {'accepted', 'edited'}:
        task = models.FarmTask(crop_cycle_id=row.crop_cycle_id, title=payload.get('title') or row.suggested_task, description=f"Irrigation suggestion. Reason: {row.reason}. Inputs: {row.inputs_json}", due_date=date.fromisoformat(payload['due_date']) if payload.get('due_date') else date.today(), status='pending')
        db.add(task); db.flush(); row.task_id = task.id
    db.commit(); db.refresh(row); return row

@router.post('/api/v1/crop-cycles/{cycle_id}/irrigation/records', status_code=201)
def add_irrigation_record(cycle_id: int, payload: dict, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _owned_cycle(db, cycle_id, user)
    for k in ('duration_minutes', 'quantity_liters', 'soil_moisture_percent'):
        if payload.get(k) is not None and float(payload[k]) < 0: raise HTTPException(status_code=422, detail=f'{k} cannot be negative')
    if payload.get('soil_moisture_percent') is not None and float(payload['soil_moisture_percent']) > 100: raise HTTPException(status_code=422, detail='Soil moisture must be at most 100%')
    row = extra_models.IrrigationRecord(crop_cycle_id=cycle_id, irrigation_date=payload.get('irrigation_date') or date.today(), method=payload.get('method') or 'not recorded', water_source=payload.get('water_source'), soil_moisture_percent=payload.get('soil_moisture_percent'), duration_minutes=payload.get('duration_minutes'), quantity_liters=payload.get('quantity_liters'), quantity_is_estimated=bool(payload.get('quantity_is_estimated', False)), crop_stage=payload.get('crop_stage'), notes=payload.get('notes'))
    db.add(row); db.commit(); db.refresh(row); return row

@router.get('/api/v1/crop-cycles/{cycle_id}/irrigation/records')
def list_irrigation_records(cycle_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _owned_cycle(db, cycle_id, user)
    return db.scalars(select(extra_models.IrrigationRecord).where(extra_models.IrrigationRecord.crop_cycle_id == cycle_id).order_by(extra_models.IrrigationRecord.irrigation_date.desc())).all()

# ---- Soil test and farm-input records ----
@router.get('/api/v1/farms/{farm_id}/soil-tests')
def list_soil_tests(farm_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _owned_farm(db, farm_id, user)
    return db.scalars(select(extra_models.SoilTestRecord).where(extra_models.SoilTestRecord.farm_id == farm_id).order_by(extra_models.SoilTestRecord.sample_date.desc())).all()

@router.post('/api/v1/farms/{farm_id}/soil-tests', status_code=201)
def add_soil_test(farm_id: int, payload: dict, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _owned_farm(db, farm_id, user)
    if payload.get('ph') is not None and not 0 <= float(payload['ph']) <= 14: raise HTTPException(status_code=422, detail='pH must be between 0 and 14')
    row = extra_models.SoilTestRecord(farm_id=farm_id, field_id=payload.get('field_id'), sample_date=date.fromisoformat(payload['sample_date']), testing_source=payload.get('testing_source'), ph=payload.get('ph'), nitrogen=payload.get('nitrogen'), phosphorus=payload.get('phosphorus'), potassium=payload.get('potassium'), nutrient_unit=payload.get('nutrient_unit'), attachment_path=payload.get('attachment_path'), notes=payload.get('notes'))
    if row.field_id is not None:
        linked_field = _owned_field(db, row.field_id, user)
        if linked_field.farm_id != farm_id: raise HTTPException(status_code=422, detail='Field does not belong to this farm')
    db.add(row); db.commit(); db.refresh(row); return row

@router.get('/api/v1/farms/{farm_id}/inputs')
def list_inputs(farm_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _owned_farm(db, farm_id, user)
    return db.scalars(select(extra_models.FarmInputRecord).where(extra_models.FarmInputRecord.farm_id == farm_id).order_by(extra_models.FarmInputRecord.applied_on.desc())).all()

@router.post('/api/v1/farms/{farm_id}/inputs', status_code=201)
def add_input(farm_id: int, payload: dict, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _owned_farm(db, farm_id, user)
    if float(payload.get('quantity', 0)) <= 0 or float(payload.get('cost', 0)) < 0: raise HTTPException(status_code=422, detail='Quantity must be positive and cost non-negative')
    if payload.get('field_id') is not None: _owned_field(db, int(payload['field_id']), user)
    if payload.get('crop_cycle_id') is not None: _owned_cycle(db, int(payload['crop_cycle_id']), user)
    row = extra_models.FarmInputRecord(farm_id=farm_id, field_id=payload.get('field_id'), crop_cycle_id=payload.get('crop_cycle_id'), input_type=payload.get('input_type') or 'other', product_name=payload['product_name'], quantity=payload['quantity'], unit=payload.get('unit') or 'unit', cost=payload.get('cost') or 0, applied_on=date.fromisoformat(payload['applied_on']), inventory_quantity=payload.get('inventory_quantity'), notes=payload.get('notes'))
    db.add(row); db.commit(); db.refresh(row); return row

# ---- Harvest, market price records and sales ----
@router.post('/api/v1/crop-cycles/{cycle_id}/harvests', status_code=201)
def add_harvest(cycle_id: int, payload: dict, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    cycle = _owned_cycle(db, cycle_id, user)
    harvest_date = date.fromisoformat(payload['harvest_date'])
    if harvest_date < cycle.planting_date: raise HTTPException(status_code=422, detail='Harvest date cannot be before planting date')
    if float(payload.get('quantity', 0)) <= 0: raise HTTPException(status_code=422, detail='Harvest quantity must be positive')
    row = extra_models.HarvestRecord(crop_cycle_id=cycle_id, harvest_date=harvest_date, quantity=payload['quantity'], unit=payload.get('unit') or 'kg', quality_grade=payload.get('quality_grade'), storage_location=payload.get('storage_location'), notes=payload.get('notes'))
    cycle.harvest_date = harvest_date; cycle.status = 'completed'
    db.add(row); db.commit(); db.refresh(row); return row

@router.get('/api/v1/crop-cycles/{cycle_id}/harvests')
def list_harvests(cycle_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _owned_cycle(db, cycle_id, user)
    return db.scalars(select(extra_models.HarvestRecord).where(extra_models.HarvestRecord.crop_cycle_id == cycle_id).order_by(extra_models.HarvestRecord.harvest_date.desc())).all()

@router.post('/api/v1/harvests/{harvest_id}/sales', status_code=201)
def add_sale(harvest_id: int, payload: dict, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    harvest = db.get(extra_models.HarvestRecord, harvest_id)
    if not harvest: raise HTTPException(status_code=404, detail='Harvest record not found')
    _owned_cycle(db, harvest.crop_cycle_id, user)
    qty, price = float(payload.get('quantity', 0)), float(payload.get('unit_price', -1))
    if qty <= 0 or price < 0: raise HTTPException(status_code=422, detail='Sale quantity must be positive and unit price non-negative')
    row = extra_models.SaleRecord(harvest_id=harvest_id, sale_date=date.fromisoformat(payload['sale_date']), quantity=qty, unit=payload.get('unit') or harvest.unit, unit_price=price, buyer_name=payload.get('buyer_name'), notes=payload.get('notes'))
    db.add(row); db.commit(); db.refresh(row); return {**{c.name: getattr(row, c.name) for c in row.__table__.columns}, 'gross_sales': round(qty * price, 2)}

@router.get('/api/v1/market-prices')
def list_market_prices(crop: str | None = None, market: str | None = None, location: str | None = None, from_date: date | None = None, to_date: date | None = None, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    q = select(extra_models.MarketPriceRecord)
    if crop: q = q.where(extra_models.MarketPriceRecord.crop_name.ilike(f'%{crop}%'))
    if market: q = q.where(extra_models.MarketPriceRecord.market_name.ilike(f'%{market}%'))
    if location: q = q.where(extra_models.MarketPriceRecord.location.ilike(f'%{location}%'))
    if from_date: q = q.where(extra_models.MarketPriceRecord.price_date >= from_date)
    if to_date: q = q.where(extra_models.MarketPriceRecord.price_date <= to_date)
    return db.scalars(q.order_by(extra_models.MarketPriceRecord.price_date.desc()).limit(500)).all()

@router.post('/api/v1/market-prices', status_code=201)
def add_market_price(payload: dict, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    # Farmer-maintained records are clearly attributed to their source; no values are invented.
    if float(payload.get('price', -1)) < 0: raise HTTPException(status_code=422, detail='Price cannot be negative')
    if not payload.get('source'): raise HTTPException(status_code=422, detail='Source is required')
    row = extra_models.MarketPriceRecord(crop_name=payload['crop_name'], market_name=payload['market_name'], location=payload['location'], price=payload['price'], unit=payload.get('unit') or 'kg', price_date=date.fromisoformat(payload['price_date']), source=payload['source'], is_sample=bool(payload.get('is_sample', False)), created_by=user.id)
    db.add(row); db.commit(); db.refresh(row); return row

@router.get('/api/v1/analytics/summary')
def analytics_summary(farm_id: int | None = None, field_id: int | None = None, crop: str | None = None, from_date: date | None = None, to_date: date | None = None, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    farm_ids_q = select(models.Farm.id).where(models.Farm.owner_id == user.id)
    if farm_id is not None: farm_ids_q = farm_ids_q.where(models.Farm.id == farm_id)
    field_q = select(models.Field.id).where(models.Field.farm_id.in_(farm_ids_q))
    if field_id is not None: field_q = field_q.where(models.Field.id == field_id)
    cycles_q = select(models.CropCycle.id).where(models.CropCycle.field_id.in_(field_q))
    if crop: cycles_q = cycles_q.where(models.CropCycle.crop_name.ilike(f'%{crop}%'))
    cycles = db.scalars(cycles_q).all()
    harvests = db.scalars(select(extra_models.HarvestRecord).where(extra_models.HarvestRecord.crop_cycle_id.in_(cycles), *([extra_models.HarvestRecord.harvest_date >= from_date] if from_date else []), *([extra_models.HarvestRecord.harvest_date <= to_date] if to_date else []))).all() if cycles else []
    inputs = db.scalars(select(extra_models.FarmInputRecord).where(extra_models.FarmInputRecord.farm_id.in_(farm_ids_q), *([extra_models.FarmInputRecord.applied_on >= from_date] if from_date else []), *([extra_models.FarmInputRecord.applied_on <= to_date] if to_date else []))).all()
    irrigation = db.scalars(select(extra_models.IrrigationRecord).where(extra_models.IrrigationRecord.crop_cycle_id.in_(cycles), *([extra_models.IrrigationRecord.irrigation_date >= from_date] if from_date else []), *([extra_models.IrrigationRecord.irrigation_date <= to_date] if to_date else []))).all() if cycles else []
    sales = db.scalars(select(extra_models.SaleRecord).join(extra_models.HarvestRecord).where(extra_models.HarvestRecord.crop_cycle_id.in_(cycles), *([extra_models.SaleRecord.sale_date >= from_date] if from_date else []), *([extra_models.SaleRecord.sale_date <= to_date] if to_date else []))).all() if cycles else []
    return {'crop_cycles': len(cycles), 'harvest_quantity_by_crop': [{'crop': name, 'quantity': sum(float(h.quantity) for h in harvests if db.get(models.CropCycle, h.crop_cycle_id).crop_name == name), 'unit': next((h.unit for h in harvests if db.get(models.CropCycle, h.crop_cycle_id).crop_name == name), 'kg')} for name in sorted({db.get(models.CropCycle, h.crop_cycle_id).crop_name for h in harvests})], 'recorded_input_cost': round(sum(float(x.cost or 0) for x in inputs), 2), 'recorded_gross_sales': round(sum(float(x.quantity) * float(x.unit_price) for x in sales), 2), 'recorded_irrigation_liters': round(sum(float(x.quantity_liters or 0) for x in irrigation if not x.quantity_is_estimated), 2), 'estimated_irrigation_liters': round(sum(float(x.quantity_liters or 0) for x in irrigation if x.quantity_is_estimated), 2), 'note': 'Calculated from recorded entries only. Estimated water is separated from measured/recorded quantities.'}

@router.get('/api/v1/notifications')
def list_notifications(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.scalars(select(extra_models.FarmNotification).where(extra_models.FarmNotification.user_id == user.id).order_by(extra_models.FarmNotification.created_at.desc()).limit(100)).all()

@router.post('/api/v1/notifications', status_code=201)
def create_notification(payload: dict, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    row = extra_models.FarmNotification(user_id=user.id, title=payload['title'], message=payload['message'], due_date=date.fromisoformat(payload['due_date']) if payload.get('due_date') else None, source_type=payload.get('source_type') or 'manual')
    db.add(row); db.commit(); db.refresh(row); return row

@router.patch('/api/v1/notifications/{notification_id}')
def update_notification(notification_id: int, payload: dict, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    row = db.scalar(select(extra_models.FarmNotification).where(extra_models.FarmNotification.id == notification_id, extra_models.FarmNotification.user_id == user.id))
    if not row: raise HTTPException(status_code=404, detail='Notification not found')
    if payload.get('status') not in {'read', 'unread', 'dismissed'}: raise HTTPException(status_code=422, detail='Invalid notification status')
    row.status = payload['status']; db.commit(); db.refresh(row); return row

@router.get('/api/v1/harvests/{harvest_id}/sales')
def list_sales(harvest_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    harvest = db.get(extra_models.HarvestRecord, harvest_id)
    if not harvest: raise HTTPException(status_code=404, detail='Harvest record not found')
    _owned_cycle(db, harvest.crop_cycle_id, user)
    sales = db.scalars(select(extra_models.SaleRecord).where(extra_models.SaleRecord.harvest_id == harvest_id).order_by(extra_models.SaleRecord.sale_date.desc())).all()
    return [{**{c.name: getattr(s, c.name) for c in s.__table__.columns}, 'gross_sales': round(float(s.quantity) * float(s.unit_price), 2)} for s in sales]

@router.post('/api/v1/notifications/generate-task-reminders')
def generate_task_reminders(days: int = 7, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    days = max(1, min(days, 30))
    owned_cycles = select(models.CropCycle.id).join(models.Field).join(models.Farm).where(models.Farm.owner_id == user.id)
    tasks = db.scalars(select(models.FarmTask).where(models.FarmTask.crop_cycle_id.in_(owned_cycles), models.FarmTask.status == 'pending', models.FarmTask.due_date.is_not(None), models.FarmTask.due_date <= date.today() + timedelta(days=days)).order_by(models.FarmTask.due_date)).all()
    created = 0
    for task in tasks:
        title = f'Task due: {task.title}'
        message = f'Task #{task.id} is due on {task.due_date.isoformat()}. {task.description or ""}'.strip()
        exists = db.scalar(select(extra_models.FarmNotification.id).where(extra_models.FarmNotification.user_id == user.id, extra_models.FarmNotification.title == title, extra_models.FarmNotification.message == message))
        if not exists:
            db.add(extra_models.FarmNotification(user_id=user.id, title=title, message=message, due_date=task.due_date, source_type='task')); created += 1
    db.commit()
    return {'created': created, 'checked_tasks': len(tasks), 'days_ahead': days, 'note': 'Task reminders are generated from saved pending tasks; no push/email delivery is configured.'}

