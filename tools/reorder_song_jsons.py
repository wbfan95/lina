import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SONGS_DIR = ROOT / 'src' / 'content' / 'songs'
DOC_PATH = ROOT / 'docs' / 'song-json-order.json'

SONG_ORDER = [
    'id',
    'title',
    'pinyin',
    'aliases',
    'year',
    'work',
    'credits',
    'lyrics',
    'scores',
    'videos',
    'notes',
]

WORK_ORDER = ['category', 'title', 'usage']
CREADITS_ORDER = ['lyricists', 'composers', 'arrangers', 'performers', 'original_singers']
LYRICS_ORDER = ['language', 'text']
INDEX_ORDER = ['id', 'title', 'aliases', 'year', 'work', 'has_scores', 'has_videos']


def sort_object(data: dict[str, Any], order: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in order:
        if key in data:
            result[key] = data[key]
    for key in data:
        if key not in result:
            result[key] = data[key]
    return result


def normalize_song(song: dict[str, Any]) -> dict[str, Any]:
    if 'work' in song and isinstance(song['work'], dict):
        song['work'] = sort_object(song['work'], WORK_ORDER)
    if 'credits' in song and isinstance(song['credits'], dict):
        song['credits'] = sort_object(song['credits'], CREADITS_ORDER)
    if 'lyrics' in song and isinstance(song['lyrics'], dict):
        song['lyrics'] = sort_object(song['lyrics'], LYRICS_ORDER)
    return sort_object(song, SONG_ORDER)


def normalize_index_item(item: dict[str, Any]) -> dict[str, Any]:
    if 'work' in item and isinstance(item['work'], dict):
        item['work'] = sort_object(item['work'], WORK_ORDER)
    return sort_object(item, INDEX_ORDER)


def main() -> None:
    for path in sorted(SONGS_DIR.glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        if path.name == 'index.json':
            if isinstance(data, list):
                data = [normalize_index_item(item) for item in data]
        else:
            data = normalize_song(data)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Reordered song JSON files.')


if __name__ == '__main__':
    main()
