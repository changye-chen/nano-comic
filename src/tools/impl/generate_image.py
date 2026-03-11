"""
漫画图片生成工具
基于 Nano Banana 2 (gemini-3.1-flash-image-preview)
"""

import os
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

from src.schemas.asset import CharacterAsset, LocationAsset
from src.schemas.manga_prompt import MangaPromptFile
from src.schemas.project import ProjectFile
from src.tools.core import (
    WorkspacePaths,
    load_json,
    make_response,
    save_json,
)

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
BASE_URL = os.getenv("GEMINI_BASE_URL")
MODEL = "gemini-3.1-flash-image-preview"

# 前图参考配置
MAX_PREVIOUS_PAGES = 2  # 最多参考前两页

if not API_KEY:
    raise ValueError("请在 .env 文件中设置 GEMINI_API_KEY")


def get_client():
    client_kwargs = {"api_key": API_KEY}
    if BASE_URL:
        client_kwargs["http_options"] = types.HttpOptions(
            api_version="v1beta",
            base_url=BASE_URL,
        )
    return genai.Client(**client_kwargs)


def collect_previous_page_images(
    wp: WorkspacePaths,
    chapter: int,
    su: int,
    page: int,
    max_images: int = MAX_PREVIOUS_PAGES,
) -> list[str]:
    """
    收集前序页面的图片作为视觉参考，保持风格一致性。

    逻辑：
    - page_1 → 无前图
    - page_2 → 参考 page_1
    - page_N → 参考 page_{N-2}, page_{N-1}
    - 跨 SU：su_2/page_1 → 参考 su_1 的最后两页
    """
    images = []

    # 同一 SU 内的前序页面
    if page > 1:
        for prev_page in range(page - 1, max(0, page - 1 - max_images), -1):
            img_path = wp.su_dir(chapter, su) / "images" / f"page_{prev_page}.png"
            if img_path.exists():
                images.append(str(img_path))

    # 如果前图不足，且当前是 SU 的第一页，尝试从上一个 SU 获取
    if len(images) < max_images and page == 1 and su > 1:
        prev_su = su - 1
        prev_su_meta = wp.su_meta(chapter, prev_su)

        if prev_su_meta.exists():
            prev_su_data = load_json(prev_su_meta)
            prev_page_count = prev_su_data.get("page_count", 0)

            if prev_page_count > 0:
                # 从上一个 SU 的最后几页获取
                for prev_page in range(prev_page_count, 0, -1):
                    img_path = (
                        wp.su_dir(chapter, prev_su) / "images" / f"page_{prev_page}.png"
                    )
                    if img_path.exists():
                        images.append(str(img_path))
                    if len(images) >= max_images:
                        break

    return images


def collect_reference_images(
    characters_dir: Path,
    locations_dir: Path,
    character_refs: list[dict],
    location_refs: list[str],
    max_images: int = 14,
) -> list[str]:
    """收集角色和场景的参考图片路径"""
    images = []

    for ref in character_refs:
        char_id = ref["id"]
        appearance_idx = ref.get("appearance_index", 0)
        char_path = characters_dir / f"{char_id}.json"
        if char_path.exists():
            char = CharacterAsset(**load_json(char_path))
            if appearance_idx < len(char.appearances):
                for img in char.appearances[appearance_idx].reference_images:
                    images.append(img["path"])
                    if len(images) >= max_images:
                        return images

    for loc_id in location_refs:
        loc_path = locations_dir / f"{loc_id}.json"
        if loc_path.exists():
            loc = LocationAsset(**load_json(loc_path))
            idx = loc.current_appearance_index
            if idx < len(loc.appearances):
                for img in loc.appearances[idx].reference_images:
                    images.append(img["path"])
                    if len(images) >= max_images:
                        return images

    return images


def map_aspect_ratio(ratio: str) -> str:
    """将 project.json 的比例映射到 Gemini 支持的格式"""
    mapping = {
        "1:1": "1:1",
        "2:3": "2:3",
        "3:2": "3:2",
        "3:4": "3:4",
        "4:3": "4:3",
        "4:5": "4:5",
        "5:4": "5:4",
        "9:16": "9:16",
        "16:9": "16:9",
        "21:9": "21:9",
    }
    return mapping.get(ratio, "2:3")


def map_resolution(res: str) -> str:
    """将 project.json 的分辨率映射到 Gemini 支持的格式"""
    mapping = {
        "1024x1536": "1K",
        "1536x1024": "1K",
        "1024x1024": "1K",
        "2048x3072": "2K",
        "3072x2048": "2K",
        "2048x2048": "2K",
        "4096x6144": "4K",
        "6144x4096": "4K",
        "512x768": "512px",
        "768x512": "512px",
    }
    return mapping.get(res, "1K")


def generate_page_image(
    workspace: Path,
    novel: str,
    chapter: int,
    su: int,
    page: int,
) -> str:
    """生成单页漫画图片"""
    wp = WorkspacePaths(workspace, novel)

    project_path = wp.project
    if not project_path.exists():
        return make_response("error", f"项目文件不存在: {project_path}")

    project = ProjectFile(**load_json(project_path))

    prompt_path = wp.prompt_file(chapter, su, page)
    if not prompt_path.exists():
        return make_response("error", f"提示词文件不存在: {prompt_path}")

    prompt_file = MangaPromptFile(**load_json(prompt_path))

    # 收集角色/场景参考图
    asset_ref_images = collect_reference_images(
        wp.characters_dir,
        wp.locations_dir,
        [r.model_dump() for r in prompt_file.character_refs],
        prompt_file.location_refs,
    )

    # 收集前序页面图片（保持风格一致性）
    previous_page_images = collect_previous_page_images(wp, chapter, su, page)

    output_dir = wp.su_dir(chapter, su) / "images"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"page_{page}.png"

    try:
        client = get_client()

        contents = []
        valid_asset_refs = []
        valid_prev_pages = []

        # 1. 添加前序页面图片作为风格参考
        for img_path in previous_page_images:
            full_path = Path(img_path)
            if full_path.exists():
                contents.append(Image.open(full_path))
                valid_prev_pages.append(str(full_path))

        # 2. 添加角色/场景参考图
        for img_path in asset_ref_images:
            full_path = Path(img_path)
            if not full_path.is_absolute():
                full_path = workspace / novel / img_path
            if full_path.exists():
                contents.append(Image.open(full_path))
                valid_asset_refs.append(str(full_path))

        final_prompt = "\n".join(
            [
                prompt_file.style_directive,
                COLOR_MODE_INSTRUCTION.get(
                    prompt_file.color_mode, "这是一张全彩色的漫画页面。"
                ),
                COLOR_MOOD_INSTRUCTION.get(prompt_file.color_mood, "色彩明快鲜艳。"),
                LINE_STYLE_INSTRUCTION.get(prompt_file.line_style, "线条干净利落。"),
                f"漫画中的对白气泡和文字使用{prompt_file.text_language}。",
                "",
                prompt_file.page_prompt,
            ]
        )
        contents.append(final_prompt)

        aspect_ratio = map_aspect_ratio(prompt_file.aspect_ratio)
        image_size = map_resolution(project.art_style.resolution)

        config = types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            ),
        )

        print(f"生成图片: {output_path}")
        print(f"  比例: {aspect_ratio}, 分辨率: {image_size}")
        print(
            f"  参考图: {len(valid_prev_pages) + len(valid_asset_refs)} 张 (前图:{len(valid_prev_pages)}, 资产:{len(valid_asset_refs)})"
        )

        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=config,
        )

        image_saved = False
        for part in response.candidates[0].content.parts:
            if part.text is not None:
                print(f"  模型回复: {part.text[:100]}...")
            elif part.inline_data is not None:
                img = Image.open(BytesIO(part.inline_data.data))
                img.save(output_path)
                print(f"  已保存: {output_path}")
                image_saved = True

        if not image_saved:
            return make_response("error", "未生成图片")

        image_meta = {
            "page_id": prompt_file.page_id,
            "output_path": str(output_path.relative_to(workspace / novel)),
            "aspect_ratio": aspect_ratio,
            "image_size": image_size,
            "reference_images": [
                {"path": p, "type": "previous_page"} for p in valid_prev_pages
            ]
            + [{"path": p, "type": "asset"} for p in valid_asset_refs],
            "model": MODEL,
        }

        meta_path = output_dir / f"page_{page}_meta.json"
        save_json(meta_path, image_meta)

        return make_response(
            "success",
            f"图片已生成: {output_path}",
            outputs=[str(output_path)],
            updated=[str(output_path), str(meta_path)],
        )

    except Exception as e:
        return make_response("error", f"生成图片失败: {str(e)}")


def run(
    novel: str,
    chapter: int,
    workspace: Path,
    su: int,
    page: int,
    model: str | None = None,
    **_,
) -> str:
    """CLI 入口"""
    return generate_page_image(workspace, novel, chapter, su, page)


# === 风格描述映射（用于最终 prompt 构建）===

COLOR_MODE_INSTRUCTION = {
    "color": "这是一张全彩色的漫画页面。",
    "black_and_white": "这是一张黑白漫画页面，使用高对比度墨线。",
}

COLOR_MOOD_INSTRUCTION = {
    "bright": "色彩明快鲜艳。",
    "muted": "色彩低饱和柔和。",
    "dark": "色调阴郁深沉。",
}

LINE_STYLE_INSTRUCTION = {
    "clean": "线条干净利落。",
    "bold": "线条粗犷有力。",
    "sketchy": "线条手绘随笔感。",
}
