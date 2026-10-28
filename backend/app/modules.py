"""Additive ORM models for AgroVision crop, irrigation, input, harvest and notification modules."""
from datetime import datetime, date
from sqlalchemy import String, DateTime, Date, Float, ForeignKey, Text, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class CropObservation(Base):
    __tablename__ = 'crop_observations'
    id: Mapped[int] = mapped_column(primary_key=True)
    crop_cycle_id: Mapped[int] = mapped_column(ForeignKey('crop_cycles.id', ondelete='CASCADE'), index=True)
    observation_type: Mapped[str] = mapped_column(String(40), default='note')
    observed_on: Mapped[date] = mapped_column(Date, default=date.today)
    growth_stage: Mapped[str | None] = mapped_column(String(80), nullable=True)
    germination_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class IrrigationRecord(Base):
    __tablename__ = 'irrigation_records'
    id: Mapped[int] = mapped_column(primary_key=True)
    crop_cycle_id: Mapped[int] = mapped_column(ForeignKey('crop_cycles.id', ondelete='CASCADE'), index=True)
    irrigation_date: Mapped[date] = mapped_column(Date, default=date.today)
    method: Mapped[str] = mapped_column(String(80))
    water_source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    soil_moisture_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity_liters: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity_is_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    crop_stage: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class IrrigationRecommendation(Base):
    __tablename__ = 'irrigation_recommendations'
    id: Mapped[int] = mapped_column(primary_key=True)
    crop_cycle_id: Mapped[int] = mapped_column(ForeignKey('crop_cycles.id', ondelete='CASCADE'), index=True)
    status: Mapped[str] = mapped_column(String(20), default='suggested')
    recommended_on: Mapped[date] = mapped_column(Date, default=date.today)
    suggested_task: Mapped[str] = mapped_column(String(160))
    reason: Mapped[str] = mapped_column(Text)
    inputs_json: Mapped[str] = mapped_column(Text)
    estimated_water_liters: Mapped[float | None] = mapped_column(Float, nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey('farm_tasks.id', ondelete='SET NULL'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class SoilTestRecord(Base):
    __tablename__ = 'soil_test_records'
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey('farms.id', ondelete='CASCADE'), index=True)
    field_id: Mapped[int | None] = mapped_column(ForeignKey('fields.id', ondelete='SET NULL'), nullable=True, index=True)
    sample_date: Mapped[date] = mapped_column(Date)
    testing_source: Mapped[str | None] = mapped_column(String(160), nullable=True)
    ph: Mapped[float | None] = mapped_column(Float, nullable=True)
    nitrogen: Mapped[float | None] = mapped_column(Float, nullable=True)
    phosphorus: Mapped[float | None] = mapped_column(Float, nullable=True)
    potassium: Mapped[float | None] = mapped_column(Float, nullable=True)
    nutrient_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    attachment_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class FarmInputRecord(Base):
    __tablename__ = 'farm_input_records'
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey('farms.id', ondelete='CASCADE'), index=True)
    field_id: Mapped[int | None] = mapped_column(ForeignKey('fields.id', ondelete='SET NULL'), nullable=True)
    crop_cycle_id: Mapped[int | None] = mapped_column(ForeignKey('crop_cycles.id', ondelete='SET NULL'), nullable=True, index=True)
    input_type: Mapped[str] = mapped_column(String(40))
    product_name: Mapped[str] = mapped_column(String(160))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(40))
    cost: Mapped[float] = mapped_column(Float, default=0)
    applied_on: Mapped[date] = mapped_column(Date)
    inventory_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class MarketPriceRecord(Base):
    __tablename__ = 'market_price_records'
    id: Mapped[int] = mapped_column(primary_key=True)
    crop_name: Mapped[str] = mapped_column(String(100), index=True)
    market_name: Mapped[str] = mapped_column(String(160), index=True)
    location: Mapped[str] = mapped_column(String(160))
    price: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(40))
    price_date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(200))
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class HarvestRecord(Base):
    __tablename__ = 'harvest_records'
    id: Mapped[int] = mapped_column(primary_key=True)
    crop_cycle_id: Mapped[int] = mapped_column(ForeignKey('crop_cycles.id', ondelete='CASCADE'), index=True)
    harvest_date: Mapped[date] = mapped_column(Date)
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(40))
    quality_grade: Mapped[str | None] = mapped_column(String(80), nullable=True)
    storage_location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class SaleRecord(Base):
    __tablename__ = 'sale_records'
    id: Mapped[int] = mapped_column(primary_key=True)
    harvest_id: Mapped[int] = mapped_column(ForeignKey('harvest_records.id', ondelete='CASCADE'), index=True)
    sale_date: Mapped[date] = mapped_column(Date)
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(40))
    unit_price: Mapped[float] = mapped_column(Float)
    buyer_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class FarmNotification(Base):
    __tablename__ = 'farm_notifications'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='unread')
    source_type: Mapped[str] = mapped_column(String(40), default='task')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
