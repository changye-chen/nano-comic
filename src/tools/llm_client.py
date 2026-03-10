from pathlib import Path
from typing import Any

import yaml
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from src.tools.config import (
    get_model_config,
    get_model_provider,
    get_model_structured_output_method,
)
from src.tools.prompting import PromptTemplate

PROMPT_DIR = Path(__file__).parent.parent / "prompts"


class LLMClient:
    def __init__(self, model_name: str | None = None):
        if model_name is None:
            model_name = "deepseek-chat"
        self.model_name = model_name
        self.config = get_model_config(model_name)
        self.provider = get_model_provider(model_name)
        self.structured_output_method = get_model_structured_output_method(model_name)
        self._base_llm = self._create_llm()

    def _create_llm(self, **overrides) -> Any:
        """创建 LLM 实例，overrides 可覆盖默认配置"""
        config = {**self.config, **overrides}

        if self.provider == "openai_compatible":
            return ChatOpenAI(**config)
        elif self.provider == "anthropic":
            try:
                from langchain_anthropic import ChatAnthropic

                return ChatAnthropic(**config)
            except ImportError:
                raise ImportError(
                    "请安装 langchain-anthropic: pip install langchain-anthropic"
                )
        elif self.provider == "google":
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI

                return ChatGoogleGenerativeAI(**config)
            except ImportError:
                raise ImportError(
                    "请安装 langchain-google-genai: pip install langchain-google-genai"
                )
        else:
            raise ValueError(f"不支持的 provider: {self.provider}")

    def _get_llm(self, **overrides) -> Any:
        """获取 LLM，如果有 overrides 则创建新实例，否则复用"""
        if overrides:
            return self._create_llm(**overrides)
        return self._base_llm

    # ──────────────────────────────────────
    # Prompt 加载与渲染
    # ──────────────────────────────────────

    def _load_prompt(self, prompt_name: str) -> PromptTemplate:
        prompt_path = PROMPT_DIR / f"{prompt_name}.yaml"
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt 文件不存在: {prompt_path}")
        with open(prompt_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return PromptTemplate(**data)

    def _render_messages(
        self, prompt: PromptTemplate, **inputs
    ) -> list[dict[str, str]]:
        messages = []
        if prompt.system:
            messages.append(
                {
                    "role": "system",
                    "content": prompt.system.format(**inputs),
                }
            )
        messages.append(
            {
                "role": "user",
                "content": prompt.user.format(**inputs),
            }
        )
        # 支持 few-shot：如果 PromptTemplate 有 examples 字段
        # 可以在这里扩展
        return messages

    # ──────────────────────────────────────
    # 核心调用方法
    # ──────────────────────────────────────

    def completion(
        self,
        prompt_name: str,
        temperature: float | None = None,
        **inputs,
    ) -> str:
        overrides = {}
        if temperature is not None:
            overrides["temperature"] = temperature

        llm = self._get_llm(**overrides)
        prompt = self._load_prompt(prompt_name)
        messages = self._render_messages(prompt, **inputs)
        response = llm.invoke(messages)
        return str(response.content)

    def structured_output(
        self,
        prompt_name: str,
        output_model: type[BaseModel],
        temperature: float | None = None,
        **inputs,
    ):
        """使用结构化输出，返回 Pydantic 模型实例"""
        overrides = {}
        if temperature is not None:
            overrides["temperature"] = temperature

        llm = self._get_llm(**overrides)
        prompt = self._load_prompt(prompt_name)
        messages = self._render_messages(prompt, **inputs)

        if self.structured_output_method == "json_mode":
            json_instruction = self._build_json_instruction(output_model)
            messages[0]["content"] += json_instruction

        structured_llm = llm.with_structured_output(
            output_model, method=self.structured_output_method
        )
        return structured_llm.invoke(messages)

    # ──────────────────────────────────────
    # 结构化输出的辅助方法
    # ──────────────────────────────────────

    def _build_json_instruction(self, model: type[BaseModel]) -> str:
        """为 json_mode 构建格式说明，注入到 prompt 中"""
        schema = model.model_json_schema()

        # 生成字段说明
        field_desc = self._schema_to_description(schema)

        # 生成 JSON 结构示例
        json_example = self._build_json_example(schema)

        return (
            f"\n\n请严格按照以下 JSON 格式输出，不要输出任何其他内容：\n"
            f"```\n{json_example}\n```\n\n"
            f"字段说明：\n{field_desc}"
        )

    def _build_json_example(
        self, schema: dict, defs: dict | None = None, indent: int = 0
    ) -> str:
        """
        根据Schema生成JSON结构示例（带占位符），让模型清楚理解层级关系。
        """
        if defs is None:
            defs = schema.get("$defs", {})

        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        lines = []
        prefix = "  " * indent

        # 处理顶层类型
        schema_type = schema.get("type", "object")

        if schema_type == "array":
            items = self._resolve_ref(schema.get("items", {}), defs)
            item_example = self._build_json_example(items, defs, indent)
            return f"[\n{prefix}  {item_example.strip()},\n{prefix}  ...\n{prefix}]"
        elif schema_type == "object" and not props:
            return "{}"

        for name, info in props.items():
            info = self._resolve_ref(info, defs)
            type_str = info.get("type", "object")
            desc = info.get("description", "")
            is_required = name in required
            req_mark = "" if is_required else " (可选)"
            comma = ","  # 总是加逗号

            # 处理 anyOf（如 Optional 字段）
            if "anyOf" in info:
                # 找到非 null 的类型
                for variant in info["anyOf"]:
                    variant = self._resolve_ref(variant, defs)
                    if variant.get("type") != "null":
                        info = variant
                        type_str = info.get("type", "object")
                        break

            if type_str == "object" and "properties" in info:
                nested = self._build_json_example(info, defs, indent + 1)
                lines.append(f'{prefix}"{name}": {nested}{comma}')
            elif type_str == "array":
                items = self._resolve_ref(info.get("items", {}), defs)
                if "properties" in items:
                    # 数组元素是对象
                    item_example = self._build_json_example(items, defs, indent + 2)
                    lines.append(
                        f'{prefix}"{name}": [\n'
                        f"{prefix}  {item_example.strip()}\n"
                        f"{prefix}]{comma}"
                    )
                else:
                    item_type = items.get("type", "any")
                    lines.append(
                        f'{prefix}"{name}": ["<{item_type}>{req_mark}"]{comma}'
                    )
            elif "enum" in info:
                enum_vals = info["enum"]
                example_val = enum_vals[0] if enum_vals else "unknown"
                lines.append(f'{prefix}"{name}": "{example_val}"{comma}{req_mark}')
            else:
                placeholder = f"<{type_str}>{req_mark}"
                lines.append(f'{prefix}"{name}": "{placeholder}"{comma}')

        return (
            "{\n" + "\n".join(lines) + "\n" + prefix[:-2] + "}"
            if indent > 0
            else "{\n" + "\n".join(lines) + "\n}"
        )

    def _schema_to_description(
        self,
        schema: dict,
        defs: dict | None = None,
        indent: int = 0,
    ) -> str:
        """
        将 JSON Schema 转为可读的字段说明。
        正确处理 $defs/$ref 引用。
        """
        # 顶层调用时提取 $defs
        if defs is None:
            defs = schema.get("$defs", {})

        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        lines = []
        prefix = "  " * indent

        for name, info in props.items():
            # 解析 $ref 引用
            info = self._resolve_ref(info, defs)

            desc = info.get("description", "")
            type_str = info.get("type", "object")
            req_mark = "*" if name in required else ""

            if type_str == "object" and "properties" in info:
                lines.append(f"{prefix}- {name}{req_mark} (object): {desc}")
                lines.append(self._schema_to_description(info, defs, indent + 1))
            elif type_str == "array":
                items = self._resolve_ref(info.get("items", {}), defs)
                if "properties" in items:
                    lines.append(f"{prefix}- {name}{req_mark} (array[object]): {desc}")
                    lines.append(self._schema_to_description(items, defs, indent + 1))
                else:
                    item_type = items.get("type", "any")
                    lines.append(
                        f"{prefix}- {name}{req_mark} (array[{item_type}]): {desc}"
                    )
            elif "enum" in info:
                enum_vals = ", ".join(repr(v) for v in info["enum"])
                lines.append(f"{prefix}- {name}{req_mark} (enum: {enum_vals}): {desc}")
            else:
                lines.append(f"{prefix}- {name}{req_mark} ({type_str}): {desc}")

        return "\n".join(lines)

    @staticmethod
    def _resolve_ref(info: dict, defs: dict) -> dict:
        """解析 $ref 引用，返回实际的 schema"""
        if "$ref" in info:
            ref_path = info["$ref"]  # e.g. "#/$defs/Address"
            ref_name = ref_path.split("/")[-1]
            if ref_name in defs:
                return defs[ref_name]
        # allOf 也是 Pydantic 常用的模式（带 description 的嵌套引用）
        if "allOf" in info:
            merged = {}
            for sub in info["allOf"]:
                merged.update(LLMClient._resolve_ref(sub, defs))
            # 保留外层的 description
            if "description" in info:
                merged["description"] = info["description"]
            return merged
        return info
