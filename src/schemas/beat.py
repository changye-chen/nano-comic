from typing import Literal, Optional

from pydantic import BaseModel, Field

# ==================== LLM 输出 ====================


class CharacterAction(BaseModel):
    id: str = Field(description="角色ID")
    action: str = Field(description="该角色在做什么")
    expression: str = Field(description="表情")


class DialogueLine(BaseModel):
    speaker: str = Field(description="说话角色ID")
    text: str = Field(description="台词原文")


class Monologue(BaseModel):
    speaker: str = Field(description="角色ID")
    text: str = Field(description="独白文本")
    intensity: Literal["low", "medium", "high"] = Field(
        description="独白强度，影响后续视觉策略"
    )


class Beat(BaseModel):
    sequence: int = Field(description="节拍序号，从1开始")
    type: Literal[
        "establishing",
        "observation",
        "dialogue",
        "action",
        "internal_reflection",
        "transition",
        "climax",
    ] = Field(description="节拍类型")
    description: str = Field(description="一句话描述本节拍发生了什么")
    emotional_tone: str = Field(description="该节拍的情感基调")
    characters_acting: list[CharacterAction] = Field(
        description="参与角色及其动作与表情"
    )
    key_dialogue: list[DialogueLine] = Field(
        default_factory=list, description="关键对白"
    )
    monologue: Optional[Monologue] = Field(default=None, description="内心独白")


class BeatLLMOutput(BaseModel):
    beats: list[Beat] = Field(description="节拍列表，按叙事顺序排列")


# ==================== 文件 ====================


class BeatFile(BaseModel):
    su_id: int
    chapter_id: int
    beats: list[Beat]
