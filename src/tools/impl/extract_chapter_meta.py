import json
from pathlib import Path

from src.schemas.asset import (
    Appearance,
    CharacterAsset,
    LocationAppearance,
    LocationAsset,
    Relationship,
)
from src.schemas.chapter_meta import ChapterFile, ChapterMetaLLMOutput
from src.tools.core import (
    WorkspacePaths,
    build_characters_brief,
    build_locations_brief,
    load_json,
    make_response,
    next_id,
    read_text,
    save_json,
)
from src.tools.llm_client import LLMClient


def _apply_character_changes(
    wp: WorkspacePaths, chap: int, changes, all_char_ids: list[str]
):
    """处理角色增删改，返回本章涉及的所有角色ID"""
    # 新角色
    for nc in changes.new:
        cid = next_id(wp.characters_dir, "char")
        asset = CharacterAsset(
            id=cid,
            name=nc.name,
            aliases=nc.aliases,
            personality=nc.personality,
            first_appearance=f"chap_{chap}",
            relationships=[
                Relationship(target=r["target_name"], relation=r["relation"])
                for r in nc.relationships
            ],
            appearances=[
                Appearance(
                    index=0,
                    label=nc.appearance_label,
                    visual_description=nc.visual_description,
                )
            ],
            current_appearance_index=0,
        )
        save_json(wp.characters_dir / f"{cid}.json", asset)
        all_char_ids.append(cid)

    # 更新已有角色
    for uc in changes.updated:
        path = wp.characters_dir / f"{uc.id}.json"
        if not path.exists():
            continue
        data = load_json(path)
        for k, v in uc.updates.items():
            data[k] = v
        save_json(path, data)
        if uc.id not in all_char_ids:
            all_char_ids.append(uc.id)

    # 外貌变化
    for ac in changes.appearance_changed:
        path = wp.characters_dir / f"{ac.id}.json"
        if not path.exists():
            continue
        data = load_json(path)
        new_index = len(data["appearances"])
        data["appearances"].append(
            {
                "index": new_index,
                "label": ac.new_label,
                "visual_description": ac.new_visual_description,
                "reference_images": [],
            }
        )
        if ac.set_current:
            data["current_appearance_index"] = new_index
        save_json(path, data)
        if ac.id not in all_char_ids:
            all_char_ids.append(ac.id)


def _apply_location_changes(
    wp: WorkspacePaths, chap: int, changes, all_loc_ids: list[str]
):
    for nl in changes.new:
        lid = next_id(wp.locations_dir, "loc")
        asset = LocationAsset(
            id=lid,
            name=nl.name,
            first_appearance=f"chap_{chap}",
            appearances=[
                LocationAppearance(
                    index=0,
                    label=nl.appearance_label,
                    visual_description=nl.visual_description,
                )
            ],
            current_appearance_index=0,
        )
        save_json(wp.locations_dir / f"{lid}.json", asset)
        all_loc_ids.append(lid)

    for ul in changes.updated:
        path = wp.locations_dir / f"{ul.id}.json"
        if not path.exists():
            continue
        data = load_json(path)
        for k, v in ul.updates.items():
            data[k] = v
        save_json(path, data)
        if ul.id not in all_loc_ids:
            all_loc_ids.append(ul.id)

    for al in changes.appearance_changed:
        path = wp.locations_dir / f"{al.id}.json"
        if not path.exists():
            continue
        data = load_json(path)
        new_index = len(data["appearances"])
        data["appearances"].append(
            {
                "index": new_index,
                "label": al.new_label,
                "visual_description": al.new_visual_description,
                "reference_images": [],
            }
        )
        if al.set_current:
            data["current_appearance_index"] = new_index
        save_json(path, data)
        if al.id not in all_loc_ids:
            all_loc_ids.append(al.id)


def run(
    novel: str, chapter: int, workspace: Path, model: str | None = None, **_
) -> str:
    wp = WorkspacePaths(workspace, novel)

    project = load_json(wp.project)
    chapter_text = read_text(wp.chap_text(chapter))

    client = LLMClient(model_name=model)
    result = client.structured_output(
        "extract_chapter_meta",
        ChapterMetaLLMOutput,
        novel_summary=project.get("summary", "（暂无，请从零生成）"),
        existing_characters_brief=build_characters_brief(wp.characters_dir),
        existing_locations_brief=build_locations_brief(wp.locations_dir),
        chapter_text=chapter_text,
    )

    # 后处理：应用资产变更
    outputs, updated = [], []
    char_ids: list[str] = []
    loc_ids: list[str] = []

    _apply_character_changes(wp, chapter, result.characters, char_ids)
    _apply_location_changes(wp, chapter, result.locations, loc_ids)

    # 更新 project.json
    project["summary"] = result.novel_summary_update
    project["current_status"] = f"chapter-{chapter}"
    save_json(wp.project, project)
    updated.append(str(wp.project))

    # 创建 chap_x.json
    chap_file = ChapterFile(
        chapter_id=chapter,
        summary=result.chapter_summary,
        characters=char_ids,
        locations=loc_ids,
        status="scanned",
    )
    save_json(wp.chap_meta(chapter), chap_file)
    outputs.append(str(wp.chap_meta(chapter)))

    return make_response(
        "success",
        f"Chapter {chapter} metadata extracted. "
        f"{len(result.characters.new)} new characters, "
        f"{len(result.locations.new)} new locations.",
        outputs=outputs,
        updated=updated,
    )
