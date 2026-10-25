import re
import shutil
import subprocess
from typing import List, Dict

# Regex for YouTube single videos, shorts, live streams, and embed links
# Captures the 11-character video ID
YT_VIDEO_REGEX = re.compile(
    r'(?:https?:\/\/)?'
    r'(?:[a-zA-Z0-9-]+\.)?'
    r'(?:youtube\.com\/(?:watch\?(?:[^&\s]*&)*v=|shorts\/|live\/|embed\/)|youtu\.be\/)'
    r'([a-zA-Z0-9_-]{11})',
    re.IGNORECASE
)

# Regex for YouTube playlist URLs
YT_PLAYLIST_REGEX = re.compile(
    r'(?:https?:\/\/)?'
    r'(?:[a-zA-Z0-9-]+\.)?'
    r'youtube\.com\/playlist\?(?:[^&\s]*&)*list=([a-zA-Z0-9_-]+)',
    re.IGNORECASE
)

from system_compat import get_clipboard_text


def extract_youtube_items(text: str) -> List[Dict[str, str]]:
    """
    Extracts all unique YouTube video and playlist items found within the provided text.
    Returns a list of dicts:
      [
        {"type": "video", "id": "...", "url": "..."},
        {"type": "playlist", "id": "...", "url": "..."}
      ]
    """
    if not text:
        return []

    items = []
    seen_ids = set()

    # 1. Check for pure playlist URLs first
    playlist_matches = YT_PLAYLIST_REGEX.findall(text)
    for p_id in playlist_matches:
        if p_id not in seen_ids:
            seen_ids.add(p_id)
            items.append({
                "type": "playlist",
                "id": p_id,
                "url": f"https://www.youtube.com/playlist?list={p_id}"
            })

    # 2. Check for video URLs (watch, shorts, live, youtu.be)
    video_matches = YT_VIDEO_REGEX.findall(text)
    for v_id in video_matches:
        if v_id not in seen_ids:
            seen_ids.add(v_id)
            items.append({
                "type": "video",
                "id": v_id,
                "url": f"https://www.youtube.com/watch?v={v_id}"
            })

    return items
