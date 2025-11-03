# Confido Voice Assistant

Voice/text front-desk prototype (appointments, insurance, FAQs) with mocked backends and a Gradio UI.

---

## 1) Setup

```bash
# From project root
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

Copy env and fill secrets:

```bash
# Windows PowerShell
Copy-Item .env.example .env
# macOS/Linux
cp .env.example .env
```

**Required keys** (in `.env`):

```
OPENAI_API_KEY=sk-...
OPENAI_CHAT_MODEL=gpt-4.1-mini      # or gpt-4o-mini, gpt-5-mini, etc.
ELEVENLABS_API_KEY=eleven-...
ELEVENLABS_VOICE_ID=...             # voice used for TTS
DATA_DIR=src/data                   # default data folder
```

> Ensure `.gitignore` contains: `.env`, `.venv/`, `.idea/`, `__pycache__/`, `*.mp3`.

---

## 2) Run

### PyCharm (GUI – recommended)
1. **Mark Sources Root:** right‑click `src/` → **Mark Directory As → Sources Root** (turns blue).
2. **Run Configuration:** Run → **Edit Configurations…**
   - **Module name:** `app.ui_gradio`
   - **Working directory:** project root (folder that contains `src/`)
   - **Interpreter:** your `.venv`
3. Run. Browser opens to Gradio; allow microphone permission.

### CLI

**A) No install, set `PYTHONPATH` inline**
```bash
# Windows (cmd)
set PYTHONPATH=src
python -m app.ui_gradio

# Windows (PowerShell)
$env:PYTHONPATH="src"; python -m app.ui_gradio

# macOS/Linux
PYTHONPATH=src python -m app.ui_gradio
```

**B) Editable install (clean imports)**
```bash
pip install -e .
python -m app.ui_gradio
```

---

## 3) Project Structure

```
src/
  app/ui_gradio.py      # Gradio UI + event wiring (autoplay + mic auto-clear)
  core/
    llm.py              # OpenAI chat + tool-calling orchestrator
    tools.py            # Booking (schedule) + Insurance tools
    voice.py            # Whisper STT + ElevenLabs TTS (REST)
    dialogue_manager.py # Tool specs + system prompt loader
    config.py           # Settings + .env validation
  data/
    schedule.json
    insurance_table.json
    procedures.json
docs/
  system.md             # System prompt (authoritative behavior)
requirements.txt
README.md
```


