import json
import re
import sys
from pathlib import Path

INPUT_PATHS = [Path('年表.json'), Path('年表2.json')]
OUTPUT_DIR = Path('output') / 'timeline'


def reconfigure_stdio() -> None:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def clean_text(value: str) -> str:
    value = value.replace('\xa0', ' ')
    value = value.replace('\u3000', ' ')
    value = value.replace('\r\n', '\n').replace('\r', '\n')
    value = value.replace('\x18', '')
    value = re.sub(r'[ \t]+', ' ', value)
    value = re.sub(r'\n{3,}', '\n\n', value)
    return value.strip()


def parse_entry_line(line: str) -> dict:
    raw = clean_text(line)
    result = {
        'raw': raw,
        'type': '',
        'work_title': '',
        'usage': '',
        'song_title': '',
        'notes': '',
    }

    patterns = [
        r'^(?P<type>电视剧|电视片|电视连续剧|电影|广播剧|纪录片|舞蹈|古典舞蹈)《(?P<work>[^》]*)》(?P<usage>[^：]*)：《(?P<song>[^》]*)》(?P<notes>.*)$',
        r'^(?P<type>电视剧|电视片|电视连续剧|电影|广播剧|纪录片|舞蹈|古典舞蹈)：《(?P<work>[^》]*)》(?P<usage>[^：]*)：《(?P<song>[^》]*)》(?P<notes>.*)$',
        r'^(?P<type>歌曲)：《(?P<work>[^》]*)》(?P<usage>[^：]*)：《(?P<song>[^》]*)》(?P<notes>.*)$',
        r'^(?P<type>歌曲)：《(?P<song>[^》]*)》(?P<notes>.*)$',
        r'^(?P<type>电视剧|电视片|电视连续剧|电影|广播剧|纪录片|舞蹈|古典舞蹈)《(?P<work>[^》]*)》(?P<usage>[^：]*)：(?P<notes>.*)$',
    ]

    for pattern in patterns:
        match = re.match(pattern, raw)
        if not match:
            continue
        result['type'] = (match.groupdict().get('type') or '').strip()
        result['work_title'] = (match.groupdict().get('work') or '').strip()
        result['usage'] = (match.groupdict().get('usage') or '').strip(' ：')
        result['song_title'] = (match.groupdict().get('song') or '').strip()
        result['notes'] = clean_text(match.groupdict().get('notes') or '')
        return result

    match = re.match(r'^《(?P<song>[^》]*)》(?P<notes>.*)$', raw)
    if match:
        result['song_title'] = match.group('song').strip()
        result['notes'] = clean_text(match.group('notes') or '')
        return result

    result['notes'] = raw
    return result


def parse_year_block(text: str, floor: int, source_file: str) -> dict | None:
    text = clean_text(text)
    lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
    if not lines:
        return None

    year_match = re.match(r'^(?P<year>\d{4})年$', lines[0])
    if not year_match:
        return None

    year = int(year_match.group('year'))
    entries = []
    current = None
    special_notes = []

    for line in lines[1:]:
        num_match = re.match(r'^(?P<index>\d{1,3})、(?P<body>.*)$', line)
        if num_match:
            if current:
                entries.append(current)
            current = {
                'index': int(num_match.group('index')),
                'raw': clean_text(num_match.group('body')),
            }
        else:
            if current:
                current['raw'] = clean_text(current['raw'] + '\n' + line)
            else:
                special_notes.append(line)

    if current:
        entries.append(current)

    parsed_entries = []
    for entry in entries:
        parsed = parse_entry_line(entry['raw'])
        parsed['index'] = entry['index']
        parsed_entries.append(parsed)

    return {
        'year': year,
        'floor': floor,
        'source_file': source_file,
        'entries': parsed_entries,
        'notes': special_notes,
    }


def parse_group_song_block(text: str, floor: int, source_file: str) -> dict | None:
    text = clean_text(text)
    lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
    if not lines:
        return None

    year_match = re.match(r'^(?P<year>\d{4})年$', lines[0])
    if not year_match or len(lines) < 2:
        return None

    head = lines[1]
    if '组歌' not in head:
        return None

    work_title = ''
    notes = ''
    m = re.match(r'^《(?P<title>[^》]+)》组歌(?P<notes>.*)$', head)
    if m:
        work_title = clean_text(m.group('title'))
        notes = clean_text(m.group('notes'))
    else:
        parsed = parse_entry_line(head)
        work_title = parsed.get('work_title', '')
        notes = parsed.get('notes', '')

    year = int(year_match.group('year'))
    items = []
    for line in lines[2:]:
        m = re.match(r'^(?P<index>\d+)、(?P<title>.*)$', line)
        if m:
            title = clean_text(m.group('title'))
            if title.startswith('《') and title.endswith('》'):
                title = title[1:-1]
            items.append({'index': int(m.group('index')), 'song_title': title})

    return {
        'year': year,
        'floor': floor,
        'source_file': source_file,
        'group_song': {
            'raw': head,
            'type': '组歌',
            'work_title': work_title,
            'usage': '组歌',
            'notes': notes,
            'items': items,
        },
    }


def main() -> int:
    reconfigure_stdio()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    extracted = {
        'title': '',
        'years': [],
        'non_year_posts': [],
        'source_files': [p.name for p in INPUT_PATHS if p.exists()],
    }

    for input_path in INPUT_PATHS:
        if not input_path.exists():
            continue
        payload = json.loads(input_path.read_text(encoding='utf-8'))
        if not extracted['title']:
            extracted['title'] = payload.get('thread', {}).get('title', '')

        for post in payload.get('post_list', []):
            floor = post.get('floor')
            text_blocks = []
            for block in post.get('content', []):
                if isinstance(block, dict) and block.get('type') == 0 and clean_text(block.get('text', '')):
                    text_blocks.append(clean_text(block.get('text', '')))
            if not text_blocks:
                continue
            text = '\n'.join(text_blocks)

            year_block = parse_year_block(text, floor, input_path.name)
            if year_block:
                group_song = parse_group_song_block(text, floor, input_path.name)
                extracted['years'].append(group_song or year_block)
            else:
                extracted['non_year_posts'].append({'floor': floor, 'source_file': input_path.name, 'raw_text': text})

    extracted['years'].sort(key=lambda item: (item['year'], item['floor']))

    out_json = OUTPUT_DIR / 'timeline_extracted.json'
    out_json.write_text(json.dumps(extracted, ensure_ascii=False, indent=2), encoding='utf-8')

    md_lines = [f"# {extracted['title']}", '']
    md_lines.append(f"有效年份块：{len(extracted['years'])}")
    md_lines.append(f"非年份楼层：{len(extracted['non_year_posts'])}")
    md_lines.append('')

    for block in extracted['years']:
        md_lines.append(f"## {block['year']}年")
        md_lines.append(f"来源：{block['source_file']} / 楼层 {block['floor']}")
        md_lines.append('')
        if 'entries' in block:
            for entry in block['entries'][:12]:
                parts = []
                if entry['type']:
                    parts.append(entry['type'])
                if entry['work_title']:
                    parts.append(f"《{entry['work_title']}》")
                if entry['usage']:
                    parts.append(entry['usage'])
                if entry['song_title']:
                    parts.append(f"《{entry['song_title']}》")
                line = f"{entry['index']:02d}. " + ' '.join(parts or [entry['raw']])
                if entry['notes']:
                    line += f" {entry['notes']}"
                md_lines.append(line)
            if len(block['entries']) > 12:
                md_lines.append(f"... 共 {len(block['entries'])} 条")
        else:
            group = block['group_song']
            md_lines.append(f"组歌：《{group['work_title']}》")
            if group['notes']:
                md_lines.append(group['notes'])
            for item in group['items']:
                md_lines.append(f"{item['index']:02d}. 《{item['song_title']}》")
        md_lines.append('')

    if extracted['non_year_posts']:
        md_lines.append('## 未归入年份的楼层')
        md_lines.append('')
        for post in extracted['non_year_posts']:
            md_lines.append(f"- {post['source_file']} / 楼层 {post['floor']}：{post['raw_text'][:160]}")

    out_md = OUTPUT_DIR / 'timeline_extracted.md'
    out_md.write_text('\n'.join(md_lines), encoding='utf-8')

    print(f'Saved {out_json}')
    print(f'Saved {out_md}')
    print(f"Years extracted: {len(extracted['years'])}")
    print(f"Non-year posts: {len(extracted['non_year_posts'])}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
