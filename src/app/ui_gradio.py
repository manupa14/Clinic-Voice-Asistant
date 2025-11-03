import os
import json
import tempfile

import gradio as gr

from core.config import settings
from core.llm import LLMOrchestrator
from core.voice import Speech
from core.tools import BookingStore, InsuranceVerifier

print("[boot] constructing Speech()");
speech = Speech();
print("[boot] Speech ready")

print("[boot] constructing LLM()");
llm = LLMOrchestrator();
print("[boot] LLM ready")
booking_store = BookingStore()
insurance = InsuranceVerifier()

SYSTEM_PROMPT = None
GREETING = "Hello! You’ve reached Confido Health Clinic. I’m an AI assistant – how can I help you today?"


def start_session():
    state = {
        "messages": llm.bootstrap_messages(),
        "holds": {},
        "transcript": [],
        "chat": []
    }
    return state, gr.update(value=[]), None

def welcome_greeting(state):
    if state is None:
        state, _, _ = start_session()

    state.setdefault("transcript", [])
    state["transcript"].append({"role": "assistant", "text": GREETING, "system_greeting": True})

    chat = state.get("chat", [])
    chat.append(("", GREETING))
    state["chat"] = chat

    audio_path = None
    try:
        audio_path = speech.tts(GREETING)
    except Exception as e:
        print(f"[TTS greeting error] {e}")

    return chat, audio_path


def process_text(user_text, state):
    if state is None:
        state, _, _ = start_session()
    if not user_text or (isinstance(user_text, str) and not user_text.strip()):
        return gr.update(), state, None, None

    if not isinstance(user_text, str):
        user_text = str(user_text)
    user_text = user_text.strip()

    state["transcript"].append({"role": "user", "text": user_text})

    chat = state.get("chat", [])
    chat.append((user_text, ""))

    try:
        assistant_text, tool_info = llm.run_turn(
            state["messages"],
            user_text,
            tool_runtime={
                "verify_insurance": insurance.verify,
                "check_calendar_and_hold_slot": booking_store.check_and_hold,
            },
        )
    except Exception as e:
        assistant_text, tool_info = f"[LLM error: {e}]", {"error": repr(e)}

    audio_path = None

    state["transcript"].append({"role": "assistant", "text": assistant_text, "tool_info": tool_info})
    chat[-1] = (user_text, assistant_text)
    state["chat"] = chat

    return chat, state, audio_path, tool_info, gr.update(value="")

def synth_last_assistant(state):
    if not state or not state.get("transcript"):
        return None
    for t in reversed(state["transcript"]):
        if t.get("role") == "assistant":
            try:
                return speech.tts(t.get("text", ""))
            except Exception as e:
                print(f"[TTS] error: {e}")
                return None
    return None

def process_audio(audio_file, state):
    if state is None:
        state, _, _ = start_session()

    if audio_file is None:
        return gr.update(), state, None, None

    chat = state.get("chat", [])

    try:
        user_text = speech.stt(audio_file)
    except Exception as e:
        msg = f"[Sorry, I couldn't transcribe your audio: {e}]"
        chat.append(("[voice message]", msg))
        state["transcript"].append({"role": "assistant", "text": msg, "error": "stt"})
        state["chat"] = chat
        return chat, state, None, None

    if not user_text or not str(user_text).strip():
        msg = "[Sorry, I didn't catch that. Could you repeat?]"
        chat.append(("[voice message]", msg))
        state["transcript"].append({"role": "assistant", "text": msg})
        state["chat"] = chat
        return chat, state, None, None

    return process_text(user_text, state)


def export_transcript(state):
    if not state or not state.get("transcript"):
        return None

    content = json.dumps(state["transcript"], indent=2)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
    tmp.write(content.encode("utf-8"))
    tmp.flush()
    return tmp.name

def _clear_mic():
    return gr.update(value=None)


with gr.Blocks(title="Confido Voice Assistant") as demo:
    gr.Markdown("# Confido Voice Assistant")
    gr.Markdown("Voice-enabled front-desk assistant (appointments, insurance, FAQs).")

    state = gr.State()

    chatbot = gr.Chatbot(height=350, label="Conversation")
    audio_out = gr.Audio(label="Assistant Audio", type="filepath", autoplay=True)
    tool_info_out = gr.JSON(label="Tool Call (debug)", visible=False)

    with gr.Row():
        mic = gr.Audio(
            sources=["microphone"],
            type="filepath",
            label="Record (Stop = Send)"
        )

    text = gr.Textbox(placeholder="Or type here and press Enter...", lines=1)

    with gr.Row():
        new_btn = gr.Button("New Session")
        export_btn = gr.Button("Export Transcript")

    demo.load(start_session, outputs=[state, chatbot, audio_out]).then(
        welcome_greeting, inputs=[state], outputs=[chatbot, audio_out]
    )

    new_btn.click(
        start_session, outputs=[state, chatbot, audio_out]
    ).then(
        welcome_greeting, inputs=[state], outputs=[chatbot, audio_out]
    )

    text.submit(
        process_text,
        inputs=[text, state],
        outputs=[chatbot, state, audio_out, tool_info_out, text],
    ).then(
        synth_last_assistant, inputs=[state], outputs=[audio_out]
    )

    mic.stop_recording(
        process_audio,
        inputs=[mic, state],
        outputs=[chatbot, state, audio_out, tool_info_out],
    ).then(
        synth_last_assistant, inputs=[state], outputs=[audio_out]
    ).then(
        _clear_mic, outputs=[mic]  # ← clear mic after audio is queued
    )

    export_btn.click(
        export_transcript,
        inputs=[state],
        outputs=[gr.File(label="Transcript")],
    )


if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1",
        server_port=7861,
        inbrowser=True,
        debug=True,
        show_error=True
    )
