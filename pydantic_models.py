from datetime import datetime
from pydantic import BaseModel, Field, validator


class WorkerBase(BaseModel):
    first_name: str
    last_name: str
    surname: str


class WorkerWithPrediction(WorkerBase):
    stress_level: str


class WorkerWithHistory(WorkerBase):
    mental_health_history: bool


class WorkerWithFeatures(WorkerWithHistory):
    info_date: datetime

    @validator("info_date", pre=True)
    def parse_datetime(cls, value):
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")

    anxiety: int = Field(ge=0, le=21)
    self_esteem: int = Field(ge=0, le=30)
    depression: int = Field(ge=0, le=27)
    headache: int = Field(ge=0, le=5)
    blood_pressure: int = Field(ge=1, le=3, default=1)
    sleep_quality: int = Field(ge=0, le=5)
    breathing_problem: int = Field(ge=0, le=5)
    noise_level: int = Field(ge=0, le=5)
    social_support: int = Field(ge=0, le=3)
    extracurricular_activities: int = Field(ge=0, le=5)
