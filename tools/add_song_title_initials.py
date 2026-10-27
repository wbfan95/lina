import json
import re
from pathlib import Path

from pypinyin import Style, lazy_pinyin


ROOT = Path(__file__).resolve().parents[1]
SONGS_DIR = ROOT / "src" / "content" / "songs"
INDEX_PATH = SONGS_DIR / "index.json"


def is_cjk(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff"


def pick_first_meaningful_char(title: str) -> str:
    for char in title.strip():
        if char.isalnum() or is_cjk(char):
            return char
    return title.strip()[:1]


def pick_last_meaningful_char(title: str) -> str:
    for char in reversed(title.strip()):
        if char.isalnum() or is_cjk(char):
            return char
    stripped = title.strip()
    return stripped[-1:] if stripped else ""


def char_initial(char: str) -> str:
    if not char:
        return ""
    if is_cjk(char):
        value = lazy_pinyin(char, style=Style.FIRST_LETTER, strict=False)
        return (value[0] if value else "").upper()
    if char.isalpha():
        return char.upper()
    if char.isdigit():
        return char
    match = re.search(r"[A-Za-z0-9]", char)
    return match.group(0).upper() if match else ""


def compute_initials(title: str) -> tuple[str, str]:
    first_char = pick_first_meaningful_char(title)
    last_char = pick_last_meaningful_char(title)
    return char_initial(first_char), char_initial(last_char)


def update_song_file(path: Path) -> dict:
    song = json.loads(path.read_text(encoding="utf-8"))
    first_initial, last_initial = compute_initials(song.get("title", ""))


    path.write_text(json.dumps(song, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return song


def rebuild_index(songs: list[dict]) -> None:
    index_items = []
    for song in songs:
        item = {
            "id": song["id"],
            "title": song["title"],


        }
        if song.get("aliases"):
            item["aliases"] = song["aliases"]
        if song.get("work"):
            item["work"] = song["work"]
        item["has_scores"] = bool(song.get("scores"))
        item["has_videos"] = bool(song.get("videos"))
        index_items.append(item)
    INDEX_PATH.write_text(json.dumps(index_items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    songs: list[dict] = []
    for path in sorted(SONGS_DIR.glob("*.json")):
        if path.name == "index.json":
            continue
        songs.append(update_song_file(path))
    rebuild_index(songs)
    print(f"Updated initials for {len(songs)} songs.")


if __name__ == "__main__":
    main()
