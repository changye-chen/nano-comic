#!/usr/bin/env python3
"""测试模型的结构化输出支持方式

用法:
  python scripts/test_structured_output.py                    # 测试默认模型
  python scripts/test_structured_output.py --model gpt-4      # 测试指定模型
  python scripts/test_structured_output.py --all              # 测试所有配置的模型
  python scripts/test_structured_output.py --update           # 测试并更新配置文件
"""

import argparse
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.llm_client import LLMClient


class TestOutput(BaseModel):
    name: str = Field(description="名称")
    age: int = Field(description="年龄")
    description: str = Field(description="描述")


METHODS = ["function_calling", "json_mode", "json_schema"]


def test_method(model_name: str, method: str) -> tuple[bool, str]:
    """测试指定方法是否可用

    Returns:
        (success, error_message)
    """
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        client = LLMClient(model_name)
        client.structured_output_method = method

        messages = [
            SystemMessage(content="你是一个测试助手。"),
            HumanMessage(content="请生成一个测试输出：名称张三，年龄25岁。"),
        ]

        llm = client._get_llm()
        if method == "json_mode":
            json_instruction = client._build_json_instruction(TestOutput)
            messages[0].content += json_instruction

        structured_llm = llm.with_structured_output(TestOutput, method=method)
        result = structured_llm.invoke(messages)
        return True, str(result)
    except Exception as e:
        return False, str(e)


def test_model(model_name: str) -> str | None:
    """测试模型，返回支持的方法

    Returns:
        支持的方法名，如果都不支持则返回 None
    """
    print(f"\n测试模型: {model_name}")
    print("=" * 70)

    supported_method = None

    for method in METHODS:
        success, message = test_method(model_name, method)
        if success:
            print(f"✓ {method:20s} - 支持")
            if supported_method is None:
                supported_method = method
        else:
            error_preview = message[:80].replace("\n", " ")
            print(f"✗ {method:20s} - 不支持 ({error_preview}...)")

    if supported_method:
        print(f"\n推荐配置: structured_output_method: {supported_method}")
    else:
        print("\n⚠ 警告: 该模型不支持任何结构化输出方法")

    return supported_method


def update_profile(model_name: str, method: str):
    """更新 llm_profiles.yaml 中的配置"""
    profiles_path = Path(__file__).parent.parent / "llm_profiles.yaml"

    with open(profiles_path, "r", encoding="utf-8") as f:
        profiles = yaml.safe_load(f)

    if model_name not in profiles["models"]:
        print(f"\n✗ 错误: 模型 {model_name} 不在配置文件中")
        return

    profiles["models"][model_name]["structured_output_method"] = method

    with open(profiles_path, "w", encoding="utf-8") as f:
        yaml.dump(
            profiles, f, allow_unicode=True, default_flow_style=False, sort_keys=False
        )

    print(f"\n✓ 已更新 {profiles_path.name}")


def main():
    parser = argparse.ArgumentParser(description="测试模型的结构化输出支持")
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="要测试的模型名称（默认: 使用 llm_profiles.yaml 中的 default_model）",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="测试所有配置的模型",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="测试后自动更新 llm_profiles.yaml",
    )
    args = parser.parse_args()

    profiles_path = Path(__file__).parent.parent / "llm_profiles.yaml"
    with open(profiles_path, "r", encoding="utf-8") as f:
        profiles = yaml.safe_load(f)

    if args.all:
        models = list(profiles["models"].keys())
        print(f"将测试 {len(models)} 个模型")
        for model_name in models:
            method = test_model(model_name)
            if args.update and method:
                update_profile(model_name, method)
    else:
        model_name = args.model or profiles.get("default_model", "deepseek-chat")
        method = test_model(model_name)
        if args.update and method:
            update_profile(model_name, method)


if __name__ == "__main__":
    main()
