import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SONGS_DIR = ROOT / "src" / "content" / "songs"
TIMELINE_PATH = ROOT / "output" / "timeline" / "timeline_structured.json"
CONFLICTS_PATH = ROOT / "output" / "timeline" / "song_merge_conflicts.json"
REPORT_PATH = ROOT / "output" / "timeline" / "song_merge_report.json"


def clean(text: str) -> str:
    text = (text or "").strip()
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_key(text: str) -> str:
    text = clean(text).lower()
    text = text.replace("，", "").replace(",", "")
    text = text.replace("。", "").replace(".", "")
    text = text.replace("！", "").replace("!", "")
    text = text.replace("？", "").replace("?", "")
    text = text.replace("：", "").replace(":", "")
    text = text.replace("；", "").replace(";", "")
    text = text.replace("、", "")
    text = text.replace("（", "").replace("）", "")
    text = text.replace("(", "").replace(")", "")
    text = text.replace("《", "").replace("》", "")
    text = text.replace("-", "").replace("_", "")
    text = text.replace(" ", "")
    return text


def safe_name(text: str) -> str:
    value = clean(text)
    value = re.sub(r'[<>:"/\\|?*]', " ", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value or "未命名"


def valid_title(text: str) -> bool:
    title = clean(text)
    return bool(re.search(r"[A-Za-z0-9\u4e00-\u9fff]", title))


def unique_list(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = clean(item)
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def load_songs() -> dict[str, dict[str, Any]]:
    songs: dict[str, dict[str, Any]] = {}
    for path in SONGS_DIR.glob("*.json"):
        if path.name == "index.json":
            continue
        songs[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return songs


def build_lookup(songs: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    lookup: dict[str, list[str]] = defaultdict(list)
    for song_id, song in songs.items():
        keys = {normalize_key(song.get("title", ""))}
        for alias in song.get("aliases", []):
            keys.add(normalize_key(alias))
        for key in keys:
            if key:
                lookup[key].append(song_id)
    return lookup


def timeline_note_bundle(item: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if item.get("歌曲副标题"):
        notes.append(item["歌曲副标题"])
    if item.get("是否串烧版"):
        notes.append("串烧版")
    if item.get("演唱语言"):
        notes.append(f"演唱语言：{item['演唱语言']}")
    notes.extend(item.get("其它信息", []))
    return unique_list(notes)


def timeline_work(item: dict[str, Any]) -> dict[str, str] | None:
    info = item.get("影视信息")
    if not info:
        return None
    work = {}
    if info.get("类别"):
        work["category"] = info["类别"]
    if info.get("名称"):
        work["title"] = info["名称"]
    if info.get("类型"):
        work["usage"] = info["类型"]
    return work or None


def timeline_credits(item: dict[str, Any]) -> dict[str, list[str]]:
    credits = {
        "lyricists": unique_list(item.get("词作者", [])),
        "composers": unique_list(item.get("曲作者", [])),
        "original_singers": unique_list(item.get("原唱", [])),
        "performers": unique_list(item.get("跟谁一起唱的", [])),
    }
    return {k: v for k, v in credits.items() if v}


def comparable(value: Any) -> Any:
    if isinstance(value, list):
        return sorted(normalize_key(str(item)) for item in value if clean(str(item)))
    if isinstance(value, str):
        return normalize_key(value)
    if isinstance(value, dict):
        return {k: comparable(v) for k, v in value.items()}
    return value


def make_conflict(
    song_id: str,
    song_title: str,
    timeline_item: dict[str, Any],
    field: str,
    existing_value: Any,
    timeline_value: Any,
    matched_by: str,
) -> dict[str, Any]:
    return {
        "song_id": song_id,
        "song_title": song_title,
        "timeline_year": timeline_item.get("年份"),
        "timeline_title": timeline_item.get("歌曲标题"),
        "field": field,
        "existing_value": existing_value,
        "timeline_value": timeline_value,
        "matched_by": matched_by,
    }


def choose_match(
    timeline_item: dict[str, Any],
    songs: dict[str, dict[str, Any]],
    lookup: dict[str, list[str]],
) -> tuple[str | None, str]:
    title = timeline_item.get("歌曲标题", "")
    aliases = timeline_item.get("歌曲又名", [])
    candidate_ids: list[str] = []

    title_key = normalize_key(title)
    if title_key in lookup:
        candidate_ids.extend(lookup[title_key])
    for alias in aliases:
        alias_key = normalize_key(alias)
        if alias_key in lookup:
            candidate_ids.extend(lookup[alias_key])

    candidate_ids = list(dict.fromkeys(candidate_ids))
    if not candidate_ids:
        return None, "new"
    if len(candidate_ids) == 1:
        matched_id = candidate_ids[0]
        song = songs[matched_id]
        if normalize_key(song.get("title", "")) == title_key:
            return matched_id, "title"
        return matched_id, "alias"

    timeline_work_info = timeline_work(timeline_item)
    if timeline_work_info:
        narrowed = []
        for candidate_id in candidate_ids:
            song_work = songs[candidate_id].get("work") or {}
            if all(
                normalize_key(song_work.get(key, "")) == normalize_key(value)
                for key, value in timeline_work_info.items()
                if value
            ):
                narrowed.append(candidate_id)
        if len(narrowed) == 1:
            return narrowed[0], "work"
        if len(narrowed) > 1:
            candidate_ids = narrowed

    exact = [cid for cid in candidate_ids if normalize_key(songs[cid].get("title", "")) == title_key]
    if len(exact) == 1:
        return exact[0], "title"
    return None, "ambiguous"


def ensure_song_id(title: str, songs: dict[str, dict[str, Any]]) -> str:
    base = safe_name(title)
    if base not in songs:
        return base
    suffix = 2
    while f"{base}-{suffix}" in songs:
        suffix += 1
    return f"{base}-{suffix}"


def merge_item_into_song(
    song: dict[str, Any],
    timeline_item: dict[str, Any],
    matched_by: str,
    conflicts: list[dict[str, Any]],
) -> None:
    song_id = song["id"]
    song_title = song["title"]

    year_value = timeline_item.get("年份")
    if year_value:
        if "year" not in song or not song.get("year"):
            song["year"] = year_value
        elif song.get("year") != year_value:
            conflicts.append(make_conflict(song_id, song_title, timeline_item, "year", song.get("year"), year_value, matched_by))

    timeline_aliases = unique_list(timeline_item.get("歌曲又名", []))
    if matched_by == "alias":
        timeline_title = clean(timeline_item.get("歌曲标题", ""))
        if timeline_title and normalize_key(timeline_title) != normalize_key(song_title):
            timeline_aliases.append(timeline_title)
    if timeline_aliases:
        existing_aliases = unique_list(song.get("aliases", []))
        song["aliases"] = unique_list(existing_aliases + timeline_aliases)
        if not song["aliases"]:
            song.pop("aliases", None)

    new_work = timeline_work(timeline_item)
    if new_work:
        existing_work = song.get("work") or {}
        if not existing_work:
            song["work"] = new_work
        else:
            merged_work = dict(existing_work)
            for key, value in new_work.items():
                if not value:
                    continue
                if not merged_work.get(key):
                    merged_work[key] = value
                elif normalize_key(merged_work[key]) != normalize_key(value):
                    conflicts.append(
                        make_conflict(song_id, song_title, timeline_item, f"work.{key}", merged_work[key], value, matched_by)
                    )
            song["work"] = merged_work

    new_credits = timeline_credits(timeline_item)
    if new_credits:
        credits = song.get("credits") or {}
        for key, values in new_credits.items():
            existing_values = unique_list(credits.get(key, []))
            if not existing_values:
                credits[key] = values
            elif comparable(existing_values) != comparable(values):
                conflicts.append(make_conflict(song_id, song_title, timeline_item, f"credits.{key}", existing_values, values, matched_by))
        if credits:
            song["credits"] = credits

    new_notes = timeline_note_bundle(timeline_item)
    if new_notes:
        existing_notes = unique_list(song.get("notes", []))
        song["notes"] = unique_list(existing_notes + new_notes)
        if not song["notes"]:
            song.pop("notes", None)


def create_song_from_timeline(timeline_item: dict[str, Any], songs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    song_id = ensure_song_id(timeline_item["歌曲标题"], songs)
    song: dict[str, Any] = {
        "id": song_id,
        "title": clean(timeline_item["歌曲标题"]),
    }
    if timeline_item.get("年份"):
        song["year"] = timeline_item["年份"]
    aliases = unique_list(timeline_item.get("歌曲又名", []))
    if aliases:
        song["aliases"] = aliases
    work = timeline_work(timeline_item)
    if work:
        song["work"] = work
    credits = timeline_credits(timeline_item)
    if credits:
        song["credits"] = credits
    notes = timeline_note_bundle(timeline_item)
    if notes:
        song["notes"] = notes
    return song


def write_song(song: dict[str, Any]) -> None:
    path = SONGS_DIR / f"{song['id']}.json"
    path.write_text(json.dumps(song, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rebuild_index(songs: dict[str, dict[str, Any]]) -> None:
    items = []
    for song in sorted(songs.values(), key=lambda item: normalize_key(item.get("title", ""))):
        item = {
            "id": song["id"],
            "title": song["title"],
            "has_scores": bool(song.get("scores")),
            "has_videos": bool(song.get("videos")),
        }
        if song.get("aliases"):
            item["aliases"] = song["aliases"]
        if song.get("work"):
            item["work"] = song["work"]
        if song.get("year"):
            item["year"] = song["year"]
        items.append(item)
    (SONGS_DIR / "index.json").write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    songs = load_songs()
    lookup = build_lookup(songs)
    timeline = json.loads(TIMELINE_PATH.read_text(encoding="utf-8"))
    conflicts: list[dict[str, Any]] = []
    created: list[str] = []
    matched_count = 0
    new_count = 0
    ambiguous_items: list[dict[str, Any]] = []

    for year_block in timeline.get("年份列表", []):
        for item in year_block.get("条目", []):
            title = clean(item.get("歌曲标题", ""))
            if not valid_title(title):
                ambiguous_items.append(item)
                continue
            song_id, matched_by = choose_match(item, songs, lookup)
            if song_id is None:
                if matched_by == "ambiguous":
                    ambiguous_items.append(item)
                    continue
                new_song = create_song_from_timeline(item, songs)
                songs[new_song["id"]] = new_song
                created.append(new_song["id"])
                new_count += 1
                write_song(new_song)
                lookup = build_lookup(songs)
                continue

            matched_count += 1
            merge_item_into_song(songs[song_id], item, matched_by, conflicts)

    for song in songs.values():
        write_song(song)
    rebuild_index(songs)

    conflict_payload = {
        "conflicts": conflicts,
        "ambiguous_unmatched": ambiguous_items,
    }
    CONFLICTS_PATH.write_text(json.dumps(conflict_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = {
        "matched_entries": matched_count,
        "created_songs": new_count,
        "created_song_ids": created,
        "conflict_count": len(conflicts),
        "ambiguous_unmatched_count": len(ambiguous_items),
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
