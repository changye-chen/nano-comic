import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(prog="nano-comic")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p):
        p.add_argument("--novel", required=True, help="小说名称")
        p.add_argument("--chapter", type=int, required=True, help="章节编号")
        p.add_argument("--workspace", default="./workspace", help="工作区路径")
        p.add_argument("--model", default=None, help="LLM 模型名称")

    p1 = sub.add_parser("extract_chapter_meta")
    add_common(p1)

    p2 = sub.add_parser("split_story_unit")
    add_common(p2)

    p3 = sub.add_parser("extract_beats")
    add_common(p3)
    p3.add_argument("--su", type=int, required=True, help="叙事单元编号")

    p4 = sub.add_parser("generate_story_board")
    add_common(p4)
    p4.add_argument("--su", type=int, required=True, help="叙事单元编号")

    p5 = sub.add_parser("generate_manga_prompt")
    add_common(p5)
    p5.add_argument("--su", type=int, required=True, help="叙事单元编号")
    p5.add_argument("--page", type=int, required=True, help="页码")

    p6 = sub.add_parser("generate_image")
    add_common(p6)
    p6.add_argument("--su", type=int, required=True, help="叙事单元编号")
    p6.add_argument("--page", type=int, required=True, help="页码")

    args = parser.parse_args()

    from src.tools.impl.extract_beats import run as extract_beats
    from src.tools.impl.extract_chapter_meta import run as extract_chapter_meta
    from src.tools.impl.generate_image import run as generate_image
    from src.tools.impl.generate_manga_prompt import run as generate_manga_prompt
    from src.tools.impl.generate_story_board import run as generate_story_board
    from src.tools.impl.split_story_unit import run as split_story_unit

    dispatch = {
        "extract_chapter_meta": extract_chapter_meta,
        "split_story_unit": split_story_unit,
        "extract_beats": extract_beats,
        "generate_story_board": generate_story_board,
        "generate_manga_prompt": generate_manga_prompt,
        "generate_image": generate_image,
    }

    try:
        result = dispatch[args.command](
            novel=args.novel,
            chapter=args.chapter,
            workspace=Path(args.workspace),
            su=getattr(args, "su", None),
            page=getattr(args, "page", None),
            model=args.model,
        )
        print(result)
    except Exception as e:
        from src.tools.core import make_response

        print(make_response("error", f"{type(e).__name__}: {e}"), file=sys.stderr)
        sys.exit(1)
