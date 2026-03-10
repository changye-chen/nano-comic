import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

LLM_PROFILES_PATH = Path(__file__).parent.parent.parent / "llm_profiles.yaml"

MODEL_CONFIG = {
    "deepseek-chat": {
        "model": "deepseek-chat",
        "api_key": os.getenv("DEEPSEEK_API_KEY"),
        "base_url": os.getenv("DEEPSEEK_BASE_URL"),
    },
}


def load_config(model_name: str = "deepseek-chat") -> dict[str, Any]:
    config = MODEL_CONFIG[model_name]

    return config


def load_llm_profiles() -> dict:
    """加载 LLM 配置文件"""
    if not LLM_PROFILES_PATH.exists():
        raise FileNotFoundError(f"LLM profiles 文件不存在: {LLM_PROFILES_PATH}")
    with open(LLM_PROFILES_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_model_config(model_name: str) -> dict[str, Any]:
    """获取指定模型的配置（包含 API 密钥）"""
    profiles = load_llm_profiles()
    model_info = profiles["models"].get(model_name)
    if not model_info:
        raise ValueError(f"未知的模型: {model_name}")

    api_key = os.getenv(model_info["env_key"])
    if not api_key:
        raise ValueError(f"未设置环境变量: {model_info['env_key']}")

    config: dict[str, Any] = {
        "model": model_name,
        "api_key": api_key,
    }

    base_url_env = model_info.get("env_base_url")
    if base_url_env:
        base_url = os.getenv(base_url_env)
        if base_url:
            config["base_url"] = base_url

    return config


def get_tool_default_model(tool_name: str) -> str:
    """获取工具的默认模型"""
    profiles = load_llm_profiles()
    return profiles.get("tool_defaults", {}).get(tool_name, profiles["default_model"])


def get_model_provider(model_name: str) -> str:
    """获取模型的 provider 类型"""
    profiles = load_llm_profiles()
    model_info = profiles["models"].get(model_name)
    if not model_info:
        raise ValueError(f"未知的模型: {model_name}")
    return model_info["provider"]


def get_model_structured_output_method(model_name: str) -> str:
    """获取模型的结构化输出方法，默认为 json_mode"""
    profiles = load_llm_profiles()
    model_info = profiles["models"].get(model_name)
    if not model_info:
        raise ValueError(f"未知的模型: {model_name}")
    return model_info.get("structured_output_method", "json_mode")
