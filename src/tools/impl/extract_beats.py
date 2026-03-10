from pathlib import Path

from src.schemas.beat import BeatFile, BeatLLMOutput
from src.tools.core import (
    WorkspacePaths,
    build_characters_brief,
    build_previous_su_summaries,
    load_json,
    make_response,
    read_text,
    save_json,
)
from src.tools.llm_client import LLMClient


def run(
    novel: str, chapter: int, workspace: Path, su: int, model: str | None = None, **_
) -> str:
    wp = WorkspacePaths(workspace, novel)

    project = load_json(wp.project)
    chap_meta = load_json(wp.chap_meta(chapter))
    su_text = read_text(wp.su_text(chapter, su))

    client = LLMClient(model_name=model)
    result = client.structured_output(
        "extract_beats",
        BeatLLMOutput,
        novel_summary=project.get("summary", ""),
        chapter_summary=chap_meta["summary"],
        previous_su_summaries=build_previous_su_summaries(wp, chapter, su),
        existing_characters_brief=build_characters_brief(wp.characters_dir),
        su_text=su_text,
    )

    beat_file = BeatFile(su_id=su, chapter_id=chapter, beats=result.beats)
    save_json(wp.beats(chapter, su), beat_file)

    # 更新进度
    su_meta = load_json(wp.su_meta(chapter, su))
    su_meta["status"] = "beats_extracted"
    save_json(wp.su_meta(chapter, su), su_meta)

    for item in chap_meta.get("story_units", []):
        if item["su_id"] == su:
            item["status"] = "beats_extracted"
    save_json(wp.chap_meta(chapter), chap_meta)

    return make_response(
        "success",
        f"Extracted {len(result.beats)} beats from chapter {chapter} SU {su}.",
        outputs=[str(wp.beats(chapter, su))],
        updated=[str(wp.su_meta(chapter, su)), str(wp.chap_meta(chapter))],
    )
