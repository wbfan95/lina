import json
import sys
import time
from pathlib import Path
from typing import Any

from DrissionPage import ChromiumOptions, ChromiumPage


TIDS = [
    '586571552', '586590468', '586627553', '586645910', '586640749', '586645504',
    '586782339', '586900188', '586956184', '587020071', '587166647', '587193059',
    '587190955', '587276384', '587164663', '587237185', '587275601', '587255595',
    '587012297', '587275838', '587276019', '587276152', '587276279',
]

PAGE_PC_URL = 'https://tieba.baidu.com/c/f/pb/page_pc'
THREAD_URL = 'https://tieba.baidu.com/p/{tid}'
OUTPUT_ROOT = Path('output') / 'tieba_full'
END_TEXT = '—— 已加载全部评论 ——'
SECURITY_TEXT = '百度安全验证'


def reconfigure_stdio() -> None:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def to_plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(v) for v in value]
    if hasattr(value, 'items'):
        return {str(k): to_plain(v) for k, v in value.items()}
    return value


def build_page() -> ChromiumPage:
    opts = ChromiumOptions()
    opts.set_browser_path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    opts.set_user_data_path(str((Path.cwd() / '.chrome-data-tieba-full').resolve()))
    opts.auto_port()
    return ChromiumPage(opts)


def page_reached_end(page: ChromiumPage) -> bool:
    try:
        html = page.html or ''
    except Exception:
        return False
    return END_TEXT in html


def on_security_page(page: ChromiumPage) -> bool:
    try:
        title = page.title or ''
    except Exception:
        return False
    return SECURITY_TEXT in title


def wait_for_first_packet(page: ChromiumPage, timeout: int = 300):
    start = time.time()
    reminded = False
    while time.time() - start < timeout:
        if on_security_page(page) and not reminded:
            print('  detected Baidu security verification; complete it in Chrome and the script will continue.')
            reminded = True
        packet = page.listen.wait(timeout=1, fit_count=False, raise_err=False)
        if packet:
            return packet
        try:
            page.actions.move_to((700, 700), duration=0.05).scroll(delta_y=1200)
        except Exception:
            pass
        time.sleep(0.2)
    return False


def packet_to_dict(packet) -> dict[str, Any]:
    return {
        'captured_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'request_url': packet.url,
        'method': packet.method,
        'request_headers': to_plain(packet.request.headers),
        'request_post_data': to_plain(packet.request.postData),
        'response_headers': to_plain(packet.response.headers),
        'body': to_plain(packet.response.body),
    }


def merge_packets(tid: str, packets: list[dict[str, Any]]) -> dict[str, Any]:
    merged_posts: dict[str, dict[str, Any]] = {}
    latest_body: dict[str, Any] = {}
    for packet in packets:
        body = packet.get('body')
        if not isinstance(body, dict):
            continue
        thread = body.get('thread') if isinstance(body, dict) else None
        thread_id = str(thread.get('id')) if isinstance(thread, dict) and thread.get('id') else ''
        if thread_id and thread_id != tid:
            continue
        latest_body = body
        for post in body.get('post_list', []):
            post_id = str(post.get('id') or post.get('post_id') or '')
            if post_id:
                merged_posts[post_id] = post
    merged = dict(latest_body) if latest_body else {}
    merged['post_list'] = sorted(
        merged_posts.values(),
        key=lambda item: (int(item.get('floor') or 0), int(item.get('id') or item.get('post_id') or 0)),
    )
    merged['post_count_merged'] = len(merged['post_list'])
    merged['packet_count'] = len(packets)
    merged['thread_id_expected'] = tid
    return merged


def capture_thread(page: ChromiumPage, tid: str, idle_seconds: int = 5, hard_timeout: int = 240) -> dict[str, Any]:
    url = THREAD_URL.format(tid=tid)
    page.listen.clear()
    page.listen.start(PAGE_PC_URL)
    page.get(url)

    first_packet = wait_for_first_packet(page)
    if not first_packet:
        return {
            'tid': tid,
            'thread_url': url,
            'captured_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'packet_count': 0,
            'merged_post_count': 0,
            'end_marker_seen': False,
            'packets': [],
            'merged': {},
            'error': 'Timed out waiting for captcha clearance or first page_pc packet.',
        }

    packets = [packet_to_dict(first_packet)]
    started_at = time.time()
    last_packet_at = started_at
    last_scroll_at = 0.0
    end_seen_at = None

    while time.time() - started_at < hard_timeout:
        packet = page.listen.wait(timeout=1, fit_count=False, raise_err=False)
        if packet:
            packets.append(packet_to_dict(packet))
            last_packet_at = time.time()
            continue

        now = time.time()
        if now - last_scroll_at >= 0.8:
            try:
                page.actions.move_to((700, 700), duration=0.05).scroll(delta_y=1400)
                page.actions.move_to((700, 700), duration=0.05).scroll(delta_y=1400)
                page.run_js('window.scrollBy(0, 1200);')
            except Exception:
                pass
            last_scroll_at = now

        if page_reached_end(page):
            if end_seen_at is None:
                end_seen_at = now
            if now - last_packet_at >= idle_seconds and now - end_seen_at >= idle_seconds:
                break
        else:
            end_seen_at = None

        if packets and now - last_packet_at >= idle_seconds * 2:
            break

    merged = merge_packets(tid, packets)
    return {
        'tid': tid,
        'thread_url': url,
        'captured_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'packet_count': len(packets),
        'merged_post_count': len(merged.get('post_list', [])),
        'end_marker_seen': page_reached_end(page),
        'packets': packets,
        'merged': merged,
    }


def save_capture(result: dict[str, Any]) -> None:
    thread_dir = OUTPUT_ROOT / result['tid']
    thread_dir.mkdir(parents=True, exist_ok=True)
    (thread_dir / 'page_pc_packets.json').write_text(json.dumps(result.get('packets', []), ensure_ascii=False, indent=2), encoding='utf-8')
    (thread_dir / 'page_pc_merged.json').write_text(json.dumps(result.get('merged', {}), ensure_ascii=False, indent=2), encoding='utf-8')
    meta = {
        'tid': result['tid'],
        'thread_url': result['thread_url'],
        'captured_at': result['captured_at'],
        'packet_count': result['packet_count'],
        'merged_post_count': result['merged_post_count'],
        'end_marker_seen': result['end_marker_seen'],
    }
    if result.get('error'):
        meta['error'] = result['error']
    (thread_dir / 'capture_meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')


def main() -> int:
    reconfigure_stdio()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    page = build_page()
    summary = []
    try:
        print('Chrome will open with a dedicated profile for Tieba full capture.')
        print('If Baidu shows security verification, complete it once in the browser and leave the window open.')
        for index, tid in enumerate(TIDS, start=1):
            print(f'[{index}/{len(TIDS)}] Capturing thread {tid} ...')
            result = capture_thread(page, tid)
            save_capture(result)
            row = {
                'tid': tid,
                'captured_at': result['captured_at'],
                'packet_count': result['packet_count'],
                'merged_post_count': result['merged_post_count'],
                'end_marker_seen': result['end_marker_seen'],
            }
            if result.get('error'):
                row['error'] = result['error']
                print(f"  failed: {result['error']}")
            else:
                print(f"  packets={result['packet_count']} merged_posts={result['merged_post_count']} end={result['end_marker_seen']}")
            summary.append(row)
        (OUTPUT_ROOT / 'capture_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"Saved summary to {OUTPUT_ROOT / 'capture_summary.json'}")
        return 0
    finally:
        try:
            page.quit()
        except Exception:
            pass


if __name__ == '__main__':
    raise SystemExit(main())
