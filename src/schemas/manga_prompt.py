from pydantic import BaseModel, Field

# ==================== LLM 输出 ====================


class CharacterRef(BaseModel):
    id: str = Field(description="引用的角色ID")
    appearance_index: int = Field(description="使用的外貌版本索引")


class MangaPromptLLMOutput(BaseModel):
    page_prompt: str = Field(
        description="完整的一页漫画自然语言绘图提示词，内联角色外貌和场景描述"
    )
    character_refs: list[CharacterRef] = Field(description="引用的角色及其外貌版本")
    location_refs: list[str] = Field(description="引用的场景ID列表")


# ==================== 文件 ====================


class MangaPromptFile(BaseModel):
    page_id: str
    page_prompt: str
    character_refs: list[CharacterRef]
    location_refs: list[str]
    style_directive: str = Field(description="从 project.json 继承的全局风格指令")
    aspect_ratio: str = Field(description="从 project.json 继承的页面比例")
    color_mode: str = Field(default="color", description="彩色或黑白模式")
    color_mood: str = Field(default="bright", description="色彩氛围")
    line_style: str = Field(default="clean", description="线条风格")
    text_language: str = Field(default="zh", description="漫画文字语言")
