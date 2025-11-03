
import json
from src.core.tools import InsuranceVerifier, BookingStore

def test_insurance_acceptance():
    iv = InsuranceVerifier()
    out = iv.verify(insurance_provider="BlueShield", plan_type="PPO", verification_topic="acceptance")
    assert out["accepted"] is True

def test_insurance_copay():
    iv = InsuranceVerifier()
    out = iv.verify(insurance_provider="BlueShield", plan_type="HMO", verification_topic="copay", procedure_code="99213")
    assert out["copay"] == 20

def test_booking_basic():
    bs = BookingStore()
    out = bs.check_and_hold(patient_name="John Doe", doctor_preference="smith", time_preference="morning")
    assert out["status"] in ("proposed", "unavailable")
