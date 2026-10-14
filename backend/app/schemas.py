from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VitalInput(BaseModel):
    """One synthetic or manually entered observation set."""

    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(default="DEMO-001", min_length=1, max_length=64)
    age: int = Field(ge=18, le=110)
    heart_rate: float = Field(ge=20, le=250)
    spo2: float = Field(ge=50, le=100)
    systolic_bp: float = Field(ge=50, le=280)
    diastolic_bp: float = Field(ge=20, le=180)
    temperature: float = Field(ge=30, le=45)
    respiratory_rate: float = Field(ge=3, le=70)

    @model_validator(mode="after")
    def validate_blood_pressure(self):
        if self.diastolic_bp >= self.systolic_bp:
            raise ValueError("diastolic_bp must be lower than systolic_bp")
        return self


class RiskFactor(BaseModel):
    feature: str
    observed_value: float
    direction: Literal["increases-risk", "decreases-risk"]
    explanation: str


class RiskPrediction(BaseModel):
    patient_id: str
    observation_id: int | None = None
    created_at: str | None = None
    risk_score: int = Field(ge=0, le=100)
    risk_level: Literal["low", "moderate", "high", "critical"]
    model_probability: float = Field(ge=0, le=1)
    factors: list[RiskFactor]
    model_version: str
    demo_only: Literal[True] = True
    disclaimer: str = (
        "Synthetic demonstration only. Not clinically validated and not for "
        "diagnosis, triage, or treatment decisions."
    )

