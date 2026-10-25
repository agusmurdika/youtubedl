import os
import sys
import glob
import hashlib
import json
import subprocess
import urllib.parse
from typing import Optional, Callable, Dict, Any

# Ensure local packages (e.g. mutagen) are found in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import yt_dlp

try:
    from mutagen.mp4 import MP4, MP4Cover
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


class YouTubeDownloader:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.download_dir = os.path.abspath(config.get("download_dir", "downloads"))
        os.makedirs(self.download_dir, exist_ok=True)

    def _build_ydl_opts(
        self,
        is_playlist: bool = False,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        postprocessor_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        container = self.config.get("format_container", "mp4").lower()
        max_res = self.config.get("max_resolution")
        multi_audio = self.config.get("multi_audio", True)
        dl_indonesian = self.config.get("download_indonesian_dub", True)

        # Format string for highest visual & audio quality + Indonesian dub if available
        if multi_audio and dl_indonesian:
            if max_res:
                format_str = (
                    f"bestvideo*[height<={max_res}]+bestaudio[ext=m4a][language=original]+bestaudio[ext=m4a][language=id]/"
                    f"bestvideo*[height<={max_res}]+bestaudio[ext=m4a][language^=en]+bestaudio[ext=m4a][language=id]/"
                    f"bestvideo*[height<={max_res}]+bestaudio[language=original]+bestaudio[language=id]/"
                    f"bestvideo*[height<={max_res}]+bestaudio[language^=en]+bestaudio[language=id]/"
                    f"bestvideo*[height<={max_res}]+bestaudio+bestaudio[language=id]/"
                    f"bestvideo*[height<={max_res}]+bestaudio/"
                    f"best[height<={max_res}]"
                )
            else:
                format_str = (
                    "bestvideo*+bestaudio[ext=m4a][language=original]+bestaudio[ext=m4a][language=id]/"
                    "bestvideo*+bestaudio[ext=m4a][language^=en]+bestaudio[ext=m4a][language=id]/"
                    "bestvideo*+bestaudio[language=original]+bestaudio[language=id]/"
                    "bestvideo*+bestaudio[language^=en]+bestaudio[language=id]/"
                    "bestvideo*+bestaudio+bestaudio[language=id]/"
                    "bestvideo*+bestaudio/"
                    "best"
                )
        elif max_res:
            format_str = f"bestvideo*[height<={max_res}]+bestaudio/best[height<={max_res}]"
        else:
            format_str = "bestvideo*+bestaudio/best"

        # Output template: Title [ID].ext
        outtmpl = os.path.join(self.download_dir, "%(title)s [%(id)s].%(ext)s")

        postprocessors = []

        # Convert thumbnail to JPG
        postprocessors.append({
            "key": "FFmpegThumbnailsConvertor",
            "format": "jpg",
            "when": "before_dl"
        })

        # Embed metadata (Title, Artist, Date, etc.)
        if self.config.get("embed_metadata", True):
            postprocessors.append({
                "key": "FFmpegMetadata",
                "add_metadata": True,
            })

        # Embed thumbnail directly into the video container
        keep_thumb_file = self.config.get("save_thumbnail_file", False)
        if self.config.get("embed_thumbnail", True):
            postprocessors.append({
                "key": "EmbedThumbnail",
                "already_have_thumbnail": keep_thumb_file,
            })

        ydl_opts: Dict[str, Any] = {
            "format": format_str,
            "format_sort": ["res", "fps", "size", "br"],  # Guarantees maximum resolution, fps and bitrate
            "allow_multiple_audio_streams": multi_audio,
            "outtmpl": outtmpl,
            "merge_output_format": container,
            "writethumbnail": True,
            "postprocessors": postprocessors,
            "noplaylist": not is_playlist,
            "windowsfilenames": True,  # Ensures filenames are compatible with exFAT/FAT32/NTFS
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "ignoreerrors": False,
            "retries": 50,
            "fragment_retries": 50,
            "skip_unavailable_fragments": False,
            "continuedl": True,
            "socket_timeout": 20,
        }

        progress_hooks = []
        if progress_callback:
            progress_hooks.append(progress_callback)
        if progress_hooks:
            ydl_opts["progress_hooks"] = progress_hooks

        postprocessor_hooks = []
        if postprocessor_callback:
            postprocessor_hooks.append(postprocessor_callback)
        if postprocessor_hooks:
            ydl_opts["postprocessor_hooks"] = postprocessor_hooks

        return ydl_opts

    def extract_info(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Fast metadata extraction without downloading media.
        """
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "extract_flat": False,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception:
            return None

    def _ensure_mp4_cover(self, video_id: str):
        """
        Ensures the MP4 file has the 'covr' metadata tag using mutagen,
        and cleans up any separate image files if save_thumbnail_file is False.
        """
        keep_thumb_file = self.config.get("save_thumbnail_file", False)

        # Locate the downloaded video and any thumbnail image
        video_matches = glob.glob(os.path.join(self.download_dir, f"*{video_id}*.mp4"))
        image_matches = (
            glob.glob(os.path.join(self.download_dir, f"*{video_id}*.jpg")) +
            glob.glob(os.path.join(self.download_dir, f"*{video_id}*.jpeg")) +
            glob.glob(os.path.join(self.download_dir, f"*{video_id}*.webp")) +
            glob.glob(os.path.join(self.download_dir, f"*{video_id}*.png"))
        )

        if MUTAGEN_AVAILABLE and video_matches and image_matches:
            target_mp4 = video_matches[0]
            thumb_file = image_matches[0]
            try:
                mp4 = MP4(target_mp4)
                if mp4.tags is not None and "covr" not in mp4.tags:
                    with open(thumb_file, "rb") as f:
                        img_bytes = f.read()
                    img_fmt = MP4Cover.FORMAT_PNG if thumb_file.endswith(".png") else MP4Cover.FORMAT_JPEG
                    mp4.tags["covr"] = [MP4Cover(img_bytes, imageformat=img_fmt)]
                    mp4.save()
            except Exception:
                pass

        # If user does NOT want a separate thumbnail file, remove all image matches
        if not keep_thumb_file:
            for img in image_matches:
                try:
                    os.remove(img)
                except OSError:
                    pass

        # Pre-generate Linux freedesktop thumbnail cache so file managers (Thunar/Nautilus/Dolphin)
        # immediately display the YouTube cover art as the file icon
        if video_matches:
            self._register_system_thumbnail(video_matches[0])
            self._pre_extract_alternate_audio(video_matches[0])

    def _pre_extract_alternate_audio(self, video_path: str):
        """
        If video contains more than 1 audio stream (e.g. English + Indonesian dub),
        extracts the alternate stream(s) to downloads/audio/ for instant playback in the web player.
        """
        try:
            cmd = [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", video_path
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            data = json.loads(res.stdout)
            audio_count = sum(1 for s in data.get("streams", []) if s.get("codec_type") == "audio")

            if audio_count > 1:
                audios_dir = os.path.join(self.download_dir, "audio")
                os.makedirs(audios_dir, exist_ok=True)
                name_no_ext = os.path.splitext(os.path.basename(video_path))[0]
                a_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]

                for trk in range(1, audio_count):
                    # Check if already extracted
                    already_extracted = False
                    for ext in (".webm", ".m4a", ".opus", ".ogg", ".mp3"):
                        candidate = os.path.join(audios_dir, f"{name_no_ext}_track{trk}{ext}")
                        if os.path.isfile(candidate) and os.path.getsize(candidate) > 10000:
                            already_extracted = True
                            break

                    if already_extracted:
                        continue

                    # Determine codec for lossless copy
                    codec = "opus"
                    if trk < len(a_streams):
                        codec = a_streams[trk].get("codec_name", "opus").lower()

                    out_ext = ".webm" if codec in ("opus", "vorbis") else (".m4a" if codec == "aac" else ".webm")
                    out_audio = os.path.join(audios_dir, f"{name_no_ext}_track{trk}{out_ext}")
                    tmp_audio = os.path.join(audios_dir, f"_tmp_{trk}_{name_no_ext}{out_ext}")

                    # 1. Try lossless stream copy (takes 2-4s for full video)
                    success = False
                    try:
                        ret = subprocess.run(
                            [
                                "ffmpeg", "-y", "-i", video_path,
                                "-map", f"0:a:{trk}",
                                "-c", "copy",
                                tmp_audio
                            ],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=120,
                            check=False
                        )
                        if ret.returncode == 0 and os.path.isfile(tmp_audio) and os.path.getsize(tmp_audio) > 10000:
                            os.replace(tmp_audio, out_audio)
                            success = True
                    except Exception:
                        pass

                    # 2. Fallback to AAC transcode only if copy failed
                    if not success:
                        try:
                            fallback_audio = os.path.join(audios_dir, f"{name_no_ext}_track{trk}.m4a")
                            tmp_fallback = os.path.join(audios_dir, f"_tmp_transcode_{trk}_{name_no_ext}.m4a")
                            ret = subprocess.run(
                                [
                                    "ffmpeg", "-y", "-i", video_path,
                                    "-map", f"0:a:{trk}",
                                    "-c:a", "aac",
                                    "-b:a", "192k",
                                    tmp_fallback
                                ],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                timeout=300,
                                check=False
                            )
                            if ret.returncode == 0 and os.path.isfile(tmp_fallback) and os.path.getsize(tmp_fallback) > 10000:
                                os.replace(tmp_fallback, fallback_audio)
                        except Exception:
                            pass
        except Exception:
            pass

    def _register_system_thumbnail(self, video_path: str):
        """
        Pre-generates freedesktop.org thumbnails in ~/.cache/thumbnails/
        so that Linux file managers (Thunar, Nautilus, Dolphin) immediately display
        the embedded YouTube cover as the video's icon.
        """
        try:
            abs_path = os.path.abspath(video_path)
            uri = "file://" + urllib.parse.quote(abs_path)
            uri_hash = hashlib.md5(uri.encode("utf-8")).hexdigest()

            for cdir_name, size in [("normal", "128"), ("large", "256")]:
                cdir = os.path.expanduser(f"~/.cache/thumbnails/{cdir_name}")
                os.makedirs(cdir, exist_ok=True)
                cache_file = os.path.join(cdir, f"{uri_hash}.png")
                subprocess.run(
                    ["ffmpegthumbnailer", "-i", abs_path, "-o", cache_file, "-m", "-s", size],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False
                )
        except Exception:
            pass

    def download(
        self,
        url: str,
        is_playlist: bool = False,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        postprocessor_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Downloads the video/playlist with embedded thumbnail, best audio, and highest quality video.
        Returns a dict with success status, title, resolution, and output file path.
        """
        ydl_opts = self._build_ydl_opts(
            is_playlist=is_playlist,
            progress_callback=progress_callback,
            postprocessor_callback=postprocessor_callback
        )

        result = {
            "success": False,
            "title": "Unknown Title",
            "resolution": "HD",
            "video_id": "",
            "filepath": "",
            "error": None
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    result["title"] = info.get("title", "Unknown Title")
                    result["video_id"] = info.get("id", "")

                    # Determine final resolution display
                    height = info.get("height")
                    if height:
                        if height >= 4320:
                            result["resolution"] = f"8K ({height}p)"
                        elif height >= 2160:
                            result["resolution"] = f"4K ({height}p)"
                        elif height >= 1440:
                            result["resolution"] = f"2K ({height}p)"
                        elif height >= 1080:
                            result["resolution"] = f"Full HD ({height}p)"
                        elif height >= 720:
                            result["resolution"] = f"HD ({height}p)"
                        else:
                            result["resolution"] = f"{height}p"

                    # Verify embedded cover & clean up any separate image file
                    if result["video_id"]:
                        self._ensure_mp4_cover(result["video_id"])

                    result["success"] = True

        except Exception as e:
            result["error"] = str(e)

        return result
