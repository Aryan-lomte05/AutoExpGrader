import os
from dotenv import load_dotenv

load_dotenv()

MODE = os.getenv("APP_MODE", "dev")  # "dev" | "prod"

MODEL_CONFIG = {
    "dev": {
        "vision_model": "gemini-2.5-flash",
        "text_model": "gemini-2.5-flash",
        "provider": "google_aistudio",
        "api_key": os.getenv("GOOGLE_AI_STUDIO_KEY")
    },
    "prod": {
        "vision_model": "qwen2.5vl:7b",
        "text_model": "qwen2.5:72b",
        "provider": "ollama_local",
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    }
}

def get_current_model_config():
    return MODEL_CONFIG.get(MODE, MODEL_CONFIG["dev"])

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./grader.db")
