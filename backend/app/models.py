from datetime import datetime, date
from sqlalchemy import String, DateTime, Date, Float, ForeignKey, Text, Boolean, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from sqlalchemy import JSON

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="farmer")
    is_active: Mapped[bool] = mapped_column(
    Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    farms: Mapped[list["Farm"]] = relationship(back_populates="owner", cascade="all, delete-orphan")

class Farm(Base):
    __tablename__ = "farms"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(255))
    area: Mapped[float] = mapped_column(Float)
    area_unit: Mapped[str] = mapped_column(String(20), default="hectare")
    soil_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    owner: Mapped[User] = relationship(back_populates="farms")
    fields: Mapped[list["Field"]] = relationship(back_populates="farm", cascade="all, delete-orphan")

class Field(Base):
    __tablename__ = "fields"
    __table_args__ = (CheckConstraint("area > 0", name="ck_field_area_positive"),)
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    area: Mapped[float] = mapped_column(Float)
    soil_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    irrigation_method: Mapped[str | None] = mapped_column(String(80), nullable=True)
    farm: Mapped[Farm] = relationship(back_populates="fields")
    crop_cycles: Mapped[list["CropCycle"]] = relationship(back_populates="field", cascade="all, delete-orphan")

class CropCycle(Base):
    __tablename__ = "crop_cycles"
    __table_args__ = (CheckConstraint("harvest_date IS NULL OR harvest_date >= planting_date", name="ck_crop_dates"),)
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    crop_name: Mapped[str] = mapped_column(String(100))
    variety: Mapped[str | None] = mapped_column(String(100), nullable=True)
    season: Mapped[str | None] = mapped_column(String(50), nullable=True)
    planting_date: Mapped[date] = mapped_column(Date)
    expected_harvest_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_harvest_quantity: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    expected_harvest_unit: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )
    harvest_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    field: Mapped[Field] = relationship(back_populates="crop_cycles")
    tasks: Mapped[list["FarmTask"]] = relationship(back_populates="crop_cycle", cascade="all, delete-orphan")

class FarmTask(Base):
    __tablename__ = "farm_tasks"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    crop_cycle_id: Mapped[int] = mapped_column(ForeignKey("crop_cycles.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    crop_cycle: Mapped[CropCycle] = relationship(back_populates="tasks")


class SoilTest(Base):
    __tablename__ = "soil_tests"

    __table_args__ = (
        CheckConstraint(
            "ph IS NULL OR (ph >= 0 AND ph <= 14)",
            name="ck_soil_test_ph_range",
        ),
        CheckConstraint(
            "electrical_conductivity IS NULL OR electrical_conductivity >= 0",
            name="ck_soil_test_ec_nonnegative",
        ),
        CheckConstraint(
            "organic_carbon_percent IS NULL OR "
            "(organic_carbon_percent >= 0 AND organic_carbon_percent <= 100)",
            name="ck_soil_test_organic_carbon_range",
        ),
        CheckConstraint(
            "nitrogen IS NULL OR nitrogen >= 0",
            name="ck_soil_test_nitrogen_nonnegative",
        ),
        CheckConstraint(
            "phosphorus IS NULL OR phosphorus >= 0",
            name="ck_soil_test_phosphorus_nonnegative",
        ),
        CheckConstraint(
            "potassium IS NULL OR potassium >= 0",
            name="ck_soil_test_potassium_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    field_id: Mapped[int] = mapped_column(
        ForeignKey("fields.id", ondelete="CASCADE"),
        index=True,
    )

    test_date: Mapped[date] = mapped_column(Date)
    ph: Mapped[float | None] = mapped_column(Float, nullable=True)
    nitrogen: Mapped[float | None] = mapped_column(Float, nullable=True)
    phosphorus: Mapped[float | None] = mapped_column(Float, nullable=True)
    potassium: Mapped[float | None] = mapped_column(Float, nullable=True)

    # The laboratory's reported unit for N, P and K, e.g. mg/kg or kg/ha.
    npk_unit: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # EC is expressed in dS/m; organic carbon is expressed as a percentage.
    electrical_conductivity: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    organic_carbon_percent: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    lab_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    field: Mapped["Field"] = relationship()
    

class WeatherSnapshot(Base):
    __tablename__ = "weather_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"),
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), default="open-meteo")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    payload: Mapped[dict] = mapped_column(JSON)

    farm: Mapped["Farm"] = relationship()

class FarmAdvisorAssignment(Base):
    __tablename__ = "farm_advisor_assignments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), index=True
    )
    advisor_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    assigned_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class AdvisoryRequest(Base):
    __tablename__ = "advisory_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), index=True
    )
    farmer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    advisor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(50), default="general")
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), default="open", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class AdvisorRecommendation(Base):
    __tablename__ = "advisor_recommendations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("advisory_requests.id", ondelete="CASCADE"),
        index=True,
    )
    advisor_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True
    )
    recommendation: Mapped[str] = mapped_column(Text)
    action_items: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[int | None] = mapped_column(nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

# Module J governance models. These map to tables already present in PostgreSQL.
class AdvisorReview(Base):
    __tablename__ = "advisor_reviews"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("advisory_requests.id", ondelete="CASCADE"), index=True
    )
    advisor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    comments: Mapped[str] = mapped_column(Text)
    recommendations: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="reviewed")
    follow_up_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CropCategory(Base):
    __tablename__ = "crop_categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SupportedModelClass(Base):
    __tablename__ = "supported_model_classes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    model_name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IntegrationConfig(Base):
    __tablename__ = "integration_configs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider_type: Mapped[str] = mapped_column(String(80))
    provider_name: Mapped[str] = mapped_column(String(160))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    settings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    secret_env_var: Mapped[str | None] = mapped_column(String(160), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SystemEvent(Base):
    __tablename__ = "system_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(20), default="info")
    source: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30), default="open")
    message: Mapped[str] = mapped_column(Text)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
