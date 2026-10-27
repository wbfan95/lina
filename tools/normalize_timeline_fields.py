import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "output" / "timeline" / "timeline_extracted.json"
OUTPUT_PATH = ROOT / "output" / "timeline" / "timeline_structured.json"

SCREEN_CATEGORIES = [
    "电视剧",
    "电视连续剧",
    "电视片",
    "电影",
    "纪录片",
    "广播剧",
    "动画片",
    "舞蹈",
    "舞剧",
]
SCREEN_USAGE = [
    "主题曲",
    "主题歌",
    "片头曲",
    "片尾曲",
    "插曲",
    "片中曲",
    "片中歌",
    "开场曲",
    "结束曲",
]


def clean(text: str) -> str:
    text = text or ""
    text = text.replace("\u3000", " ").replace("\xa0", " ").replace("\r", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ，,。；;（）()")


def split_names(text: str) -> list[str]:
    text = clean(text)
    if not text:
        return []
    text = text.replace("等演唱", "").replace("等", "")
    parts = re.split(r"[、，,/／和与及 ]+", text)
    return [clean(item) for item in parts if clean(item)]


def unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def normalize_year(value: str) -> int | None:
    value = clean(value)
    if not value:
        return None
    if len(value) == 2 and value.isdigit():
        number = int(value)
        return 1900 + number if number >= 30 else 2000 + number
    if len(value) == 4 and value.isdigit():
        return int(value)
    return None


def extract_aliases(text: str) -> tuple[list[str], str]:
    aliases: list[str] = []

    def repl(match: re.Match[str]) -> str:
        alias = clean(match.group(1))
        if alias:
            aliases.append(alias)
        return " "

    patterns = [
        r"又名《([^》]+)》",
        r"原名《([^》]+)》",
    ]
    remaining = text
    for pattern in patterns:
        remaining = re.sub(pattern, repl, remaining)
    return unique(aliases), remaining


def extract_language(text: str) -> tuple[str | None, str]:
    language = None
    remaining = text
    mappings = [
        (r"（第一段用日语演唱）", "日语"),
        (r"（日语演唱）", "日语"),
        (r"（用日语演唱）", "日语"),
        (r"（用英语演唱）", "英语"),
        (r"（英语演唱）", "英语"),
        (r"（英文演唱）", "英语"),
    ]
    for pattern, label in mappings:
        if re.search(pattern, remaining):
            language = label
            remaining = re.sub(pattern, " ", remaining)
    return language, remaining


def extract_medley(text: str) -> tuple[bool, str]:
    medley = "串烧版" in text
    return medley, re.sub(r"（串烧版）", " ", text)


def extract_subtitle(text: str) -> tuple[str | None, str]:
    subtitle = None
    remaining = text
    candidates = re.findall(r"（([^（）]+)）", text)
    for item in candidates:
        value = clean(item)
        if not value:
            continue
        if "旅游节歌曲" in value or "运动会" in value or "开幕式演唱" in value:
            subtitle = value
            remaining = remaining.replace(f"（{item}）", " ")
            break
        if value.endswith("歌曲") and "原唱" not in value and "主题" not in value:
            subtitle = value
            remaining = remaining.replace(f"（{item}）", " ")
            break
    return subtitle, remaining


def extract_original_singers(text: str) -> tuple[list[str], str]:
    originals: list[str] = []
    remaining = text

    def repl_before(match: re.Match[str]) -> str:
        originals.extend(split_names(match.group(1)))
        tail = clean(match.group(2) or "")
        return f" {tail} " if tail else " "

    def repl_after(match: re.Match[str]) -> str:
        originals.extend(split_names(match.group(1)))
        return " "

    remaining = re.sub(r"（([^（）]+?)原唱([^（）]*)）", repl_before, remaining)
    remaining = re.sub(r"([^，。,；;（）()《》]+?)原唱", repl_after, remaining)
    return unique([item for item in originals if item not in {"翻唱曲"}]), remaining


def extract_cosingers(text: str) -> tuple[list[str], str]:
    cosingers: list[str] = []
    remaining = text
    patterns = [
        r"（([^（）]+?)演唱）",
        r"([^，。,；;（）()]+?)及群星演唱",
        r"([^，。,；;（）()]+?)及李娜演唱",
        r"([^，。,；;（）()]+?)演唱",
    ]

    def consume(names_text: str) -> None:
        names = split_names(names_text)
        filtered = [name for name in names if name != "李娜"]
        if "群星" in names_text and "群星" not in filtered:
            filtered.append("群星")
        if "众歌星" in names_text and "众歌星" not in filtered:
            filtered.append("众歌星")
        cosingers.extend(filtered)

    for pattern in patterns:
        for match in list(re.finditer(pattern, remaining)):
            value = match.group(1)
            if "原唱" in value:
                continue
            consume(value)
        remaining = re.sub(pattern, lambda m: " " if "原唱" not in m.group(1) else m.group(0), remaining)
    return unique(cosingers), remaining


def extract_screen_info(entry: dict[str, Any], raw: str, notes: str) -> tuple[dict[str, Any] | None, str]:
    category = entry.get("type", "")
    title = clean(entry.get("work_title", ""))
    usage = clean(entry.get("usage", ""))
    working = notes

    info = None
    if category in SCREEN_CATEGORIES and title:
        info = {
            "类别": category,
            "名称": title,
            "类型": usage or None,
            "拍摄年份": None,
        }

    pattern = re.compile(
        rf"({'|'.join(map(re.escape, SCREEN_CATEGORIES))})《([^》]+)》\s*({'|'.join(map(re.escape, SCREEN_USAGE))})"
    )
    source = f"{raw} {notes}"
    match = pattern.search(source)
    if match:
        info = {
            "类别": clean(match.group(1)),
            "名称": clean(match.group(2)),
            "类型": clean(match.group(3)),
            "拍摄年份": None,
        }
        working = working.replace(match.group(0), " ")

    if info:
        year_match = re.search(r"(?:百度百科写)?(?:就是)?(\d{2,4})年[^。；，)]*(?:开机拍摄|开机|拍摄|拍的|出品)", source)
        if year_match:
            info["拍摄年份"] = normalize_year(year_match.group(1))
            working = re.sub(r"（[^（）]*?(?:百度百科写)?(?:就是)?\d{2,4}年[^（）]*?(?:开机拍摄|开机|拍摄|拍的|出品)[^（）]*?）", " ", working)
            working = re.sub(r"(?:百度百科写)?(?:就是)?\d{2,4}年[^。；，)]*(?:开机拍摄|开机|拍摄|拍的|出品)", " ", working)

    return info, working


def parse_credit_fields(text: str) -> tuple[list[str], list[str], str, bool]:
    cleaned = text
    lyricists: list[str] = []
    composers: list[str] = []

    ambiguous = False
    if cleaned.count("作词") > 1 or cleaned.count("作曲") > 1:
        ambiguous = True

    if "作词，" in cleaned and "作曲" in cleaned and "。《" in cleaned:
        ambiguous = True

    if ambiguous:
        return [], [], text, True

    both_patterns = [
        r"([^，。,；;（）()《》]+?)作词作曲",
        r"([^，。,；;（）()《》]+?)词作曲",
    ]
    for pattern in both_patterns:
        match = re.search(pattern, cleaned)
        if match:
            names = split_names(match.group(1))
            lyricists.extend(names)
            composers.extend(names)
            cleaned = cleaned.replace(match.group(0), " ")
            return unique(lyricists), unique(composers), cleaned, False

    lyric_match = re.search(r"([^，。,；;（）()《》]+?)作词", cleaned)
    if lyric_match:
        lyricists.extend(split_names(lyric_match.group(1)))
        cleaned = cleaned.replace(lyric_match.group(0), " ")

    composer_match = re.search(r"([^，。,；;（）()《》]+?)作曲", cleaned)
    if composer_match:
        composers.extend(split_names(composer_match.group(1)))
        cleaned = cleaned.replace(composer_match.group(0), " ")

    return unique(lyricists), unique(composers), cleaned, False


def extract_other_info(text: str) -> list[str]:
    if not text:
        return []
    text = text.replace("（）", " ")
    text = re.sub(r"[()（）]", " ", text)
    parts = re.split(r"[。；;]", text)
    result: list[str] = []
    for part in parts:
        value = clean(part)
        if value:
            result.append(value)
    return unique(result)


def normalize_entry(year: int, entry: dict[str, Any]) -> dict[str, Any]:
    raw = clean(entry.get("raw", ""))
    notes = (entry.get("notes", "") or "").strip()
    working = notes

    aliases, working = extract_aliases(working)
    language, working = extract_language(working)
    is_medley, working = extract_medley(working)
    subtitle, working = extract_subtitle(working)
    screen_info, working = extract_screen_info(entry, raw, working)
    original_singers, working = extract_original_singers(working)
    cosingers, working = extract_cosingers(working)
    lyricists, composers, working, credit_ambiguous = parse_credit_fields(working)

    other_info = extract_other_info(working)
    if credit_ambiguous:
        other_info = unique([clean(notes or raw)] + other_info)

    result = {
        "年份": year,
        "影视信息": screen_info,
        "歌曲标题": clean(entry.get("song_title", "")) or None,
        "歌曲副标题": subtitle,
        "歌曲又名": aliases,
        "词作者": lyricists,
        "曲作者": composers,
        "原唱": original_singers,
        "跟谁一起唱的": cosingers,
        "是否串烧版": is_medley,
        "演唱语言": language,
        "其它信息": other_info,
    }
    return result


def normalize_group_song(year: int, group_song: dict[str, Any]) -> list[dict[str, Any]]:
    notes = (group_song.get("notes", "") or "").strip()
    lyricists, composers, remaining, ambiguous = parse_credit_fields(notes)
    other_info = extract_other_info(remaining)
    if ambiguous:
        other_info = unique([notes] + other_info)

    subtitle = f"《{clean(group_song.get('work_title', ''))}》组歌"
    results = []
    for item in group_song.get("items", []):
        results.append(
            {
                "年份": year,
                "影视信息": None,
                "歌曲标题": clean(item.get("song_title", "")) or None,
                "歌曲副标题": subtitle,
                "歌曲又名": [],
                "词作者": lyricists,
                "曲作者": composers,
                "原唱": [],
                "跟谁一起唱的": [],
                "是否串烧版": False,
                "演唱语言": None,
                "其它信息": other_info,
            }
        )
    return results


def main() -> None:
    data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    years_output = []

    for year_block in data.get("years", []):
        year = year_block["year"]
        entries_output: list[dict[str, Any]] = []
        for entry in year_block.get("entries", []):
            entries_output.append(normalize_entry(year, entry))
        if year_block.get("group_song"):
            entries_output.extend(normalize_group_song(year, year_block["group_song"]))
        years_output.append({"年份": year, "条目": entries_output})

    result = {
        "标题": data.get("title"),
        "年份列表": years_output,
    }
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
