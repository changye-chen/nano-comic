from pydantic import BaseModel, Field

# ==================== LLM 输出 ====================


class StoryUnitEntry(BaseModel):
    start_anchor: str = Field(
        description="叙事单元起始锚点，原文中15-30字的文字片段，需在原文中唯一可定位"
    )
    end_anchor: str = Field(
        description="叙事单元结束锚点，原文中15-30字的文字片段，需在原文中唯一可定位"
    )
    summary: str = Field(description="该叙事单元的内容摘要")
    characters: list[str] = Field(description="出场角色ID列表")
    location: str = Field(description="场景ID")


class StoryUnitLLMOutput(BaseModel):
    story_units: list[StoryUnitEntry] = Field(
        description="按场景切分的叙事单元列表，按出现顺序排列，覆盖全部原文"
    )


# ==================== 文件 ====================


class StoryUnitFile(BaseModel):
    su_id: int
    chapter_id: int
    summary: str
    characters: list[str]
    location: str
    char_range: list[int] = Field(description="[start, end] 在章节原文中的字符位置")
    status: str = "split"
