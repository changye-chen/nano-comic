import json
from pathlib import Path

from src.schemas.manga_prompt import MangaPromptFile, MangaPromptLLMOutput
from src.tools.core import (
    WorkspacePaths,
    build_characters_detail,
    build_locations_detail,
    build_previous_su_summaries,
    load_json,
    make_response,
    save_json,
)
from src.tools.llm_client import LLMClient


# === 风格描述映射 ===

COLOR_MODE_DESC = {
    "color": "全彩色",
    "black_and_white": "黑白",
}

COLOR_MOOD_DESC = {
    "bright": "明快鲜艳，色彩饱满，适合轻松愉快的场景",
    "muted": "低饱和灰调，柔和淡雅，适合日常或怀旧氛围",
    "dark": "阴郁深沉，暗色调为主，适合悬疑或压抑场景",
}

LINE_STYLE_DESC = {
    "clean": "干净利落，线条精细清晰",
    "bold": "粗犷有力，强调轮廓和动态",
    "sketchy": "手绘随笔感，线条自然随性",
}

TEXT_LANGUAGE_DESC = {
    "zh": "中文",
    "ja": "日文",
    "en": "英文",
}


def run(
    novel: str,
    chapter: int,
    workspace: Path,
    su: int,
    page: int,
    model: str | None = None,
    **_,
) -> str:
    wp = WorkspacePaths(workspace, novel)

    project = load_json(wp.project)
    chap_meta = load_json(wp.chap_meta(chapter))
    page_data = load_json(wp.page(chapter, su, page))
    su_meta = load_json(wp.su_meta(chapter, su))

    char_ids = set()
    for panel in page_data["panels"]:
        for c in panel.get("characters", []):
            char_ids.add(c["id"])
    loc_ids = [su_meta["location"]] if su_meta.get("location") else []

    art = project["art_style"]

    client = LLMClient(model_name=model)
    result = client.structured_output(
        "generate_manga_prompt",
        MangaPromptLLMOutput,
        # 摘要链路
        novel_summary=project.get("summary", "（暂无小说摘要）"),
        chapter_summary=chap_meta.get("summary", "（暂无章节摘要）"),
        previous_su_summaries=build_previous_su_summaries(wp, chapter, su),
        current_su_summary=su_meta.get("summary", "（暂无叙事单元摘要）"),
        # 风格配置
        style_directive=art["style_directive"],
        color_mode_desc=COLOR_MODE_DESC.get(art["color_mode"], "全彩色"),
        color_mood_desc=COLOR_MOOD_DESC.get(art["color_mood"], "明快鲜艳，色彩饱满"),
        line_style_desc=LINE_STYLE_DESC.get(art["line_style"], "干净利落"),
        text_language_desc=TEXT_LANGUAGE_DESC.get(
            art["text_language"], art["text_language"]
        ),
        # 分镜与资产
        page_json=json.dumps(page_data, indent=2, ensure_ascii=False),
        characters_detail=build_characters_detail(wp.characters_dir, sorted(char_ids)),
        locations_detail=build_locations_detail(wp.locations_dir, loc_ids),
    )

    prompt_file = MangaPromptFile(
        page_id=page_data["page_id"],
        page_prompt=result.page_prompt,
        character_refs=result.character_refs,
        location_refs=result.location_refs,
        style_directive=art["style_directive"],
        aspect_ratio=art["aspect_ratio"],
        color_mode=art["color_mode"],
        color_mood=art["color_mood"],
        line_style=art["line_style"],
        text_language=art["text_language"],
    )
    out_path = wp.prompt_file(chapter, su, page)
    save_json(out_path, prompt_file)

    # 更新进度
    chap_meta = load_json(wp.chap_meta(chapter))
    for item in chap_meta.get("story_units", []):
        if item["su_id"] == su:
            item["status"] = "prompt_generated"
    save_json(wp.chap_meta(chapter), chap_meta)

    su_data = load_json(wp.su_meta(chapter, su))
    su_data["status"] = "prompt_generated"
    save_json(wp.su_meta(chapter, su), su_data)

    return make_response(
        "success",
        f"Manga prompt generated for {page_data['page_id']}.",
        outputs=[str(out_path)],
        updated=[str(wp.chap_meta(chapter)), str(wp.su_meta(chapter, su))],
    )
