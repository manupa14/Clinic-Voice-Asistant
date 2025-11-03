from typing import Dict, List, Tuple, Optional
import json
from openai import OpenAI
from .config import settings
from .dialogue_manager import tool_specs, load_system_prompt



def _trim_messages(messages: List[Dict], max_pairs: int = 3) -> List[Dict]:
    """Keep system + last N pairs to limit latency/cost."""
    if not messages:
        return messages
    sys = messages[:1] if messages[0].get("role") == "system" else []
    rest = [m for m in messages if m.get("role") != "system"]
    return sys + rest[-2 * max_pairs:]


class LLMOrchestrator:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=45, max_retries=2)
        self.tools = tool_specs()
        self.system_prompt = load_system_prompt()
        self._max_out_tokens = int(getattr(settings, "MAX_COMPLETION_TOKENS", 180))

    def _create(self, **kwargs):

        params = {**kwargs, **self._token_kwargs()}
        try:
            return self.client.chat.completions.create(**params)
        except Exception as e:
            s = str(e)
            # swap param and retry once
            if "max_tokens" in s and "max_completion_tokens" in s:
                params.pop("max_tokens", None)
                params["max_completion_tokens"] = self._max_out_tokens
                return self.client.chat.completions.create(**params)
            if "max_completion_tokens" in s and "max_tokens" in s:
                params.pop("max_completion_tokens", None)
                params["max_tokens"] = self._max_out_tokens
                return self.client.chat.completions.create(**params)
            raise

    def _token_kwargs(self) -> dict:

        m = settings.OPENAI_CHAT_MODEL.lower()
        if any(tag in m for tag in ["gpt-5", "4.1", "omni", "o4"]):
            return {"max_completion_tokens": self._max_out_tokens}
        return {"max_tokens": self._max_out_tokens}


    def bootstrap_messages(self) -> List[Dict]:
        return [{"role": "system", "content": self.system_prompt}]

    # --------------------- helpers to verbalize tool payloads ---------------------

    @staticmethod
    def _verbalize_schedule(payload: Dict) -> str:
        if not payload:
            return "I couldn’t retrieve availability just now. Want me to try again?"
        st = payload.get("status")
        if st == "options":
            slots = payload.get("slots", [])[:3]
            if not slots:
                return "No matching times. Want me to broaden the search?"
            lines = [
                f"{s['start_iso'].replace('T', ' ').replace(':00', ':00')} with {s['doctor_name']}"
                for s in slots
            ]
            return "Here are available times:\n- " + "\n- ".join(lines) + "\n\nWould you like me to hold one?"
        if st == "proposed":
            p = payload.get("proposed_slot")
            if not p:
                return "I found a time. Should I book it?"
            start = p["start_iso"].replace("T", " ").replace(":00", ":00")
            doc = p["doctor_name"]
            return f"I’ve held {start} with {doc}. Should I confirm this appointment?"
        if st == "no_availability":
            alts = payload.get("alternatives", [])[:3]
            if not alts:
                return "No availability in that window. Want me to search other days?"
            lines = [
                f"{s['start_iso'].replace('T', ' ').replace(':00', ':00')} with {s['doctor_name']}"
                for s in alts
            ]
            return "Nothing there, but next available is:\n- " + "\n- ".join(lines) + "\n\nInterested in one of these?"
        if st == "error":
            missing = ", ".join(payload.get("missing", [])) or "details"
            return f"I need {missing} before I can check. What should I use?"
        return "I couldn’t retrieve availability just now."

    @staticmethod
    def _verbalize_insurance(payload: Dict) -> str:
        if not payload:
            return "I couldn’t verify that right now."
        parts = []
        if "accepted" in payload:
            parts.append("Accepted" if payload["accepted"] else "Not accepted")
        if payload.get("copay") is not None:
            parts.append(f"Copay ${payload['copay']:.0f}")
        if payload.get("prior_auth_required") is not None:
            parts.append("PA required" if payload["prior_auth_required"] else "No PA required")
        if payload.get("notes"):
            parts.append(payload["notes"])
        return "; ".join(parts) or "Done."

    # ------------------------------ main turn loop ------------------------------

    def run_turn(
        self,
        messages: List[Dict],
        user_text: str,
        tool_runtime: Dict[str, callable],
    ) -> Tuple[str, Dict]:
        # 1) add user turn
        messages.append({"role": "user", "content": user_text})

        # 2) first call: model may decide to call tools
        first = self.client.chat.completions.create(
            model=settings.OPENAI_CHAT_MODEL,
            messages=_trim_messages(messages),
            tools=self.tools,
            tool_choice="auto",
        )
        msg = first.choices[0].message

        tool_info: Dict[str, Dict] = {}

        # 3) If tools requested, append the assistant tool-call message, then run tools
        if getattr(msg, "tool_calls", None):
            # IMPORTANT: do not surface msg.content (it may contain “Calling tool…” narration)
            assistant_with_calls = {
                "role": "assistant",
                "content": None,  # suppress narration
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
            messages.append(assistant_with_calls)

            # Execute each tool and append `role:tool` messages
            for tc in msg.tool_calls:
                name = tc.function.name
                args = {}
                try:
                    if tc.function.arguments:
                        args = json.loads(tc.function.arguments)
                except Exception as e:
                    args = {"_parse_error": str(e)}
                if name not in tool_runtime:
                    result = {"status": "error", "message": f"Tool {name} not implemented"}
                else:
                    try:
                        result = tool_runtime[name](**args)
                    except Exception as e:
                        result = {"status": "error", "message": f"{type(e).__name__}: {e}"}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": name,
                        "content": json.dumps(result),
                    }
                )
                tool_info[name] = result

            # 4) FAST-PATHS: if we just used scheduler or insurance, format reply here (skip second LLM)
            if "check_calendar_and_hold_slot" in tool_info:
                text = self._verbalize_schedule(tool_info["check_calendar_and_hold_slot"])
                messages.append({"role": "assistant", "content": text})
                return text, tool_info

            if "verify_insurance" in tool_info:
                text = self._verbalize_insurance(tool_info["verify_insurance"])
                messages.append({"role": "assistant", "content": text})
                return text, tool_info

            # 5) Fallback: second call to let the model compose a reply using tool JSON
            second = self.client.chat.completions.create(
                model=settings.OPENAI_CHAT_MODEL,
                messages=_trim_messages(messages),
            )
            final_msg = second.choices[0].message
            final_text = final_msg.content or ""
            messages.append({"role": "assistant", "content": final_text})
            return final_text, tool_info

        # 6) No tools requested: return the assistant text directly
        text = msg.content or ""
        messages.append({"role": "assistant", "content": text})
        return text, tool_info
