import json
import time
from difflib import SequenceMatcher
from pathlib import Path

from pydantic import BaseModel


class WorkspacePaths:
    """基于约定的路径管理器"""

    def __init__(self, workspace: Path, novel: str):
        self.root = workspace / novel
        self.project = self.root / "project.json"
        self.characters_dir = self.root / "characters"
        self.locations_dir = self.root / "locations"

    def chap_dir(self, chap: int) -> Path:
        return self.root / f"chap_{chap}"

    def chap_text(self, chap: int) -> Path:
        return self.chap_dir(chap) / f"chap_{chap}.txt"

    def chap_meta(self, chap: int) -> Path:
        return self.chap_dir(chap) / f"chap_{chap}.json"

    def su_dir(self, chap: int, su: int) -> Path:
        return self.chap_dir(chap) / f"su_{su}"

    def su_meta(self, chap: int, su: int) -> Path:
        return self.su_dir(chap, su) / f"su_{su}.json"

    def su_text(self, chap: int, su: int) -> Path:
        return self.su_dir(chap, su) / f"su_{su}.txt"

    def beats(self, chap: int, su: int) -> Path:
        return self.su_dir(chap, su) / f"su_{su}_beats.json"

    def page(self, chap: int, su: int, pg: int) -> Path:
        return self.su_dir(chap, su) / f"su_{su}_page_{pg}.json"

    def prompt_file(self, chap: int, su: int, pg: int) -> Path:
        return self.su_dir(chap, su) / f"su_{su}_page_{pg}_prompt.json"


# ==================== 文件 I/O ====================


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, BaseModel):
        text = data.model_dump_json(indent=2, ensure_ascii=False)
    else:
        text = json.dumps(data, indent=2, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ==================== 响应 ====================


def make_response(
    status: str,
    message: str,
    outputs: list[str] | None = None,
    updated: list[str] | None = None,
) -> str:
    return json.dumps(
        {
            "status": status,
            "message": message,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "outputs": outputs or [],
            "updated": updated or [],
        },
        indent=2,
        ensure_ascii=False,
    )


# ==================== ID 生成 ====================


def next_id(directory: Path, prefix: str) -> str:
    """扫描目录下已有文件，返回下一个ID，如 char_003"""
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)
        return f"{prefix}_001"
    existing = [f.stem for f in directory.glob(f"{prefix}_*.json")]
    if not existing:
        return f"{prefix}_001"
    nums = [int(name.split("_")[-1]) for name in existing]
    return f"{prefix}_{max(nums) + 1:03d}"


# ==================== 上下文构建 ====================


def build_characters_brief(characters_dir: Path) -> str:
    if not characters_dir.exists() or not list(characters_dir.glob("char_*.json")):
        return "（暂无角色档案）"
    lines = []
    for f in sorted(characters_dir.glob("char_*.json")):
        c = load_json(f)
        cur = c["appearances"][c["current_appearance_index"]]
        aliases = "、".join(c.get("aliases", []))
        alias_part = f" | 别名：{aliases}" if aliases else ""
        desc_short = cur["visual_description"][:50]
        lines.append(
            f'- {c["id"]} | {c["name"]}{alias_part} | 当前外貌：{cur["label"]}-{desc_short}'
        )
    return "\n".join(lines)


def build_locations_brief(locations_dir: Path) -> str:
    if not locations_dir.exists() or not list(locations_dir.glob("loc_*.json")):
        return "（暂无场景档案）"
    lines = []
    for f in sorted(locations_dir.glob("loc_*.json")):
        loc = load_json(f)
        cur = loc["appearances"][loc["current_appearance_index"]]
        desc_short = cur["visual_description"][:50]
        lines.append(
            f'- {loc["id"]} | {loc["name"]} | {cur["label"]}-{desc_short}'
        )
    return "\n".join(lines)


def build_characters_detail(characters_dir: Path, char_ids: list[str]) -> str:
    """完整外貌描述，用于绘图提示词生成"""
    if not char_ids:
        return "（无角色引用）"
    blocks = []
    for cid in char_ids:
        path = characters_dir / f"{cid}.json"
        if not path.exists():
            continue
        c = load_json(path)
        cur = c["appearances"][c["current_appearance_index"]]
        blocks.append(
            f"### {c['name']} ({c['id']})\n"
            f"外貌阶段：{cur['label']}\n"
            f"视觉描述：{cur['visual_description']}\n"
            f"性格：{c['personality']}"
        )
    return "\n\n".join(blocks) if blocks else "（无角色引用）"


def build_locations_detail(locations_dir: Path, loc_ids: list[str]) -> str:
    if not loc_ids:
        return "（无场景引用）"
    blocks = []
    for lid in loc_ids:
        path = locations_dir / f"{lid}.json"
        if not path.exists():
            continue
        loc = load_json(path)
        cur = loc["appearances"][loc["current_appearance_index"]]
        blocks.append(
            f"### {loc['name']} ({loc['id']})\n"
            f"状态：{cur['label']}\n"
            f"视觉描述：{cur['visual_description']}"
        )
    return "\n\n".join(blocks) if blocks else "（无场景引用）"


def build_previous_su_summaries(wp: WorkspacePaths, chap: int, current_su: int) -> str:
    summaries = []
    for i in range(1, current_su):
        p = wp.su_meta(chap, i)
        if p.exists():
            su = load_json(p)
            summaries.append(f"叙事单元{i}：{su['summary']}")
    return "\n".join(summaries) if summaries else "（这是本章第一个叙事单元）"


# ==================== 模糊匹配 ====================


def fuzzy_find(text: str, anchor: str, threshold: float = 0.65) -> int | None:
    """在text中模糊查找anchor，返回匹配起始位置"""
    # 精确查找
    pos = text.find(anchor)
    if pos != -1:
        return pos

    # 粗搜
    window = len(anchor)
    best_pos, best_ratio = -1, 0.0
    step = max(1, window // 4)

    for i in range(0, max(1, len(text) - window + 1), step):
        ratio = SequenceMatcher(None, anchor, text[i : i + window]).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_pos = i

    # 精搜
    if best_pos >= 0:
        lo = max(0, best_pos - step)
        hi = min(len(text) - window + 1, best_pos + step + 1)
        for i in range(lo, max(lo + 1, hi)):
            ratio = SequenceMatcher(None, anchor, text[i : i + window]).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_pos = i

    return best_pos if best_ratio >= threshold else None
