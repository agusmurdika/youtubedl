import os
import sys
import json
import time
import queue
import signal
import socket
import threading
from typing import Set, Dict, Any, Optional, List

import clipboard
from downloader import YouTubeDownloader
from notifier import send_notification
import system_compat

# ANSI styling colors
class Colors:
    HEADER    = '\033[95m'
    BLUE      = '\033[94m'
    CYAN      = '\033[96m'
    GREEN     = '\033[92m'
    YELLOW    = '\033[93m'
    RED       = '\033[91m'
    BOLD      = '\033[1m'
    DIM       = '\033[2m'
    RESET     = '\033[0m'
    CLEAR     = '\033[2K\r'

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
HISTORY_FILE = os.path.join(SCRIPT_DIR, "download_history.txt")
QUEUE_FILE = os.path.join(SCRIPT_DIR, "download_queue.json")

def load_config() -> Dict[str, Any]:
    defaults = {
        "download_dir": os.path.join(SCRIPT_DIR, "downloads"),
        "format_container": "mp4",
        "embed_thumbnail": True,
        "save_thumbnail_file": False,
        "embed_metadata": True,
        "max_resolution": None,
        "desktop_notifications": True,
        "prevent_re_download": True,
        "clipboard_check_interval": 0.8,
        "max_retries": 25,
        "retry_delay_seconds": 5,
        "auto_retry_on_network_loss": True
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_conf = json.load(f)
                defaults.update(user_conf)
        except Exception as e:
            print(f"{Colors.YELLOW}[Peringatan] Gagal membaca config.json ({e}), menggunakan setelan bawaan.{Colors.RESET}")

    # Resolve download directory relative to script if not absolute
    if not os.path.isabs(defaults["download_dir"]):
        defaults["download_dir"] = os.path.abspath(os.path.join(SCRIPT_DIR, defaults["download_dir"]))

    return defaults

def load_history() -> Set[str]:
    history = set()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    item_id = line.strip()
                    if item_id:
                        history.add(item_id)
        except Exception:
            pass
    return history

def save_to_history(item_id: str):
    try:
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(item_id + "\n")
    except Exception:
        pass

def load_saved_queue() -> List[Dict[str, str]]:
    """Loads unfinished queue items from download_queue.json."""
    if os.path.exists(QUEUE_FILE):
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []

def save_queue_file(items: List[Dict[str, str]]):
    """Safely saves queue items to download_queue.json using atomic replace."""
    try:
        if not items:
            if os.path.exists(QUEUE_FILE):
                os.remove(QUEUE_FILE)
            return
        tmp_file = QUEUE_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, QUEUE_FILE)
    except Exception:
        pass

def print_banner(config: Dict[str, Any], os_info: Dict[str, Any]):
    print(f"{Colors.CYAN}{Colors.BOLD}=" * 66 + f"{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}   🎥 AUTO YOUTUBE DOWNLOADER (HD / 4K / Audio / Thumbnail){Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}=" * 66 + f"{Colors.RESET}")
    print(f" {Colors.BOLD}💻 Sistem Operasi :{Colors.RESET} {os_info['os_name']} | {os_info['desktop_env']}")
    ffmpeg_badge = f"{Colors.GREEN}✔ {os_info['ffmpeg_version']}{Colors.RESET}" if os_info['ffmpeg_available'] else f"{Colors.RED}✘ Tidak ditemukan!{Colors.RESET}"
    print(f" {Colors.BOLD}🎬 FFmpeg Status  :{Colors.RESET} {ffmpeg_badge}")
    print(f" {Colors.BOLD}📋 Clipboard Tool :{Colors.RESET} {os_info['clip_backend']}")
    notif_badge = f"{Colors.GREEN}Aktif ({os_info['notif_backend']}){Colors.RESET}" if config.get('desktop_notifications') else f"{Colors.DIM}Nonaktif{Colors.RESET}"
    print(f" {Colors.BOLD}🔔 Notifikasi     :{Colors.RESET} {notif_badge}")
    print(f" {Colors.BOLD}📁 Folder Unduhan :{Colors.RESET} {config['download_dir']}")
    print(f" {Colors.BOLD}🎞️ Format Video   :{Colors.RESET} {config['format_container'].upper()} (Best Video + Best Audio)")
    max_res = f"{config['max_resolution']}p (Limit)" if config.get('max_resolution') else "Maksimal (4K / 2K / 1080p HD)"
    print(f" {Colors.BOLD}📐 Resolusi Video :{Colors.RESET} {max_res}")
    print(f" {Colors.BOLD}🖼️ Thumbnail      :{Colors.RESET} Disematkan Langsung ke Video (Cover Art)" + (" + File JPG" if config.get('save_thumbnail_file') else " (Hanya 1 File Video)"))
    print(f" {Colors.BOLD}🔄 Auto Retry     :{Colors.RESET} Aktif (Auto-resume jika internet putus, maks {config.get('max_retries', 25)}x)")
    print(f" {Colors.BOLD}💾 Antrean        :{Colors.RESET} {Colors.GREEN}Persisten (Tersimpan otomatis, auto-resume jika di-stop){Colors.RESET}")
    print(f" {Colors.BOLD}📋 Mode           :{Colors.RESET} {Colors.GREEN}Auto Clipboard Monitor (Aktif){Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}=" * 66 + f"{Colors.RESET}")
    print(f"{Colors.DIM} 💡 Panduan:{Colors.RESET}")
    print(f"{Colors.DIM}    Cukup COPY (Ctrl+C) link YouTube dari browser/aplikasi.{Colors.RESET}")
    print(f"{Colors.DIM}    Video akan langsung terdeteksi & diunduh otomatis seberapa banyakpun.{Colors.RESET}")
    print(f"{Colors.DIM}    Jika dihentikan [Ctrl+C], sisa antrean akan otomatis tersimpan.{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}=" * 66 + f"{Colors.RESET}\n")

class AppState:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.history = load_history()
        self.task_queue = queue.Queue()
        self.queued_ids: Set[str] = set()
        self.pending_items: List[Dict[str, str]] = []
        self.current_item: Optional[Dict[str, str]] = None
        self.running = True
        self.downloader = YouTubeDownloader(config)
        self.lock = threading.RLock()

    @property
    def current_id(self) -> Optional[str]:
        with self.lock:
            return self.current_item["id"] if self.current_item else None

    def _persist_queue(self):
        with self.lock:
            items_to_save = []
            if self.current_item:
                items_to_save.append(self.current_item)
            items_to_save.extend(self.pending_items)
            save_queue_file(items_to_save)

    def is_in_queue_or_active(self, item_id: str) -> bool:
        with self.lock:
            return (item_id in self.queued_ids) or (self.current_id == item_id)

    def add_to_queue(self, item: Dict[str, str], persist: bool = True):
        with self.lock:
            if item["id"] in self.queued_ids:
                return
            self.queued_ids.add(item["id"])
            self.pending_items.append(item)
            if persist:
                self._persist_queue()
        self.task_queue.put(item)

    def start_downloading(self, item: Dict[str, str]):
        with self.lock:
            self.current_item = item
            self.pending_items = [p for p in self.pending_items if p["id"] != item["id"]]
            self._persist_queue()

    def mark_completed(self, item_id: str):
        with self.lock:
            self.history.add(item_id)
            if item_id in self.queued_ids:
                self.queued_ids.remove(item_id)
            if self.current_item and self.current_item["id"] == item_id:
                self.current_item = None
            self.pending_items = [p for p in self.pending_items if p["id"] != item_id]
            self._persist_queue()
        save_to_history(item_id)

    def mark_failed(self, item_id: str):
        with self.lock:
            if item_id in self.queued_ids:
                self.queued_ids.remove(item_id)
            if self.current_item and self.current_item["id"] == item_id:
                self.current_item = None
            self.pending_items = [p for p in self.pending_items if p["id"] != item_id]
            self._persist_queue()

    def save_on_exit(self):
        with self.lock:
            self._persist_queue()

def make_progress_hook():
    last_print = 0
    bar_width = 24

    def hook(d: Dict[str, Any]):
        nonlocal last_print
        now = time.time()
        status = d.get("status")

        if status == "downloading":
            if now - last_print < 0.15:
                return
            last_print = now

            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0

            percent = 0.0
            if total > 0:
                percent = min(100.0, (downloaded / total) * 100.0)

            filled = int(bar_width * percent / 100)
            bar = "█" * filled + "░" * (bar_width - filled)

            speed_str = d.get("_speed_str", "").strip() or "N/A"
            eta_str = d.get("_eta_str", "").strip() or "N/A"

            sys.stdout.write(
                f"{Colors.CLEAR}  {Colors.GREEN}[{bar}]{Colors.RESET} {Colors.BOLD}{percent:5.1f}%{Colors.RESET} | "
                f"{Colors.CYAN}{speed_str:>10}{Colors.RESET} | ETA: {Colors.YELLOW}{eta_str:>5}{Colors.RESET}"
            )
            sys.stdout.flush()

        elif status == "finished":
            sys.stdout.write(f"{Colors.CLEAR}  {Colors.BLUE}⚡ Selesai mengunduh stream. Menggabungkan audio, video & thumbnail...{Colors.RESET}\n")
            sys.stdout.flush()

    return hook

def check_internet_connection(host: str = "1.1.1.1", port: int = 53, timeout: float = 3.0) -> bool:
    """Fast check if internet connection is currently reachable."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect(("8.8.8.8", port))
            s.close()
            return True
        except Exception:
            return False

def wait_for_internet_connection(state: AppState, check_interval: int = 5) -> bool:
    """
    Blocks until internet connection is restored or the user interrupts.
    Updates console and sends desktop notification.
    """
    if check_internet_connection():
        return True

    print(f"\n{Colors.BOLD}{Colors.YELLOW}⚠️  [Koneksi Terputus] Koneksi internet tidak terdeteksi!{Colors.RESET}")
    print(f"{Colors.YELLOW}   Menunggu internet kembali untuk melanjutkan download otomatis...{Colors.RESET}")

    if state.config.get("desktop_notifications"):
        send_notification(
            title="⚠️ Koneksi Internet Terputus",
            message="Menunggu internet kembali untuk melanjutkan download...",
            urgency="critical"
        )

    dots = 0
    while state.running:
        time.sleep(check_interval)
        if check_internet_connection():
            print(f"\n{Colors.BOLD}{Colors.GREEN}✔ [Internet Tersambung] Koneksi pulih kembali!{Colors.RESET}")
            print(f"{Colors.CYAN}   Melanjutkan proses unduhan dari titik terakhir (auto-resume)...{Colors.RESET}\n")

            if state.config.get("desktop_notifications"):
                send_notification(
                    title="✅ Internet Pulih",
                    message="Melanjutkan unduhan video dari posisi terakhir...",
                    urgency="normal"
                )
            return True
        dots = (dots + 1) % 4
        sys.stdout.write(f"\r{Colors.YELLOW}   Menunggu internet terhubung kembali{'.' * dots}{' ' * (3 - dots)} (cek setiap {check_interval}s){Colors.RESET}")
        sys.stdout.flush()

    return False

def download_worker(state: AppState):
    max_retries = state.config.get("max_retries", 25)
    retry_delay = state.config.get("retry_delay_seconds", 5)
    auto_retry_net = state.config.get("auto_retry_on_network_loss", True)

    while state.running:
        try:
            item = state.task_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        item_id = item["id"]
        item_url = item["url"]
        item_type = item.get("type", "video")
        is_playlist = (item_type == "playlist")

        with state.lock:
            state.start_downloading(item)

        remaining = state.task_queue.qsize()
        queue_badge = f"{Colors.YELLOW}[Sisa antrean: {remaining}]{Colors.RESET}" if remaining > 0 else ""
        print(f"\n{Colors.BOLD}{Colors.CYAN}▶ Memulai Download:{Colors.RESET} {item_url} {queue_badge}")

        if state.config.get("desktop_notifications"):
            send_notification(
                title="⬇️ Mengunduh Video YouTube",
                message=f"Sedang mengunduh: {item_url}\nSisa antrean: {remaining}",
                urgency="normal"
            )

        attempt = 0
        success = False

        while state.running and not success:
            attempt += 1

            # Pastikan koneksi internet terhubung sebelum mencoba
            if auto_retry_net and not check_internet_connection():
                if not wait_for_internet_connection(state):
                    break

            progress_callback = make_progress_hook()

            res = state.downloader.download(
                url=item_url,
                is_playlist=is_playlist,
                progress_callback=progress_callback
            )

            if res["success"]:
                success = True
                state.mark_completed(item_id)
                title = res.get("title", item_url)
                resolution = res.get("resolution", "HD")
                print(f"  {Colors.BOLD}{Colors.GREEN}✔ BERHASIL DIUNDUH!{Colors.RESET}")
                print(f"    {Colors.BOLD}Judul    :{Colors.RESET} {title}")
                print(f"    {Colors.BOLD}Resolusi :{Colors.RESET} {Colors.GREEN}{resolution}{Colors.RESET}")
                print(f"    {Colors.BOLD}Lokasi   :{Colors.RESET} {state.config['download_dir']}\n")

                if state.config.get("desktop_notifications"):
                    send_notification(
                        title="✅ Download Selesai!",
                        message=f"{title}\nResolusi: {resolution}",
                        urgency="normal"
                    )
                break
            else:
                err = res.get("error", "Kesalahan tidak diketahui")
                err_lower = err.lower()

                # Cek apakah kegagalan disebabkan oleh koneksi jaringan terputus
                is_net_err = any(w in err_lower for w in [
                    "network", "unreachable", "connection", "timed out", "timeout",
                    "reset", "broken pipe", "errno 101", "errno 104", "nodename",
                    "servname", "gaierror", "temporary failure", "failed to establish",
                    "remote disconnected", "urlerror", "httperror"
                ]) or not check_internet_connection()

                if auto_retry_net and is_net_err:
                    print(f"\n{Colors.YELLOW}⚠️  Terjadi gangguan koneksi internet saat mengunduh.{Colors.RESET}")
                    print(f"{Colors.YELLOW}   Percobaan {attempt}/{max_retries}. Menunggu koneksi pulih...{Colors.RESET}")

                    if not wait_for_internet_connection(state):
                        break

                    if attempt < max_retries:
                        print(f"{Colors.CYAN}   Melanjutkan unduhan (resume) dalam {retry_delay} detik...{Colors.RESET}")
                        time.sleep(retry_delay)
                        continue
                    else:
                        print(f"{Colors.RED}❌ Mencapai batas maksimal {max_retries} kali percobaan retry.{Colors.RESET}")
                        state.mark_failed(item_id)
                        break
                else:
                    # Kesalahan non-jaringan (misal video dibatasi usia, private, atau dihapus)
                    state.mark_failed(item_id)
                    print(f"  {Colors.BOLD}{Colors.RED}✘ GAGAL MENGUNDUH:{Colors.RESET} {err}\n")

                    if state.config.get("desktop_notifications"):
                        send_notification(
                            title="❌ Download Gagal",
                            message=f"Gagal mengunduh: {item_url}\n{err[:80]}",
                            urgency="critical"
                        )
                    break

        state.task_queue.task_done()

def clipboard_monitor(state: AppState):
    last_clipboard = ""
    interval = state.config.get("clipboard_check_interval", 0.8)

    while state.running:
        try:
            current_clipboard = clipboard.get_clipboard_text()
            if current_clipboard and current_clipboard != last_clipboard:
                last_clipboard = current_clipboard
                detected_items = clipboard.extract_youtube_items(current_clipboard)

                for item in detected_items:
                    item_id = item["id"]
                    item_url = item["url"]
                    item_type = item.get("type", "video")

                    # Check if already in queue or actively downloading
                    if state.is_in_queue_or_active(item_id):
                        continue

                    # Check history if prevention is enabled
                    if state.config.get("prevent_re_download", True) and (item_id in state.history):
                        print(f"{Colors.DIM}  [Lewati] Video sudah pernah diunduh sebelumnya: {item_url}{Colors.RESET}")
                        continue

                    # Add new item to download queue
                    state.add_to_queue(item)
                    q_size = state.task_queue.qsize()

                    label = "Playlist" if item_type == "playlist" else "Video"
                    print(f"{Colors.BOLD}{Colors.GREEN}📥 Link {label} Terdeteksi!{Colors.RESET} {Colors.CYAN}{item_url}{Colors.RESET} (Antrean: {q_size})")

                    if state.config.get("desktop_notifications"):
                        send_notification(
                            title=f"📥 Link {label} Ditambahkan ke Antrean",
                            message=f"{item_url}\nTotal dalam antrean: {q_size}",
                            urgency="low"
                        )

            time.sleep(interval)
        except Exception:
            time.sleep(interval)

def main():
    config = load_config()

    # CLI argument parsing
    force_download = "--force" in sys.argv
    clear_history = "--clear-history" in sys.argv
    clear_queue = "--clear-queue" in sys.argv

    if clear_history:
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
            print(f"{Colors.GREEN}✔ Riwayat unduhan berhasil dibersihkan.{Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}Riwayat unduhan kosong.{Colors.RESET}")
        if not clear_queue and not any(arg for arg in sys.argv[1:] if not arg.startswith("--")):
            return

    if clear_queue:
        if os.path.exists(QUEUE_FILE):
            os.remove(QUEUE_FILE)
            print(f"{Colors.GREEN}✔ Antrean unduhan tersimpan berhasil dibersihkan.{Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}Antrean unduhan tersimpan sudah kosong.{Colors.RESET}")
        if not any(arg for arg in sys.argv[1:] if not arg.startswith("--")):
            return

    if force_download:
        config["prevent_re_download"] = False

    system_compat.init_system()
    os_info = system_compat.get_os_info()
    print_banner(config, os_info)

    state = AppState(config)

    # 1. Load persistent queue saved from previous session
    saved_items = load_saved_queue()
    if saved_items:
        valid_saved = []
        for it in saved_items:
            # Skip if already downloaded in history, unless --force
            if config.get("prevent_re_download", True) and (it["id"] in state.history) and not force_download:
                continue
            valid_saved.append(it)

        if valid_saved:
            print(f"{Colors.BOLD}{Colors.YELLOW}🔄 [Antrean Tersimpan] Ditemukan {len(valid_saved)} video dari sesi sebelumnya:{Colors.RESET}")
            for idx, it in enumerate(valid_saved, 1):
                label = "Playlist" if it.get("type") == "playlist" else "Video"
                print(f"   {idx}. [{label}] {Colors.CYAN}{it['url']}{Colors.RESET}")
            print(f"{Colors.GREEN}   ▶ Melanjutkan unduhan otomatis secara berurutan...{Colors.RESET}\n")

            for it in valid_saved:
                state.add_to_queue(it, persist=False)
            state.save_on_exit()

    # 2. Check for direct manual URLs in sys.argv
    manual_urls = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    for u in manual_urls:
        items = clipboard.extract_youtube_items(u)
        for item in items:
            state.add_to_queue(item)
            print(f"{Colors.GREEN}📥 URL manual ditambahkan:{Colors.RESET} {item['url']}")

    # Setup signal handler for graceful shutdown
    def handle_sigint(signum, frame):
        print(f"\n\n{Colors.YELLOW}🛑 Menghentikan aplikasi...{Colors.RESET}")
        state.running = False
        remaining_cnt = len(state.pending_items) + (1 if state.current_item else 0)
        if remaining_cnt > 0:
            state.save_on_exit()
            print(f"{Colors.GREEN}💾 Antrean tersisa ({remaining_cnt} video) tersimpan otomatis di download_queue.json.{Colors.RESET}")
            print(f"{Colors.CYAN}   Jalankan kembali 'python3 main.py' untuk otomatis melanjutkan unduhan!{Colors.RESET}\n")
        else:
            print(f"{Colors.GREEN}✔ Semua antrean sudah selesai diunduh.{Colors.RESET}\n")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    # Start download worker thread
    worker = threading.Thread(target=download_worker, args=(state,), daemon=True)
    worker.start()

    # Start clipboard watcher thread
    watcher = threading.Thread(target=clipboard_monitor, args=(state,), daemon=True)
    watcher.start()

    print(f"{Colors.GREEN}● Menunggu link di clipboard... Silakan buka YouTube dan COPY (Ctrl+C) link video.{Colors.RESET}\n")

    try:
        while state.running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        handle_sigint(None, None)

if __name__ == "__main__":
    main()
