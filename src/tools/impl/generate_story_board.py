import json
from pathlib import Path

from src.schemas.story_board import PageFile, StoryBoardLLMOutput
from src.tools.core import (
    WorkspacePaths,
    build_previous_su_summaries,
    load_json,
    make_response,
    save_json,
)
from src.tools.llm_client import LLMClient


def run(
    novel: str, chapter: int, workspace: Path, su: int, model: str | None = None, **_
) -> str:
    wp = WorkspacePaths(workspace, novel)

    project = load_json(wp.project)
    chap_meta = load_json(wp.chap_meta(chapter))
    su_meta = load_json(wp.su_meta(chapter, su))
    beats_data = load_json(wp.beats(chapter, su))

    client = LLMClient(model_name=model)
    result = client.structured_output(
        "generate_story_board",
        StoryBoardLLMOutput,
        novel_summary=project.get("summary", ""),
        chapter_summary=chap_meta["summary"],
        previous_su_summaries=build_previous_su_summaries(wp, chapter, su),
        su_summary=su_meta["summary"],
        beats_json=json.dumps(beats_data["beats"], indent=2, ensure_ascii=False),
    )

    outputs = []
    for page in result.pages:
        page_file = PageFile(
            page_id=f"chap_{chapter}_su_{su}_page_{page.page_index}",
            su_id=su,
            chapter_id=chapter,
            page_index=page.page_index,
            beats_used=page.beats_used,
            layout=page.layout,
            page_mood=page.page_mood,
            panels=page.panels,
        )
        out_path = wp.page(chapter, su, page.page_index)
        save_json(out_path, page_file)
        outputs.append(str(out_path))

    # 更新进度
    su_meta["status"] = "storyboard_done"
    save_json(wp.su_meta(chapter, su), su_meta)

    for item in chap_meta.get("story_units", []):
        if item["su_id"] == su:
            item["status"] = "storyboard_done"
            item["page_count"] = len(result.pages)
    save_json(wp.chap_meta(chapter), chap_meta)

    return make_response(
        "success",
        f"Generated {len(result.pages)} pages for chapter {chapter} SU {su}.",
        outputs=outputs,
        updated=[str(wp.su_meta(chapter, su)), str(wp.chap_meta(chapter))],
    )
