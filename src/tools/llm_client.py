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
        result = structured_llm.invoke(messages)

        if hasattr(output_model, "__name__") and "Beat" in output_model.__name__:
            result = self._fix_beat_format(result)

        return result

    # ──────────────────────────────────────
    # 结构化输出的辅助方法
    # ──────────────────────────────────────

    def _build_json_instruction(self, model: type[BaseModel]) -> str:
        """为 json_mode 构建格式说明，注入到 prompt 中"""
        schema = model.model_json_schema()
        field_desc = self._schema_to_description(schema)

        return (
            f"\n\n请严格按照以下 JSON Schema 输出，不要输出任何其他内容：\n"
            f"```\n{field_desc}\n```"
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
            for item in info["allOf"]:
                if "$ref" in item:
                    ref_path = item["$ref"]
                    ref_name = ref_path.split("/")[-1]
                    if ref_name in defs:
                        merged.update(defs[ref_name])
                else:
                    merged.update(item)
            return merged
        return info

    @staticmethod
    def _fix_beat_format(result):
        """修复模型输出的Beat格式问题"""
        if not hasattr(result, "beats"):
            return result

        for beat in result.beats:
            # 修复 monologue: {id, content} -> {speaker, text}
            if beat.monologue:
                if hasattr(beat.monologue, "id"):
                    beat.monologue.speaker = beat.monologue.id
                    delattr(beat.monologue, "id")
                if hasattr(beat.monologue, "content"):
                    beat.monologue.text = beat.monologue.content
                    delattr(beat.monologue, "content")
                # 添加缺失的 intensity
                if not hasattr(beat.monologue, "intensity"):
                    beat.monologue.intensity = "medium"

            # 修复 key_dialogue: 单个对象 -> 列表
            if beat.key_dialogue and not isinstance(beat.key_dialogue, list):
                beat.key_dialogue = [beat.key_dialogue]

            # 修复 key_dialogue 中的字段名
            if beat.key_dialogue:
                for dialogue in beat.key_dialogue:
                    if hasattr(dialogue, "content"):
                        dialogue.text = dialogue.content
                        delattr(dialogue, "content")

        return result
