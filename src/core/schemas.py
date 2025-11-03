
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

# ---- Insurance tool ----
class InsuranceInput(BaseModel):
    patient_name: Optional[str] = Field(None, description="Caller name")
    insurance_provider: str = Field(..., description="Provider, e.g., BlueShield, Aetna, United, Cigna")
    plan_type: str = Field(..., description="PPO, HMO, or EPO")
    verification_topic: str = Field(..., description="acceptance | copay | prior_auth | eligibility")
    procedure_code: Optional[str] = Field(None, description="Optional CPT-like code, e.g., 99213 or 70551")
    member_id: Optional[str] = Field(None, description="Optional demo member id")

class InsuranceOutput(BaseModel):
    accepted: bool
    copay: Optional[float] = None
    prior_auth_required: Optional[bool] = None
    notes: Optional[str] = None

# ---- Appointment tool ----
class AppointmentInput(BaseModel):
    patient_name: str
    doctor_preference: Optional[str] = Field(None, description="e.g., smith or lee")
    date_preference: Optional[str] = Field(None, description="YYYY-MM-DD or a date range string")
    time_preference: Optional[str] = Field(None, description="morning | afternoon | specific time like 10:00")
    visit_reason: Optional[str] = None

class Slot(BaseModel):
    doctor_id: str
    doctor_name: str
    start_iso: str
    end_iso: str

class AppointmentOutput(BaseModel):
    status: str  # "proposed" or "booked" or "unavailable"
    proposed_slot: Optional[Slot] = None
    alternatives: Optional[List[Slot]] = None
    notes: Optional[str] = None
