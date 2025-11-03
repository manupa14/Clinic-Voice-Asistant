
import os
from dataclasses import dataclass
from dotenv import load_dotenv

OPENAI_TIMEOUT_SECONDS: int = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "45"))
OPENAI_MAX_RETRIES: int = int(os.getenv("OPENAI_MAX_RETRIES", "2"))
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)


@dataclass
class Settings:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "")
    OPENAI_CHAT_MODEL: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
    OPENAI_WHISPER_MODEL: str = os.getenv("OPENAI_WHISPER_MODEL", "whisper-1")
    DATA_DIR: str = os.path.join(BASE_DIR, "src", "data")
    PROMPTS_DIR: str = os.path.join(BASE_DIR, "src", "prompts")
    DEMOS_DIR: str = os.path.join(BASE_DIR, "demos")

    def validate(self):
        missing = []
        if not self.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")
        if not self.ELEVENLABS_API_KEY:
            missing.append("ELEVENLABS_API_KEY")
        if not self.ELEVENLABS_VOICE_ID:
            missing.append("ELEVENLABS_VOICE_ID")
        if missing:
            raise RuntimeError(f"Missing required secrets: {', '.join(missing)}")

settings = Settings()
