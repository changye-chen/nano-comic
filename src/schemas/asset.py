from pydantic import BaseModel, Field


class ReferenceImage(BaseModel):
    path: str = Field(description="图片文件路径")
    description: str = Field(description="图片内容描述")


class Appearance(BaseModel):
    index: int = Field(description="外貌版本索引")
    label: str = Field(description="外貌阶段标签，如 青年时期/中年时期")
    visual_description: str = Field(description="详细视觉描述，供绘图使用")
    reference_images: list[ReferenceImage] = Field(
        default_factory=list, description="参考图片列表"
    )


class Relationship(BaseModel):
    target: str = Field(description="关联角色ID")
    relation: str = Field(description="关系描述")


class CharacterAsset(BaseModel):
    id: str = Field(description="角色唯一ID，如 char_001")
    name: str = Field(description="角色名")
    aliases: list[str] = Field(default_factory=list, description="别名列表")
    personality: str = Field(description="性格描述")
    first_appearance: str = Field(description="首次出场章节ID，如 chap_1")
    relationships: list[Relationship] = Field(
        default_factory=list, description="角色关系"
    )
    appearances: list[Appearance] = Field(description="外貌版本池")
    current_appearance_index: int = Field(default=0, description="当前外貌索引")


class LocationAppearance(BaseModel):
    index: int = Field(description="场景版本索引")
    label: str = Field(description="场景状态标签，如 白天/夜晚/被破坏后")
    visual_description: str = Field(description="详细视觉描述")
    reference_images: list[ReferenceImage] = Field(
        default_factory=list, description="参考图片列表"
    )


class LocationAsset(BaseModel):
    id: str = Field(description="场景唯一ID，如 loc_001")
    name: str = Field(description="场景名称")
    first_appearance: str = Field(description="首次出现章节ID")
    appearances: list[LocationAppearance] = Field(description="场景版本池")
    current_appearance_index: int = Field(default=0, description="当前场景索引")
