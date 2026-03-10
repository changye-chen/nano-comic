from pathlib import Path

from src.schemas.chapter_meta import ChapterFile, StoryUnitProgress
from src.schemas.story_unit import StoryUnitFile, StoryUnitLLMOutput
from src.tools.core import (
    WorkspacePaths,
    build_characters_brief,
    build_locations_brief,
    fuzzy_find,
    load_json,
    make_response,
    read_text,
    save_json,
    write_text,
)
from src.tools.llm_client import LLMClient


def _locate_anchors(text: str, entries) -> list[int]:
    """用 start_anchor 定位每个 SU 的起始位置，返回排序后的位置列表"""
    positions = []
    for entry in entries:
        pos = fuzzy_find(text, entry.start_anchor)
        if pos is None:
            raise ValueError(f"无法定位锚点: '{entry.start_anchor[:30]}...'")
        positions.append(pos)

    # 确保单调递增
    for i in range(1, len(positions)):
        if positions[i] <= positions[i - 1]:
            raise ValueError(
                f"锚点顺序异常: SU{i} 位置 {positions[i]} <= SU{i - 1} 位置 {positions[i - 1]}"
            )
    return positions


def run(
    novel: str, chapter: int, workspace: Path, model: str | None = None, **_
) -> str:
    wp = WorkspacePaths(workspace, novel)
    chapter_text = read_text(wp.chap_text(chapter))
    chap_meta = load_json(wp.chap_meta(chapter))

    client = LLMClient(model_name=model)

    # LLM 调用（含一次重试）
    last_error = None
    positions = None
    result = None

    for attempt in range(2):
        result = client.structured_output(
            "split_story_unit",
            StoryUnitLLMOutput,
            chapter_summary=chap_meta["summary"],
            existing_characters_brief=build_characters_brief(wp.characters_dir),
            existing_locations_brief=build_locations_brief(wp.locations_dir),
            chapter_text=chapter_text,
        )
        try:
            positions = _locate_anchors(chapter_text, result.story_units)
            break
        except ValueError as e:
            last_error = e

    if positions is None:
        raise RuntimeError(f"锚点匹配失败（已重试）: {last_error}")

    # 切分文本并写文件
    entries = result.story_units
    outputs = []

    for i, entry in enumerate(entries):
        su_id = i + 1
        start = positions[i]
        end = positions[i + 1] if i + 1 < len(positions) else len(chapter_text)
        su_text = chapter_text[start:end]

        su_file = StoryUnitFile(
            su_id=su_id,
            chapter_id=chapter,
            summary=entry.summary,
            characters=entry.characters,
            location=entry.location,
            char_range=[start, end],
        )
        save_json(wp.su_meta(chapter, su_id), su_file)
        write_text(wp.su_text(chapter, su_id), su_text)
        outputs.append(str(wp.su_meta(chapter, su_id)))

    # 更新 chap_x.json
    chap_meta["story_unit_count"] = len(entries)
    chap_meta["story_units"] = [
        StoryUnitProgress(su_id=i + 1, status="split").model_dump()
        for i in range(len(entries))
    ]
    chap_meta["status"] = "split"
    save_json(wp.chap_meta(chapter), chap_meta)

    return make_response(
        "success",
        f"Chapter {chapter} split into {len(entries)} story units.",
        outputs=outputs,
        updated=[str(wp.chap_meta(chapter))],
    )
