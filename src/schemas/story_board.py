from typing import Literal

from pydantic import BaseModel, Field

# ==================== LLM 输出 ====================


class PanelCharacter(BaseModel):
    id: str = Field(description="角色ID")
    action: str = Field(description="该角色在本格中的动作")
    expression: str = Field(description="表情")


class PanelDialogue(BaseModel):
    speaker: str = Field(
        description="说话者角色ID，群众用 mob，旁白用 narrator"
    )
    text: str = Field(description="台词/旁白文本")
    type: Literal["normal", "shout", "thought", "narration"] = Field(
        description="气泡类型：普通/喊叫/思考/旁白"
    )


class Panel(BaseModel):
    panel_index: int = Field(description="格子序号，页内从1开始")
    beat_refs: list[int] = Field(description="对应的节拍序号列表")
    shot: str = Field(description="镜头描述：远景俯拍/中景正面/特写侧面 等")
    composition: str = Field(description="构图描述：元素在画面中的空间关系")
    scene: str = Field(description="场景/背景环境描述")
    characters: list[PanelCharacter] = Field(description="画面中的角色")
    dialogue: list[PanelDialogue] = Field(
        default_factory=list, description="对白与旁白"
    )
    sfx: str = Field(default="", description="漫画音效文字，如 哗——、砰！")
    tension: Literal["low", "medium", "high"] = Field(
        description="画面张力：影响线条粗细/对比度/速度线"
    )


class Page(BaseModel):
    page_index: int = Field(description="页码，SU内从1开始")
    beats_used: list[int] = Field(description="本页使用的节拍序号列表")
    layout: str = Field(
        description="页面布局自然语言描述，如：上方一个横长格，下方左右各一格"
    )
    page_mood: str = Field(description="整页氛围/光影基调")
    panels: list[Panel] = Field(description="格子列表")


class StoryBoardLLMOutput(BaseModel):
    pages: list[Page] = Field(description="分镜页列表")


# ==================== 文件（每页一个文件） ====================


class PageFile(BaseModel):
    page_id: str = Field(description="全局唯一页面ID，如 chap_1_su_1_page_1")
    su_id: int
    chapter_id: int
    page_index: int
    beats_used: list[int]
    layout: str
    page_mood: str
    panels: list[Panel]
