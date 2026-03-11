import json
from pathlib import Path

characters_dir = Path("workspace/classroom_of_the_elite/characters")

for char_file in characters_dir.glob("char_*.json"):
    with open(char_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "relationships" in data:
        for rel in data["relationships"]:
            if "target_name" in rel and "target" not in rel:
                rel["target"] = rel.pop("target_name")

        with open(char_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Fixed {char_file.name}")
