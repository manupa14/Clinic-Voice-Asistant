# Health voice Assistant — System Design

> Scope: a voice-enabled front‑desk prototype that can **schedule** (list/hold slots), **verify insurance**, and answer **clinic FAQs**. Voice is optional (text also works). All backends are mocked with JSON files.

---

## 1) Architecture Overview

**High‑level flow**

```
User (mic or text)
   │
   ├─► Gradio UI (app/ui_gradio.py)
   │     • process_audio(): mic → Whisper STT → text
   │     • process_text(): orchestrates one LLM turn
   │     • keeps session 'state' (chat, transcript, messages)
   │
   ├─► LLM Orchestrator (core/llm.py)
   │     • sends chat messages + tool specs to OpenAI
   │     • if 'tool_calls' returned → runs Python tools → sends result back
   │     • returns final assistant text (and tool debug info)
   │
   ├─► Tools (core/tools.py)
   │     • InsuranceVerifier.verify(...): reads 'insurance_table.json' (+ optional 'procedures.json')
   │     • BookingStore.check_and_hold(...): reads 'schedule.json', filters, can hold a slot
   │
   └─► TTS (core/voice.py) → ElevenLabs
         • synthesizes assistant text to mp3; UI autoplays

```

**State & messaging**

- 'gr.State()' holds a dict per browser session:  
  '{"messages": [...], "chat": [(u,b)...], "transcript": [...], "holds": {...}}'
- We maintain OpenAI chat history in '"messages"'. For voice UX we keep a human‑readable '"chat"' (list of '(user, assistant)' pairs) and a full '"transcript"' (with tool results) for export.
- **Two‑call tool handshake** (OpenAI function/tool calling):
  1) Call #1: model may return 'tool_calls=[{name, arguments}]'.
  2) We append that assistant message (with 'tool_calls'), execute the mapped Python function(s), and append 'role:"tool"' messages with JSON results.
  3) Call #2: model writes the final, user‑facing message using the tool JSON.
- **Greeting**: on app load we inject a hardcoded voice greeting so the user doesn’t have to speak first.

## 2) Tech Stack & Tools (choices & rationale)

**UI:** Gradio 5.x  
- Fast to prototype mic+chat UIs; simple event wiring ('.submit', '.stop_recording').
- Alternatives considered: Streamlit (poorer mic ergonomics), custom React (overkill for the take‑home).

**LLM:** OpenAI Chat (default: 'gpt‑4.1‑mini'; also tested 'gpt‑4o‑mini', 'gpt‑4.1‑nano')  
- **Why:** good function/tool-calling behavior with minimal glue code (no need for LangChain). Prior experience working with it, simple, reliable.
- **Trade‑off:** latency varies under load; I accept 6–7s turns for the prototype.

**STT:** OpenAI Whisper ('whisper-1') via OpenAI Python client  
- **Why:** reliable accuracy for short utterances; simple API.  
- **Trade‑off:** adds ~0.3–1.0s; acceptable for the demo.

**TTS:** ElevenLabs (REST)  
- **Why:** natural output; easy HTTP integration with 'requests'.  
- **Note:** we call the REST API directly (no SDK import), which keeps deps small.

**Config:** 'python-dotenv'; Settings object ('core/config.py') validates required secrets on boot.

**Data:** local JSON fixtures in 'data/'  
- 'schedule.json' (doctors & slots), 'insurance_table.json' (accepted providers/plans).  
- Optional 'procedures.json' (CPT defaults) if we want crisp copay/PA answers.

**Not used by design**  
- No vector DB/RAG (FAQ is tiny; we inline into the system prompt).  
- No LangChain/LLM framework (tool calling is implemented directly).  
- No real calendar/insurance APIs (time-boxed; mocked with JSON).
---

## 3) Prompting Strategy

**System prompt (summary of rules)**

- Persona: concise, courteous clinic front desk assistant.  
- Scope: appointments, insurance verification, FAQs; **no medical advice**; escalate emergencies.  
- Tooling policy:
  - **Scheduling:** “If the user asks about availability, call the calendar tool **immediately** with what you have. Default 'confirm=false' to **list up to 3 options**. After the user picks one, call with 'confirm=true' (requires 'patient_name') to hold it.”
  - **Insurance:** “If acceptance/copay/PA is asked, call the insurance tool with 'provider', 'plan_type', and 'procedure_code' when available. Ask a **single clarifying question** if a required field is missing.”
  - **Never invent availability**; only state times returned by the tool.
- FAQ: a compact **Clinic FAQ** is appended to the prompt; answer logistics **only** from that section; say “don’t know” if it’s not in the FAQ.
- Using caps to emphasize problematic behaviors seen in testing.


**Few-shots** (optional)  
- I prepared a 'fewshot.json' with 2–4 targeted examples (e.g., “Dr. Lee Friday afternoon → list first → then hold”). It’s not loaded by default to save tokens; can be injected if behavior becomes unstable.

**Issues & mitigations encountered**

- **API shape bug** (''tool' must follow message with 'tool_calls''): fixed by appending the assistant message with 'tool_calls' *before* the 'role:"tool"' messages.  
- **Over‑questioning** before calendar calls: loosened the tool description (list first, hold later) so the model calls the tool with partial info.  
- **Hallucinated slots**: system prompt explicitly forbids inventing availability; the model must call the calendar tool.

---

## 4) Assumptions & Limitations

**Assumptions**

- Single speaker; short utterances (1–10 seconds).  
- English only; naive local datetimes (no timezone math).  
- Simple date phrases resolved in‑tool (“Friday”, “this week”, “afternoon”).  
- One clinic location; static providers: BlueShield, Aetna, United, Cigna.

**Known limitations**

- **Latency**: typical 6-7s per turn (voice path); worst‑case spikes observed.
- **Persistence**: holds live in process memory; no TTL or cross‑process coherence.  
- **Data realism**: small static JSONs; no double‑booking checks; no real insurance rules.  
- **Safety/Compliance**: no HIPAA controls; transcripts stored locally without redaction.  
- **Robustness**: no interrupt/“barge‑in” handling; limited retry policy; minimal analytics/observability.
- **Text model**: not using LLMs real time model (audio to audio) which would cut down latency. I didn't even know the model existed until today.

**Out‑of‑scope for the take‑home but on the roadmap**

- Real calendar integration (Google/Microsoft) and durable reservations with TTL/confirm/cancel flows.  
- Real payer/eligibility checks (270/271) or clearinghouse API; CPT mapping from a maintained source.  
- Multi‑lingual STT/TTS; better date/time normalization; timezone awareness.  
- Streaming UI (text first token in <1s) and batched TTS; queueing for concurrency.  
- Security & compliance: encryption at rest, PII redaction, access controls, audit logs, SOC2/HIPAA posture.  
- Analytics: turn timings, tool call telemetry, failure reasons, conversation outcomes.

---

