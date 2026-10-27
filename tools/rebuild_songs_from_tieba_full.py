import json
import re
import shutil
import time
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
TIEBA_DIR = ROOT / "output" / "tieba_full"
SONGS_DIR = ROOT / "src" / "content" / "songs"
SCORES_DIR = ROOT / "src" / "content" / "scores"

THREAD_IDS = [
    "586571552",
    "586590468",
    "586627553",
    "586645910",
    "586640749",
    "586645504",
    "586782339",
    "586900188",
    "586956184",
    "587020071",
    "587166647",
    "587193059",
    "587190955",
    "587276384",
    "587164663",
    "587237185",
    "587275601",
    "587255595",
    "587012297",
    "587275838",
    "587276019",
    "587276152",
    "587276279",
]

WORK_CATEGORIES = [
    "电视剧",
    "电视连续剧",
    "电视片",
    "电影",
    "故事片",
    "纪录片",
    "动画片",
    "广播剧",
    "歌舞剧",
    "舞剧",
    "舞蹈",
    "音乐电视",
    "专题片",
    "专题节目",
    "大型专题片",
    "大型文献纪录片",
    "电视剧片",
]
USAGE_KEYWORDS = [
    "主题曲",
    "片头曲",
    "片尾曲",
    "插曲",
    "主题歌",
    "片中歌",
    "片中曲",
    "开场曲",
    "结束曲",
]
STOP_MARKERS = [
    "简谱",
    "歌谱",
    "音频地址",
    "视频地址",
    "电视剧视频",
    "视频：",
    "视频:",
    "伴奏",
]
SKIP_PREFIXES = [
    "回复",
    "楼主",
    "叶子",
    "懒姐",
    "谢谢",
]
URL_RE = re.compile(r"https?://\S+")
TITLE_RE = re.compile(r"^《([^》]+)》(?:（又名《([^》]+)》）)?(?:\s*[（(]又名[《“\"]?([^》”\")]+)[》”\")][）)]?)?(.*)$")
WORK_RE = re.compile(
    r"^(?P<category>%s)《(?P<title>[^》]+)》(?P<usage>.*)$"
    % "|".join(re.escape(item) for item in WORK_CATEGORIES)
)


def clean_text(text: str) -> str:
    text = text.replace("\r", "\n").replace("\u3000", " ").replace("\xa0", " ")
    text = text.replace("\x18", "").replace("\ufeff", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def safe_name(text: str) -> str:
    text = clean_text(text)
    text = re.sub(r'[<>:"/\\|?*]', "-", text)
    text = text.strip(" .")
    return text or "未命名"


def split_lines(text_chunks: list[str]) -> list[str]:
    lines: list[str] = []
    for chunk in text_chunks:
        for raw in clean_text(chunk).splitlines():
            line = raw.strip()
            if line:
                lines.append(line)
    return lines


def content_texts(post: dict[str, Any]) -> list[str]:
    texts = []
    for item in post.get("content", []):
        if item.get("type") == 0 and item.get("text"):
            texts.append(item["text"])
    return texts


def content_images(post: dict[str, Any]) -> list[str]:
    images = []
    for item in post.get("content", []):
        if item.get("type") == 3:
            url = item.get("origin_src") or item.get("big_cdn_src") or item.get("cdn_src_active") or item.get("cdn_src")
            if url:
                images.append(url)
    return images


def parse_title(line: str) -> tuple[str | None, list[str], str]:
    line = clean_text(line)
    match = TITLE_RE.match(line)
    if not match:
        return None, [], line
    title = clean_text(match.group(1))
    alias_candidates = [match.group(2), match.group(3)]
    aliases = [clean_text(value) for value in alias_candidates if value and clean_text(value) and clean_text(value) != title]
    rest = clean_text(match.group(4) or "")
    return title, aliases, rest


def parse_work(lines: list[str], start_index: int) -> tuple[dict[str, str] | None, int, str | None]:
    if start_index >= len(lines):
        return None, start_index, None
    line = lines[start_index]
    match = WORK_RE.match(line)
    if not match:
        return None, start_index, None
    usage_tail = clean_text(match.group("usage"))
    usage_tail = usage_tail.lstrip("：: ")
    usage = usage_tail
    extra = None
    for keyword in USAGE_KEYWORDS:
        marker_index = usage_tail.find(keyword)
        if marker_index >= 0:
            usage = usage_tail[: marker_index + len(keyword)]
            extra = clean_text(usage_tail[marker_index + len(keyword) :])
            break
    work = {
        "category": clean_text(match.group("category")),
        "title": clean_text(match.group("title")),
    }
    if usage:
        work["usage"] = usage
    return work, start_index + 1, extra


def looks_like_credit(line: str) -> bool:
    if any(marker in line for marker in STOP_MARKERS):
        return False
    if len(line) > 80 and ("词" not in line and "曲" not in line and "演唱" not in line):
        return False
    credit_markers = ["作词", "作曲", "编曲", "演唱", "原唱", "词曲", "词", "曲", "民歌"]
    return any(marker in line for marker in credit_markers)


def extract_names(text: str) -> list[str]:
    text = clean_text(text)
    text = text.strip("：:，,。；; ")
    if not text:
        return []
    parts = re.split(r"[、/／,，和与及 ]+", text)
    return [item.strip() for item in parts if item.strip()]


def parse_credit_lines(lines: list[str], start_index: int) -> tuple[dict[str, list[str]], list[str], int]:
    credits = {
        "lyricists": [],
        "composers": [],
        "arrangers": [],
        "performers": [],
        "original_singers": [],
    }
    notes: list[str] = []
    credit_lines: list[str] = []
    index = start_index
    while index < len(lines) and looks_like_credit(lines[index]):
        credit_lines.append(lines[index])
        index += 1
        if len(credit_lines) >= 4:
            break

    for line in credit_lines:
        compact = clean_text(line)
        if compact in {"歌词：", "歌词:"}:
            continue

        explicit_patterns = [
            ("lyricists", r"作词[:：]\s*([^。；;]+)"),
            ("composers", r"作曲[:：]\s*([^。；;]+)"),
            ("arrangers", r"编曲[:：]\s*([^。；;]+)"),
            ("performers", r"演唱[:：]\s*([^。；;]+)"),
            ("original_singers", r"原唱[:：]\s*([^。；;]+)"),
        ]
        matched_explicit = False
        for key, pattern in explicit_patterns:
            found = re.search(pattern, compact)
            if found:
                credits[key].extend(extract_names(found.group(1)))
                matched_explicit = True

        pair_match = re.match(r"^(?P<lyricist>.+?)\s+词\s+(?P<composer>.+?)\s+曲(?:\s+(?P<tail>.+))?$", compact)
        if pair_match:
            credits["lyricists"].extend(extract_names(pair_match.group("lyricist")))
            credits["composers"].extend(extract_names(pair_match.group("composer")))
            tail = clean_text(pair_match.group("tail") or "")
            if tail:
                if "演唱" in tail:
                    tail = tail.replace("演唱", "").strip()
                    credits["performers"].extend(extract_names(tail))
                else:
                    notes.append(compact)
            continue

        both_match = re.match(r"^(?P<name>.+?)\s*词曲(?:\s+(?P<tail>.+))?$", compact)
        if both_match:
            names = extract_names(both_match.group("name"))
            credits["lyricists"].extend(names)
            credits["composers"].extend(names)
            tail = clean_text(both_match.group("tail") or "")
            if tail:
                if "演唱" in tail:
                    credits["performers"].extend(extract_names(tail.replace("演唱", "")))
                else:
                    notes.append(compact)
            continue

        performer_prefix = re.match(r"^(合唱|独唱|领唱|对唱)[:：]?\s*(.+)$", compact)
        if performer_prefix:
            credits["performers"].extend(extract_names(performer_prefix.group(2)))
            continue

        if compact.endswith("民歌"):
            notes.append(compact)
            continue

        if not matched_explicit and compact not in notes:
            notes.append(compact)

    for key in credits:
        deduped: list[str] = []
        seen: set[str] = set()
        for item in credits[key]:
            if item and item not in seen:
                deduped.append(item)
                seen.add(item)
        credits[key] = deduped
    return credits, notes, index


def extract_videos(lines: list[str]) -> list[str]:
    urls: list[str] = []
    for line in lines:
        urls.extend(URL_RE.findall(line))
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        if url not in seen:
            result.append(url)
            seen.add(url)
    return result


def extract_lyrics(lines: list[str], start_index: int) -> tuple[str | None, list[str]]:
    lyrics_lines: list[str] = []
    trailing_notes: list[str] = []
    for line in lines[start_index:]:
        normalized = clean_text(line)
        if any(marker in normalized for marker in STOP_MARKERS):
            tail = normalized.split("：", 1)[0].split(":", 1)[0]
            if tail and tail not in STOP_MARKERS and tail not in trailing_notes:
                trailing_notes.append(tail)
            continue
        if normalized in {"歌词：", "歌词:"}:
            continue
        lyrics_lines.append(normalized)
    lyrics_text = "\n".join(line for line in lyrics_lines if line).strip()
    return lyrics_text or None, trailing_notes


def is_song_candidate(lines: list[str]) -> bool:
    if not lines:
        return False
    first = lines[0]
    if any(first.startswith(prefix) for prefix in SKIP_PREFIXES):
        return False
    title, _, _ = parse_title(first)
    if title:
        return True
    if len(lines) >= 2 and first.startswith("《") and len(lines[1]) > 3:
        return True
    return False


def build_entry(post: dict[str, Any], tid: str) -> dict[str, Any] | None:
    texts = content_texts(post)
    lines = split_lines(texts)
    if not is_song_candidate(lines):
        return None

    title, aliases, title_rest = parse_title(lines[0])
    if not title:
        return None

    index = 1
    work, index, work_extra = parse_work(lines, index)
    parse_lines = lines[:]
    if work_extra:
        parse_lines.insert(index, work_extra)
    credits, credit_notes, index = parse_credit_lines(parse_lines, index)
    lyrics_text, trailing_notes = extract_lyrics(parse_lines, index)
    videos = extract_videos(lines)
    images = content_images(post)

    notes: list[str] = []
    if title_rest:
        notes.append(title_rest)
    notes.extend(item for item in credit_notes if item not in notes)
    notes.extend(item for item in trailing_notes if item not in notes)

    has_credit_values = any(credits.get(key) for key in credits)
    meaningful = bool(lyrics_text or images or videos or has_credit_values)
    if not meaningful:
        return None

    entry: dict[str, Any] = {
        "title": title,
        "aliases": aliases,
        "work": work,
        "credits": credits,
        "lyrics_text": lyrics_text,
        "score_urls": images,
        "videos": videos,
        "notes": notes,
        "_meta": {
            "tid": tid,
            "post_id": str(post.get("id", "")),
            "floor": post.get("floor"),
        },
    }
    return entry


def dedupe_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for entry in entries:
        work = entry.get("work") or {}
        lyrics_text = entry.get("lyrics_text") or ""
        if work.get("title") or work.get("usage"):
            key = (
                "work",
                entry["title"],
                work.get("title", ""),
                work.get("usage", ""),
            )
        elif lyrics_text:
            key = ("lyrics", entry["title"], lyrics_text, "")
        else:
            key = (
                "work",
                entry["title"],
                work.get("title", ""),
                work.get("usage", ""),
            )
        current = grouped.get(key)
        if current is None:
            grouped[key] = entry
            continue

        for alias in entry.get("aliases", []):
            if alias not in current["aliases"]:
                current["aliases"].append(alias)
        for note in entry.get("notes", []):
            if note not in current["notes"]:
                current["notes"].append(note)
        for key_name, values in entry.get("credits", {}).items():
            current["credits"].setdefault(key_name, [])
            for value in values:
                if value not in current["credits"][key_name]:
                    current["credits"][key_name].append(value)
        for url in entry.get("score_urls", []):
            if url not in current["score_urls"]:
                current["score_urls"].append(url)
        for url in entry.get("videos", []):
            if url not in current["videos"]:
                current["videos"].append(url)
        if not current.get("lyrics_text") and entry.get("lyrics_text"):
            current["lyrics_text"] = entry["lyrics_text"]
    return list(grouped.values())


def choose_id(entry: dict[str, Any], used_ids: set[str], duplicate_count: int) -> str:
    candidates = [entry["title"]]
    work = entry.get("work") or {}
    if work.get("title"):
        candidates.append(f"{entry['title']}-{work['title']}")
    if work.get("usage"):
        candidates.append(f"{entry['title']}-{work['usage']}")
    if entry.get("aliases"):
        candidates.append(f"{entry['title']}-{entry['aliases'][0]}")
    if duplicate_count > 1:
        candidates.append(f"{entry['title']}-{duplicate_count}")

    for candidate in candidates:
        song_id = safe_name(candidate)
        if song_id not in used_ids:
            used_ids.add(song_id)
            return song_id

    suffix = 2
    base = safe_name(entry["title"])
    while f"{base}-{suffix}" in used_ids:
        suffix += 1
    result = f"{base}-{suffix}"
    used_ids.add(result)
    return result


def prune_dict(data: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, list) and not value:
            continue
        if isinstance(value, dict):
            nested = prune_dict(value)
            if nested:
                result[key] = nested
            continue
        if isinstance(value, str) and not value.strip():
            continue
        result[key] = value
    return result


def fetch_binary(url: str, referer: str) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/135.0.0.0 Safari/537.36"
            ),
            "Referer": referer,
        },
    )
    with urlopen(request, timeout=30) as response:
        return response.read()


def download_scores(song_id: str, score_urls: list[str]) -> list[str]:
    if not score_urls:
        return []
    target_dir = SCORES_DIR / song_id
    target_dir.mkdir(parents=True, exist_ok=True)
    saved_files: list[str] = []
    for index, url in enumerate(score_urls, start=1):
        parsed = urlparse(url)
        suffix = Path(parsed.path).suffix.lower() or ".jpg"
        if suffix not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
            suffix = ".jpg"
        filename = f"{index:02d}{'.jpg' if suffix in {'.jpeg', '.jpg'} else suffix}"
        target_path = target_dir / filename
        if not target_path.exists():
            binary = fetch_binary(url, "https://tieba.baidu.com/")
            target_path.write_bytes(binary)
            time.sleep(0.15)
        saved_files.append(filename)
    return saved_files


def rebuild() -> None:
    if SONGS_DIR.exists():
        shutil.rmtree(SONGS_DIR)
    if SCORES_DIR.exists():
        shutil.rmtree(SCORES_DIR)
    SONGS_DIR.mkdir(parents=True, exist_ok=True)
    SCORES_DIR.mkdir(parents=True, exist_ok=True)

    raw_entries: list[dict[str, Any]] = []
    skipped_posts: list[dict[str, Any]] = []

    for tid in THREAD_IDS:
        merged_path = TIEBA_DIR / tid / "page_pc_merged.json"
        data = json.loads(merged_path.read_text(encoding="utf-8"))
        for post in data.get("post_list", []):
            entry = build_entry(post, tid)
            if entry is None:
                lines = split_lines(content_texts(post))
                if lines:
                    skipped_posts.append(
                        {
                            "tid": tid,
                            "post_id": str(post.get("id", "")),
                            "floor": post.get("floor"),
                            "first_line": lines[0],
                        }
                    )
                continue
            raw_entries.append(entry)

    entries = dedupe_entries(raw_entries)
    title_counts = defaultdict(int)
    used_ids: set[str] = set()
    normalized_entries: list[dict[str, Any]] = []

    for entry in sorted(entries, key=lambda item: item["title"]):
        title_counts[entry["title"]] += 1
        song_id = choose_id(entry, used_ids, title_counts[entry["title"]])
        score_files = download_scores(song_id, entry.get("score_urls", []))
        song = prune_dict(
            {
                "id": song_id,
                "title": entry["title"],
                "aliases": entry.get("aliases", []),
                "work": entry.get("work"),
                "credits": entry.get("credits"),
                "lyrics": {"language": "zh", "text": entry.get("lyrics_text")} if entry.get("lyrics_text") else None,
                "scores": score_files,
                "videos": entry.get("videos", []),
                "notes": entry.get("notes", []),
            }
        )
        normalized_entries.append(song)
        (SONGS_DIR / f"{song_id}.json").write_text(
            json.dumps(song, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    index_items = []
    for song in normalized_entries:
        item = {
            "id": song["id"],
            "title": song["title"],
            "aliases": song.get("aliases", []),
            "work": song.get("work"),
            "has_scores": bool(song.get("scores")),
            "has_videos": bool(song.get("videos")),
        }
        index_items.append(prune_dict(item))

    (SONGS_DIR / "index.json").write_text(
        json.dumps(index_items, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "raw_candidate_count": len(raw_entries),
        "song_count": len(normalized_entries),
        "score_folder_count": len([song for song in normalized_entries if song.get("scores")]),
        "skipped_post_count": len(skipped_posts),
        "skipped_posts_sample": skipped_posts[:120],
    }
    report_path = ROOT / "output" / "rebuild_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(normalized_entries)} songs.")
    print(f"Songs with scores: {report['score_folder_count']}")
    print(f"Skipped posts: {len(skipped_posts)}")
    print(f"Report: {report_path.relative_to(ROOT)}")


if __name__ == "__main__":
    rebuild()
