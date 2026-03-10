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

    ref_images = collect_reference_images(
        wp.characters_dir,
        wp.locations_dir,
        [r.model_dump() for r in prompt_file.character_refs],
        prompt_file.location_refs,
    )

    output_dir = wp.su_dir(chapter, su) / "images"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"page_{page}.png"

    try:
        client = get_client()

        contents = []
        valid_ref_images = []

        for img_path in ref_images:
            full_path = Path(img_path)
            if not full_path.is_absolute():
                full_path = workspace / novel / img_path
            if full_path.exists():
                contents.append(Image.open(full_path))
                valid_ref_images.append(str(full_path))

        final_prompt = f"{prompt_file.style_directive}\n\n{prompt_file.page_prompt}"
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
        print(f"  参考图: {len(valid_ref_images)} 张")

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
            "reference_images_used": valid_ref_images,
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


def run(novel: str, chapter: int, su: int, page: int, workspace: Path) -> str:
    """CLI 入口"""
    return generate_page_image(workspace, novel, chapter, su, page)
