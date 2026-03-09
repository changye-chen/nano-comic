import os
from typing import Dict

from dotenv import load_dotenv

load_dotenv()

MODEL_CONFIG = {
    "deepseek-chat": {
        "model": "deepseek-chat",
        "api_key": os.getenv("DEEPSEEK_API_KEY"),
        "base_url": os.getenv("DEEPSEEK_BASE_URL"),
    },
}


def load_config(model_name: str = "deepseek-chat") -> Dict:
    config = MODEL_CONFIG[model_name]

    return config
