from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field as PydanticField, model_validator
from typing import Literal

class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = PydanticField(min_length=2, max_length=120)
    password: str = PydanticField(min_length=10, max_length=128)

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    full_name: str
    role: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class FarmCreate(BaseModel):
    name: str = PydanticField(min_length=2, max_length=120)
    location: str = PydanticField(min_length=2, max_length=255)
    area: float = PydanticField(gt=0)
    area_unit: str = PydanticField(default="hectare", max_length=20)
    soil_type: str | None = None
    latitude: float | None = PydanticField(default=None, ge=-90, le=90)
    longitude: float | None = PydanticField(default=None, ge=-180, le=180)

class FarmOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    location: str
    area: float
    area_unit: str
    soil_type: str | None
    latitude: float | None
    longitude: float | None
    created_at: datetime

class FieldCreate(BaseModel):
    name: str = PydanticField(min_length=1, max_length=120)
    area: float = PydanticField(gt=0)
    soil_type: str | None = None
    irrigation_method: str | None = None

class FieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    farm_id: int
    name: str
    area: float
    soil_type: str | None
    irrigation_method: str | None

class CropCycleCreate(BaseModel):
    crop_name: str = PydanticField(min_length=1, max_length=100)
    variety: str | None = None
    season: str | None = None
    planting_date: date
    expected_harvest_date: date | None = None
    expected_harvest_quantity: float | None = PydanticField(default=None, gt=0)
    expected_harvest_unit: str | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.expected_harvest_date and self.expected_harvest_date < self.planting_date:
            raise ValueError("Expected harvest date cannot be before planting date")
        return self

class CropCycleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    field_id: int
    crop_name: str
    variety: str | None
    season: str | None
    planting_date: date
    expected_harvest_date: date | None
    expected_harvest_quantity: float | None
    expected_harvest_unit: str | None
    harvest_date: date | None
    status: str

class TaskCreate(BaseModel):
    title: str = PydanticField(min_length=2, max_length=160)
    description: str | None = None
    due_date: date | None = None

class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    crop_cycle_id: int
    title: str
    description: str | None
    due_date: date | None
    status: str
    created_at: datetime


class SoilTestCreate(BaseModel):
    test_date: date
    ph: float | None = PydanticField(default=None, ge=0, le=14)
    nitrogen: float | None = PydanticField(default=None, ge=0)
    phosphorus: float | None = PydanticField(default=None, ge=0)
    potassium: float | None = PydanticField(default=None, ge=0)
    npk_unit: str | None = PydanticField(default=None, min_length=1, max_length=30)
    electrical_conductivity: float | None = PydanticField(default=None, ge=0)
    organic_carbon_percent: float | None = PydanticField(
        default=None, ge=0, le=100
    )
    lab_name: str | None = PydanticField(default=None, max_length=160)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_measurements(self):
        measurements = (
            self.ph,
            self.nitrogen,
            self.phosphorus,
            self.potassium,
            self.electrical_conductivity,
            self.organic_carbon_percent,
        )

        if all(value is None for value in measurements):
            raise ValueError("Provide at least one actual soil measurement")

        has_npk = any(
            value is not None
            for value in (self.nitrogen, self.phosphorus, self.potassium)
        )

        if has_npk and not self.npk_unit:
            raise ValueError(
                "npk_unit is required when nitrogen, phosphorus, "
                "or potassium is provided"
            )

        return self


class SoilTestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    field_id: int
    test_date: date
    ph: float | None
    nitrogen: float | None
    phosphorus: float | None
    potassium: float | None
    npk_unit: str | None
    electrical_conductivity: float | None
    organic_carbon_percent: float | None
    lab_name: str | None
    notes: str | None
    created_at: datetime

class RoleUpdate(BaseModel):
    role: Literal["farmer", "advisor", "farm_manager", "admin"]


class AdvisorAssignmentCreate(BaseModel):
    farm_id: int = PydanticField(gt=0)
    advisor_id: int = PydanticField(gt=0)


class AdvisorAssign(BaseModel):
    advisor_id: int = PydanticField(gt=0)


class AdvisoryRequestCreate(BaseModel):
    farm_id: int = PydanticField(gt=0)
    subject: str = PydanticField(min_length=3, max_length=160)
    description: str = PydanticField(min_length=10, max_length=5000)
    category: str = PydanticField(default="general", min_length=1, max_length=50)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"


class AdvisoryStatusUpdate(BaseModel):
    status: Literal["open", "in_progress", "resolved", "closed"]


class AdvisoryRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    farm_id: int
    farmer_id: int
    advisor_id: int | None
    subject: str
    category: str
    priority: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime


class AdvisorRecommendationCreate(BaseModel):
    recommendation: str = PydanticField(
        min_length=10, max_length=10000
    )
    action_items: list[str] = PydanticField(default_factory=list, max_length=50)


class AdvisorRecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    advisor_id: int
    recommendation: str
    action_items: list[str]
    created_at: datetime