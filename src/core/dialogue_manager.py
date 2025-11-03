
import json
from pathlib import Path

from .config import settings

def load_system_prompt() -> str:
    p = Path(settings.PROMPTS_DIR) / "system.md"
    return p.read_text(encoding="utf-8")

def tool_specs():
    """Return OpenAI tool/function specs for tool-calling."""
    return [
        {
            "type": "function",
            "function": {
                "name": "verify_insurance",
                "description": "Verify insurance acceptance, copay, or prior auth for a given provider/plan and optional procedure code.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "patient_name": {"type": "string", "description": "Caller name"},
                        "insurance_provider": {"type": "string", "enum": ["BlueShield", "Aetna", "United", "Cigna"]},
                        "plan_type": {"type": "string", "enum": ["PPO", "HMO", "EPO"]},
                        "verification_topic": {"type": "string", "enum": ["acceptance", "copay", "prior_auth", "eligibility"]},
                        "procedure_code": {"type": "string", "description": "CPT-like code, e.g., 99213 or 70551"},
                        "member_id": {"type": "string", "description": "Optional demo member id"}
                    },
                    "required": ["insurance_provider", "plan_type", "verification_topic"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "check_calendar_and_hold_slot",
                "description": "Suggest an appointment slot and hold it temporarily for confirmation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "patient_name": {"type": "string"},
                        "doctor_preference": {"type": "string", "description": "smith or lee"},
                        "date_preference": {"type": "string", "description": "YYYY-MM-DD or free-form date range"},
                        "time_preference": {"type": "string", "enum": ["morning", "afternoon"], "description": "or specific time like 10:00"},
                        "visit_reason": {"type": "string"}
                    },
                    "required": ["patient_name"]
                }
            }
        }
    ]
