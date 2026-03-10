from typing import Literal

from pydantic import BaseModel, Field


class ArtStyle(BaseModel):
    color_mode: Literal["black_and_white", "color"] = Field(
        description="黑白或彩色"
    )
    text_language: str = Field(description="漫画文字语言，如 zh/en/ja")
    resolution: str = Field(description="输出分辨率，如 1024x1536")
    aspect_ratio: str = Field(description="页面比例，如 2:3")
    file_format: Literal["png", "jpg", "webp"] = Field(description="输出图片格式")
    style_directive: str = Field(
        description="全局风格指令，如：黑白漫画，高对比度墨线，日式分镜风格"
    )


class ProjectFile(BaseModel):
    novel_name: str = Field(description="小说名称")
    author: str = Field(description="作者")
    genre: str = Field(description="小说类型，如 科幻/奇幻/现实主义")
    summary: str = Field(default="", description="小说整体摘要，随章节推进更新")
    art_style: ArtStyle = Field(description="绘画风格与输出参数")
    current_status: str = Field(
        default="initialized", description="当前工作进度，如 initialized / chapter-3"
    )
