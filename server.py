#!/usr/bin/env python3
"""
Local YouTube-like Video Player Server
Serves videos from ./downloads/ and provides a web-based player at http://localhost:8888
"""

import os
import sys
import json
import signal
import subprocess
import glob
import urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
import system_compat

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(SCRIPT_DIR, "downloads")
THUMBS_DIR = os.path.join(DOWNLOADS_DIR, "thumbs")
AUDIOS_DIR = os.path.join(DOWNLOADS_DIR, "audio")
PLAYER_HTML = os.path.join(SCRIPT_DIR, "player.html")
DEFAULT_PORT = 8888


def get_video_metadata(filepath: str) -> dict:
    """Extract video and audio metadata using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                filepath
            ],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(result.stdout)
        duration = float(data.get("format", {}).get("duration", 0))
        file_size = int(data.get("format", {}).get("size", 0))

        width, height, codec = 0, 0, "unknown"
        audio_tracks = []
        audio_stream_idx = 0

        for stream in data.get("streams", []):
            stype = stream.get("codec_type")
            if stype == "video":
                # Skip attached pictures (thumbnails)
                disp = stream.get("disposition", {})
                if disp.get("attached_pic", 0) == 1:
                    continue
                if width == 0:
                    width = int(stream.get("width", 0))
                    height = int(stream.get("height", 0))
                    codec = stream.get("codec_name", "unknown")
            elif stype == "audio":
                tags = stream.get("tags", {})
                lang = tags.get("language", "").lower()
                title = tags.get("title", "")

                if lang in ("id", "ind") or "indonesia" in title.lower() or "sulih" in title.lower():
                    label = "Indonesia [Sulih Suara]"
                    code = "id"
                elif lang in ("en", "eng") or "english" in title.lower():
                    label = "Inggris [Asli]"
                    code = "en"
                elif audio_stream_idx == 0:
                    label = "Asli (Original)"
                    code = lang or "orig"
                elif audio_stream_idx == 1:
                    label = "Indonesia [Sulih Suara]"
                    code = "id"
                else:
                    label = f"Audio {audio_stream_idx + 1}"
                    code = lang or f"track{audio_stream_idx}"

                audio_tracks.append({
                    "index": audio_stream_idx,
                    "language": code,
                    "label": label,
                    "is_default": (audio_stream_idx == 0)
                })
                audio_stream_idx += 1

        # Check if an alternate audio track was pre-extracted or saved separately
        name_no_ext = os.path.splitext(os.path.basename(filepath))[0]
        for ext in (".webm", ".m4a", ".opus", ".ogg", ".mp3"):
            alt_audio = os.path.join(AUDIOS_DIR, f"{name_no_ext}_track1{ext}")
            if os.path.exists(alt_audio) and len(audio_tracks) <= 1:
                audio_tracks.append({
                    "index": 1,
                    "language": "id",
                    "label": "Indonesia [Sulih Suara]",
                    "is_default": False
                })
                break

        return {
            "duration": duration,
            "width": width,
            "height": height,
            "codec": codec,
            "file_size": file_size,
            "audio_tracks": audio_tracks,
        }
    except Exception:
        return {
            "duration": 0,
            "width": 0,
            "height": 0,
            "codec": "unknown",
            "file_size": 0,
            "audio_tracks": [],
        }


def scan_videos() -> list:
    """Scan downloads directory for video files and build metadata list."""
    videos = []
    extensions = ("*.mp4", "*.mkv", "*.webm", "*.avi", "*.mov")
    video_files = []
    for ext in extensions:
        video_files.extend(glob.glob(os.path.join(DOWNLOADS_DIR, ext)))

    video_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)

    for filepath in video_files:
        filename = os.path.basename(filepath)
        name_no_ext = os.path.splitext(filename)[0]

        # Extract title: remove [videoId] suffix if present
        title = name_no_ext
        if "[" in title and title.endswith("]"):
            title = title[:title.rfind("[")].strip()

        # Check for thumbnail
        thumb_path = os.path.join(THUMBS_DIR, name_no_ext + ".jpg")
        has_thumb = os.path.exists(thumb_path)

        # Get metadata
        meta = get_video_metadata(filepath)

        encoded_filename = urllib.parse.quote(filename)
        encoded_thumb = urllib.parse.quote(name_no_ext + ".jpg") if has_thumb else ""

        videos.append({
            "filename": filename,
            "title": title,
            "duration": meta["duration"],
            "width": meta["width"],
            "height": meta["height"],
            "codec": meta["codec"],
            "file_size": meta["file_size"],
            "audio_tracks": meta.get("audio_tracks", []),
            "thumbnail": f"/thumbs/{encoded_thumb}" if has_thumb else "",
            "video_url": f"/videos/{encoded_filename}",
            "date_modified": os.path.getmtime(filepath),
        })

    return videos


def generate_thumbnails():
    """Generate thumbnails for any videos that don't have one yet."""
    os.makedirs(THUMBS_DIR, exist_ok=True)
    extensions = ("*.mp4", "*.mkv", "*.webm", "*.avi", "*.mov")
    video_files = []
    for ext in extensions:
        video_files.extend(glob.glob(os.path.join(DOWNLOADS_DIR, ext)))

    for filepath in video_files:
        filename = os.path.basename(filepath)
        name_no_ext = os.path.splitext(filename)[0]
        thumb_path = os.path.join(THUMBS_DIR, name_no_ext + ".jpg")

        # Extract real YouTube cover art if not present
        if not os.path.exists(thumb_path) or os.path.getsize(thumb_path) < 15000:
            print(f"  Extracting real YouTube thumbnail: {name_no_ext}.jpg")
            try:
                # 1. Use ffmpegthumbnailer if installed
                if shutil.which("ffmpegthumbnailer"):
                    try:
                        subprocess.run(
                            ["ffmpegthumbnailer", "-i", filepath, "-o", thumb_path, "-m", "-s", "480"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20
                        )
                    except Exception:
                        pass

                # 2. If needed, try mutagen
                if not os.path.exists(thumb_path) or os.path.getsize(thumb_path) < 1000:
                    try:
                        from mutagen.mp4 import MP4
                        mp4 = MP4(filepath)
                        if mp4.tags and "covr" in mp4.tags and len(mp4.tags["covr"]) > 0:
                            with open(thumb_path, "wb") as f:
                                f.write(bytes(mp4.tags["covr"][0]))
                    except Exception:
                        pass

                # 3. Fallback only if no cover art exists
                if not os.path.exists(thumb_path) or os.path.getsize(thumb_path) < 1000:
                    subprocess.run(
                        [
                            "ffmpeg", "-y", "-i", filepath,
                            "-ss", "00:00:05",
                            "-vframes", "1",
                            "-vf", "scale=480:-1",
                            thumb_path
                        ],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20
                    )
            except Exception as e:
                print(f"  Warning: Failed to generate thumbnail for {filename}: {e}")


class PlayerRequestHandler(SimpleHTTPRequestHandler):
    """Custom HTTP request handler for the video player."""

    def __init__(self, *args, video_cache=None, **kwargs):
        self.video_cache = video_cache
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        """Suppress default logging for cleaner output."""
        pass

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        try:
            self._do_GET_impl()
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception:
            try:
                self.send_error(500)
            except Exception:
                pass

    def _do_GET_impl(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)

        # Root: serve the player HTML
        if path == "/" or path == "/index.html":
            self.serve_file(PLAYER_HTML, "text/html; charset=utf-8")
            return

        # API: return video metadata
        if path == "/api/videos":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps(self.video_cache, ensure_ascii=False).encode("utf-8"))
            return

        # API: rescan videos
        if path == "/api/rescan":
            generate_thumbnails()
            self.video_cache.clear()
            self.video_cache.extend(scan_videos())
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "count": len(self.video_cache)}).encode("utf-8"))
            return

        # Serve video files
        if path.startswith("/videos/"):
            video_filename = path[len("/videos/"):]
            video_path = os.path.join(DOWNLOADS_DIR, video_filename)
            if os.path.isfile(video_path):
                self.serve_video(video_path)
                return

        # Serve audio tracks (supports on-demand extraction from video)
        if path.startswith("/audio/"):
            audio_subpath = path[len("/audio/"):]
            query = urllib.parse.parse_qs(parsed.query)
            try:
                track_idx = int(query.get("track", [1])[0])
            except ValueError:
                track_idx = 1

            name_no_ext = os.path.splitext(audio_subpath)[0]
            os.makedirs(AUDIOS_DIR, exist_ok=True)

            # 1. Check if a valid extracted audio file already exists
            existing_audio = None
            for ext in (".webm", ".m4a", ".opus", ".ogg", ".mp3"):
                candidate = os.path.join(AUDIOS_DIR, f"{name_no_ext}_track{track_idx}{ext}")
                if os.path.isfile(candidate) and os.path.getsize(candidate) > 10000:
                    existing_audio = candidate
                    break

            if existing_audio:
                self.serve_video(existing_audio)
                return

            # 2. If not yet extracted, find the video file and extract
            video_matches = glob.glob(os.path.join(DOWNLOADS_DIR, f"{name_no_ext}.*"))
            video_file = None
            for vm in video_matches:
                if vm.endswith((".mp4", ".mkv", ".webm")):
                    video_file = vm
                    break

            if video_file and os.path.isfile(video_file):
                codec = "opus"
                try:
                    probe_res = subprocess.run(
                        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", video_file],
                        capture_output=True, text=True, timeout=10
                    )
                    probe_data = json.loads(probe_res.stdout)
                    a_streams = [s for s in probe_data.get("streams", []) if s.get("codec_type") == "audio"]
                    if track_idx < len(a_streams):
                        codec = a_streams[track_idx].get("codec_name", "opus").lower()
                except Exception:
                    pass

                out_ext = ".webm" if codec in ("opus", "vorbis") else (".m4a" if codec == "aac" else ".webm")
                out_audio = os.path.join(AUDIOS_DIR, f"{name_no_ext}_track{track_idx}{out_ext}")
                tmp_audio = os.path.join(AUDIOS_DIR, f"_tmp_{track_idx}_{name_no_ext}{out_ext}")

                success = False
                try:
                    ret = subprocess.run(
                        ["ffmpeg", "-y", "-i", video_file, "-map", f"0:a:{track_idx}", "-c", "copy", tmp_audio],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120
                    )
                    if ret.returncode == 0 and os.path.isfile(tmp_audio) and os.path.getsize(tmp_audio) > 10000:
                        os.replace(tmp_audio, out_audio)
                        success = True
                except Exception:
                    pass

                if not success:
                    try:
                        fallback_audio = os.path.join(AUDIOS_DIR, f"{name_no_ext}_track{track_idx}.m4a")
                        tmp_fallback = os.path.join(AUDIOS_DIR, f"_tmp_transcode_{track_idx}_{name_no_ext}.m4a")
                        ret = subprocess.run(
                            ["ffmpeg", "-y", "-i", video_file, "-map", f"0:a:{track_idx}", "-c:a", "aac", "-b:a", "192k", tmp_fallback],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300
                        )
                        if ret.returncode == 0 and os.path.isfile(tmp_fallback) and os.path.getsize(tmp_fallback) > 10000:
                            os.replace(tmp_fallback, fallback_audio)
                            out_audio = fallback_audio
                            success = True
                    except Exception:
                        pass

                if success and os.path.isfile(out_audio):
                    self.serve_video(out_audio)
                    return

            self.send_error(404)
            return

        # Serve thumbnail files
        if path.startswith("/thumbs/"):
            thumb_filename = path[len("/thumbs/"):]
            thumb_path = os.path.join(THUMBS_DIR, thumb_filename)
            if os.path.isfile(thumb_path):
                self.serve_file(thumb_path, "image/jpeg")
                return

        # 404
        self.send_error(404)

    def serve_file(self, filepath, content_type):
        """Serve a complete file."""
        try:
            with open(filepath, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception:
            try:
                self.send_error(500)
            except Exception:
                pass

    def serve_video(self, filepath):
        """Serve video or audio with Range request support (essential for seeking)."""
        try:
            file_size = os.path.getsize(filepath)

            # Determine content type
            ext = os.path.splitext(filepath)[1].lower()
            content_types = {
                ".mp4": "video/mp4",
                ".webm": "video/webm",
                ".mkv": "video/x-matroska",
                ".avi": "video/x-msvideo",
                ".mov": "video/quicktime",
                ".m4a": "audio/mp4",
                ".aac": "audio/aac",
                ".opus": "audio/opus",
                ".mp3": "audio/mpeg",
                ".ogg": "audio/ogg",
            }
            content_type = content_types.get(ext, "application/octet-stream")
            if ext == ".webm" and (filepath.startswith(AUDIOS_DIR) or "_track" in filepath):
                content_type = "audio/webm"

            range_header = self.headers.get("Range")
            if range_header:
                # Parse Range header
                range_str = range_header.replace("bytes=", "")
                parts = range_str.split("-")
                start = int(parts[0]) if parts[0] else 0
                end = int(parts[1]) if parts[1] else file_size - 1
                end = min(end, file_size - 1)
                length = end - start + 1

                self.send_response(206)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Content-Length", str(length))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()

                with open(filepath, "rb") as f:
                    f.seek(start)
                    remaining = length
                    chunk_size = 1024 * 1024  # 1MB chunks
                    while remaining > 0:
                        chunk = f.read(min(chunk_size, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            else:
                # Full file response
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(file_size))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()

                with open(filepath, "rb") as f:
                    chunk_size = 1024 * 1024
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception:
            try:
                self.send_error(500)
            except Exception:
                pass


class QuietThreadingHTTPServer(ThreadingHTTPServer):
    """Threading HTTPServer that suppresses BrokenPipeError / ConnectionResetError on client disconnect."""
    daemon_threads = True

    def handle_error(self, request, client_address):
        exc_type, _, _ = sys.exc_info()
        if exc_type in (BrokenPipeError, ConnectionResetError):
            return
        super().handle_error(request, client_address)


def main():
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    system_compat.init_system()
    os_info = system_compat.get_os_info()

    # Check player.html exists
    if not os.path.exists(PLAYER_HTML):
        print(f"❌ player.html tidak ditemukan di: {PLAYER_HTML}")
        sys.exit(1)

    print(f"\033[96m\033[1m{'=' * 60}\033[0m")
    print(f"\033[1m\033[92m  🎬 Local YouTube Player Server\033[0m")
    print(f"\033[2m  Sistem: {os_info['os_name']} | Desktop: {os_info['desktop_env']}\033[0m")
    print(f"\033[96m\033[1m{'=' * 60}\033[0m")

    # Generate thumbnails
    print(f"\n\033[93m📸 Memeriksa thumbnail...\033[0m")
    generate_thumbnails()

    # Scan videos
    print(f"\033[93m🔍 Memindai video...\033[0m")
    video_cache = scan_videos()
    print(f"\033[92m✔ Ditemukan {len(video_cache)} video\033[0m\n")

    # Create handler with shared video cache
    handler = partial(PlayerRequestHandler, video_cache=video_cache)

    server = QuietThreadingHTTPServer(("0.0.0.0", port), handler)
    server.daemon_threads = True

    def shutdown(signum, frame):
        print(f"\n\033[93m🛑 Server dihentikan.\033[0m")
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)

    url = f"http://localhost:{port}"
    print(f"\033[1m  🌐 Buka di browser: \033[4m\033[96m{url}\033[0m")
    print(f"\033[2m  Tekan Ctrl+C untuk menghentikan server.\033[0m\n")

    # Try to open browser automatically
    try:
        system_compat.open_in_browser(url)
    except Exception:
        pass

    server.serve_forever()


if __name__ == "__main__":
    main()
