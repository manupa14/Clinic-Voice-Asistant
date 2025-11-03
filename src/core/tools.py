import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import settings
from .utils import load_json
from .schemas import (
    InsuranceInput,
    InsuranceOutput,
    AppointmentInput,      # kept for type consistency if you later use it
    AppointmentOutput,
    Slot,
)

DATA_DIR = Path(settings.DATA_DIR)

# Month map for natural-language date parsing
MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5,
    "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12
}


# ----------------------------- Insurance -----------------------------

class InsuranceVerifier:
    def __init__(self):
        self.table = load_json(str(DATA_DIR / "insurance_table.json"))
        # Optional; if missing, lookups will just return None/unknown gracefully
        self.procedures = load_json(str(DATA_DIR / "procedures.json"))

    def verify(self, **kwargs) -> Dict:
        """Simulated insurance verification."""
        args = InsuranceInput(**kwargs)
        provider = args.insurance_provider
        plan = args.plan_type.upper()
        topic = args.verification_topic.lower()

        acceptance = self.table.get("acceptance", {}).get(provider, {})
        accepted = bool(acceptance.get(plan, False))

        copay = None
        prior_auth = None
        notes: List[str] = []

        if topic in ("acceptance", "eligibility"):
            notes.append(
                f"Provider '{provider}' with plan '{plan}' is "
                f"{'accepted' if accepted else 'not accepted'}."
            )

        if topic == "copay":
            proc_code = args.procedure_code or self.table.get("defaults", {}).get("routine_visit_code", "99213")
            proc = (self.procedures or {}).get(proc_code, {})
            copay_map = proc.get("copay", {})
            copay = float(copay_map.get(plan)) if plan in copay_map else None
            if copay is None:
                notes.append(f"No copay rule for {plan} on {proc_code}.")

        if topic == "prior_auth":
            proc_code = args.procedure_code or self.table.get("defaults", {}).get("mri_code", "70551")
            proc = (self.procedures or {}).get(proc_code, {})
            pa_map = proc.get("prior_auth", {})
            prior_auth = bool(pa_map.get(plan)) if plan in pa_map else None
            if prior_auth is None:
                notes.append(f"No prior auth rule for {plan} on {proc_code}.")

        if not accepted:
            notes.append("Plan is out-of-network or not accepted.")

        out = InsuranceOutput(
            accepted=accepted,
            copay=copay,
            prior_auth_required=prior_auth,
            notes=" ".join(notes) if notes else None,
        )
        return json.loads(out.model_dump_json())


# ----------------------------- Scheduling -----------------------------

class BookingStore:
    """Simple in-memory booking/hold store over a static schedule."""
    def __init__(self):
        self.schedule: Dict = load_json(str(DATA_DIR / "schedule.json"))
        self.doctors: Dict[str, Dict] = {d["id"]: d for d in self.schedule.get("doctors", [])}
        self.holds: set[str] = set()  # set of start_iso strings considered held for this process

    @staticmethod
    def _next_weekday(now: datetime, target_idx: int) -> datetime:
        """Mon=0..Sun=6; return the *next* occurrence (not 'today')."""
        days_ahead = (target_idx - now.weekday()) % 7
        return now + timedelta(days=days_ahead or 7)

    @classmethod
    def _parse_date_window(cls, pref: Optional[str], now: datetime) -> Tuple[datetime, datetime]:
        """
        Return (start, end_exclusive).
        Accepts: ISO 'YYYY-MM-DD', 'this week', 'next week', weekday names,
                 'November 6' (w/ or w/o comma/year), '11/06' (assume MM/DD).
        Default: [now, now+7d).
        """
        if not pref:
            return now, now + timedelta(days=7)

        p = pref.strip().lower()
        p = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', p)  # '6th' -> '6'

        # ISO YYYY-MM-DD
        m = re.search(r'(\d{4})-(\d{2})-(\d{2})', p)
        if m:
            y, mo, d = map(int, m.groups())
            day = datetime(y, mo, d)
            start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            return start, start + timedelta(days=1)

        # this week / next week
        if "this week" in p:
            start = now
            return start, start + timedelta(days=7)
        if "next week" in p:
            start = now + timedelta(days=7)
            return start, start + timedelta(days=7)

        # weekday name -> next occurrence
        weekdays = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                    "friday": 4, "saturday": 5, "sunday": 6}
        for name, idx in weekdays.items():
            if name in p:
                day = cls._next_weekday(now, idx)
                start = day.replace(hour=0, minute=0, second=0, microsecond=0)
                return start, start + timedelta(days=1)

        # "November 6" [optional , YYYY]
        m = re.search(r'([a-z]+)\s+(\d{1,2})(?:,\s*(\d{4}))?', p)
        if m:
            mon_str = m.group(1)
            if mon_str in MONTHS:
                mo = MONTHS[mon_str]
                d = int(m.group(2))
                y = int(m.group(3)) if m.group(3) else now.year
                day = datetime(y, mo, d)
                start = day.replace(hour=0, minute=0, second=0, microsecond=0)
                return start, start + timedelta(days=1)

        # Numeric "11/06[/YYYY]" assume MM/DD
        m = re.search(r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?', p)
        if m:
            mo = int(m.group(1))
            d = int(m.group(2))
            y = int(m.group(3)) if m.group(3) else now.year
            if y < 100:
                y += 2000
            day = datetime(y, mo, d)
            start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            return start, start + timedelta(days=1)

        # fallback
        return now, now + timedelta(days=7)

    @staticmethod
    def _time_window(pref: Optional[str]) -> Tuple[int, int]:
        """Return (start_hour, end_hour_exclusive). Defaults 08–20."""
        if not pref:
            return 8, 20
        p = pref.lower().strip()
        if "morning" in p:
            return 8, 12
        if "afternoon" in p:
            return 12, 16
        if "evening" in p:
            return 16, 20
        # "2pm", "14:00"
        m = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', p)
        if m:
            h = int(m.group(1))
            mer = m.group(3)
            if mer:
                mer = mer.lower()
                if mer == "pm" and h < 12:
                    h += 12
                if mer == "am" and h == 12:
                    h = 0
            return h, min(h + 1, 24)
        return 8, 20

    def _slots_for_doctor(self, doctor_id: str) -> List[str]:
        doc = self.doctors.get(doctor_id, {})
        return list(doc.get("slots", []))

    def _slot_to_obj(self, doctor_id: str, start_iso: str, duration_min: int = 30) -> Slot:
        start_dt = datetime.fromisoformat(start_iso)
        end_dt = start_dt + timedelta(minutes=duration_min)
        return Slot(
            doctor_id=doctor_id,
            doctor_name=self.doctors[doctor_id]["name"],
            start_iso=start_dt.isoformat(timespec="seconds"),
            end_iso=end_dt.isoformat(timespec="seconds"),
        )

    def _hold_slot(self, slot_obj: Dict, patient_name: str) -> str:
        """
        Minimal hold mechanism: mark start_iso as held; return a simple hold_id.
        (In a real system you’d generate a GUID and set a TTL.)
        """
        start_iso = slot_obj["start_iso"]
        self.holds.add(start_iso)
        return start_iso  # act as a hold_id

    def check_and_hold(
        self,
        patient_name: Optional[str] = None,
        doctor_preference: Optional[str] = None,
        date_preference: Optional[str] = None,
        time_preference: Optional[str] = None,
        confirm: bool = False,
        duration_minutes: int = 30,
    ) -> Dict:
        """
        List or hold appointment times.
        - confirm=False: list up to 3 matching options (no hold)
        - confirm=True: require patient_name; hold first match and return alternatives
        Filtering NEVER goes earlier than the requested date window; if none match,
        propose forward alternatives (on/after the window end).
        """
        now = datetime.now()
        win_start, win_end = self._parse_date_window(date_preference, now)
        hour_start, hour_end = self._time_window(time_preference)

        # Choose candidate doctors (id or name substring)
        def _doc_ok(doc: Dict) -> bool:
            if not doctor_preference:
                return True
            q = doctor_preference.strip().lower()
            return q in doc["id"].lower() or q in doc["name"].lower()

        # Gather matching candidates ON/AFTER requested window only
        candidates: List[Dict] = []
        for doc in filter(_doc_ok, self.doctors.values()):
            did = doc["id"]
            for iso in doc.get("slots", []):
                dt = datetime.fromisoformat(iso)
                if not (win_start <= dt < win_end):
                    continue
                if not (hour_start <= dt.hour < hour_end):
                    continue
                if iso in self.holds:
                    continue
                candidates.append(
                    {
                        "doctor_id": did,
                        "doctor_name": doc["name"],
                        "start_iso": dt.isoformat(timespec="seconds"),
                        "end_iso": (dt + timedelta(minutes=duration_minutes)).isoformat(timespec="seconds"),
                    }
                )

        candidates.sort(key=lambda s: s["start_iso"])

        if not candidates:
            # Forward-only broadening (never earlier than the requested window)
            forward: List[Dict] = []
            for doc in filter(_doc_ok, self.doctors.values()):
                did = doc["id"]
                for iso in doc.get("slots", []):
                    dt = datetime.fromisoformat(iso)
                    if dt >= win_end and iso not in self.holds:
                        forward.append(
                            {
                                "doctor_id": did,
                                "doctor_name": doc["name"],
                                "start_iso": dt.isoformat(timespec="seconds"),
                                "end_iso": (dt + timedelta(minutes=duration_minutes)).isoformat(timespec="seconds"),
                            }
                        )
            forward.sort(key=lambda s: s["start_iso"])
            return {"status": "no_availability", "alternatives": forward[:3]}

        if not confirm:
            return {"status": "options", "slots": candidates[:3]}

        # confirm=True
        if not patient_name:
            return {
                "status": "error",
                "missing": ["patient_name"],
                "message": "patient_name required to hold a slot",
            }

        proposed = candidates[0]
        hold_id = self._hold_slot(proposed, patient_name)
        alternatives = candidates[1:4]

        out = AppointmentOutput(
            status="proposed",
            proposed_slot=Slot(
                doctor_id=proposed["doctor_id"],
                doctor_name=proposed["doctor_name"],
                start_iso=proposed["start_iso"],
                end_iso=proposed["end_iso"],
            ),
            alternatives=[
                Slot(
                    doctor_id=a["doctor_id"],
                    doctor_name=a["doctor_name"],
                    start_iso=a["start_iso"],
                    end_iso=a["end_iso"],
                )
                for a in alternatives
            ],
            hold_id=hold_id,
        )
        return json.loads(out.model_dump_json())
