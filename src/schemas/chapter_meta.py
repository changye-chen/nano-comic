from pydantic import BaseModel, Field

# ==================== LLM 输出 ====================


class NewCharacter(BaseModel):
    name: str = Field(description="角色名")
    aliases: list[str] = Field(default_factory=list, description="别名")
    personality: str = Field(description="性格描述")
    appearance_label: str = Field(description="当前外貌阶段标签")
    visual_description: str = Field(
        description="详细外貌描述：体型、发型、五官、穿着等"
    )
    relationships: list[dict] = Field(
        default_factory=list,
        description="关系列表，每项含 target_name(str) 和 relation(str)",
    )


class UpdatedCharacter(BaseModel):
    id: str = Field(description="已有角色ID")
    updates: dict = Field(
        description="需更新的字段键值对，可含 personality, aliases 等"
    )


class AppearanceChangedCharacter(BaseModel):
    id: str = Field(description="已有角色ID")
    new_label: str = Field(description="新外貌阶段标签")
    new_visual_description: str = Field(description="新外貌详细描述")
    set_current: bool = Field(default=True, description="是否设为当前外貌")


class CharacterChanges(BaseModel):
    new: list[NewCharacter] = Field(
        default_factory=list, description="本章新出现的角色"
    )
    updated: list[UpdatedCharacter] = Field(
        default_factory=list, description="信息需更新的已有角色"
    )
    appearance_changed: list[AppearanceChangedCharacter] = Field(
        default_factory=list, description="外貌发生变化的已有角色"
    )


class NewLocation(BaseModel):
    name: str = Field(description="场景名称")
    appearance_label: str = Field(description="场景状态标签")
    visual_description: str = Field(description="详细场景描述")


class UpdatedLocation(BaseModel):
    id: str = Field(description="已有场景ID")
    updates: dict = Field(description="需更新的字段键值对")


class AppearanceChangedLocation(BaseModel):
    id: str = Field(description="已有场景ID")
    new_label: str = Field(description="新场景状态标签")
    new_visual_description: str = Field(description="新场景详细描述")
    set_current: bool = Field(default=True, description="是否设为当前场景状态")


class LocationChanges(BaseModel):
    new: list[NewLocation] = Field(
        default_factory=list, description="本章新出现的场景"
    )
    updated: list[UpdatedLocation] = Field(
        default_factory=list, description="信息需更新的已有场景"
    )
    appearance_changed: list[AppearanceChangedLocation] = Field(
        default_factory=list, description="状态发生变化的已有场景"
    )


class ChapterMetaLLMOutput(BaseModel):
    chapter_summary: str = Field(description="本章内容摘要")
    novel_summary_update: str = Field(
        description="结合本章内容更新后的小说整体摘要，若当前为空则从零生成"
    )
    characters: CharacterChanges = Field(description="角色变更")
    locations: LocationChanges = Field(description="场景变更")


# ==================== 文件 ====================


class StoryUnitProgress(BaseModel):
    su_id: int
    status: str = "split"  # split | beats_extracted | storyboard_done | prompt_generated
    page_count: int = 0


class ChapterFile(BaseModel):
    chapter_id: int
    summary: str
    characters: list[str] = Field(default_factory=list, description="本章出场角色ID")
    locations: list[str] = Field(default_factory=list, description="本章涉及场景ID")
    story_unit_count: int = 0
    story_units: list[StoryUnitProgress] = Field(default_factory=list)
    status: str = "scanned"  # scanned | split | processing | done
