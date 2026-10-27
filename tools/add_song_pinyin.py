import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYDEPS = ROOT / '.pydeps'
if PYDEPS.exists():
    sys.path.insert(0, str(PYDEPS))

from pypinyin import Style, lazy_pinyin  # type: ignore

SONGS_DIR = ROOT / 'src' / 'content' / 'songs'


def is_cjk(char: str) -> bool:
    return '\u4e00' <= char <= '\u9fff'


def title_to_pinyin(title: str) -> str:
    tokens: list[str] = []
    buffer = ''

    def flush_buffer() -> None:
        nonlocal buffer
        cleaned = buffer.strip()
        if cleaned:
            tokens.append(cleaned)
        buffer = ''

    for char in title:
        if is_cjk(char):
            flush_buffer()
            pinyin = lazy_pinyin(char, style=Style.NORMAL, strict=False)
            tokens.append(pinyin[0] if pinyin else char)
            continue

        if char.isspace():
            flush_buffer()
            continue

        buffer += char

    flush_buffer()
    return ' '.join(tokens)


def main() -> None:
    updated = 0
    for path in sorted(SONGS_DIR.glob('*.json')):
        if path.name == 'index.json':
            continue
        song = json.loads(path.read_text(encoding='utf-8'))
        title = song.get('title', '')
        if not title:
            continue
        song['pinyin'] = title_to_pinyin(title)
        path.write_text(json.dumps(song, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        updated += 1
    print(f'Updated pinyin for {updated} songs.')


if __name__ == '__main__':
    main()
