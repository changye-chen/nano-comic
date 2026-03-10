import json
from pathlib import Path

from src.schemas.manga_prompt import MangaPromptFile, MangaPromptLLMOutput
from src.tools.core import (
    WorkspacePaths,
    build_characters_detail,
    build_locations_detail,
    load_json,
    make_response,
    save_json,
)
from src.tools.llm_client import LLMClient


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
        style_directive=art["style_directive"],
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
