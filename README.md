<div align="center">

# 🎬 OmniTube / Auto YouTube Downloader & Local Player

**Modern, cross-platform YouTube automation suite with Clipboard Auto-Monitor, Multi-Audio (Dubbing) switcher, 4K/8K downloads, persistent queues, and a sleek YouTube-like web player.**

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20|%20macOS%20|%20Linux-blue?style=for-the-badge)](#-multi-os-support)
[![yt-dlp](https://img.shields.io/badge/Engine-yt--dlp-red?style=for-the-badge)](https://github.com/yt-dlp/yt-dlp)
[![FFmpeg](https://img.shields.io/badge/Media-FFmpeg-007808?style=for-the-badge&logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

[Fitur](#-fitur-utama) • [Cara Menjalankan](#-cara-menjalankan) • [Web Player](#-local-youtube-web-player) • [Konfigurasi](#%EF%B8%8F-konfigurasi-configjson) • [Troubleshooting](#-troubleshooting)

</div>

---

## ✨ Fitur Utama

- 📋 **Auto Clipboard Monitor**:
  Cukup buka YouTube di browser atau aplikasi, lalu **Copy (Ctrl + C)** link video. Downloader akan langsung mendeteksi URL dan mulai mengunduh secara otomatis.
- 🎧 **Multi-Audio Track & Auto-Dubbing**:
  Mendukung video multi-bahasa (seperti MrBeast). Mengunduh trek asli (**English**) sekaligus trek sulih suara (**Bahasa Indonesia**) secara sinkron.
- 🍿 **YouTube-like Local Web Player**:
  Pemutar video lokal modern berbasis HTML5 di browser dengan tampilan ala YouTube:
  - Tombol ganti bahasa/sulih suara (Shortcut keyboard: `A`).
  - Thumbnail preview, progress bar tontonan, resume titik terakhir.
  - Shortcut playback lengkap (`Spasi`, `J`, `K`, `L`, `F`, `M`, `0-9`).
- 💾 **Persistent Queue (Antrean Tersimpan)**:
  Jika aplikasi ditutup (`Ctrl + C`) saat antrean belum selesai, seluruh sisa antrean disimpan ke `download_queue.json` dan **otomatis dilanjutkan saat aplikasi dijalankan kembali**.
- 🔄 **Network Auto-Resume**:
  Jika internet terputus, unduhan tidak akan hangus/gagal. Program menunggu koneksi pulih dan otomatis melanjutkan (*resume*) dari persentase terakhir (hemat kuota & waktu).
- 🖼️ **Embedded Cover Art & Real Thumbnails**:
  Menyematkan thumbnail resolusi tinggi langsung ke dalam wadah file `.mp4` sebagai cover art lagu/video.
- 💻 **100% Native Multi-OS Support**:
  Otomatis mendeteksi sistem operasi (Windows 10/11, macOS, Linux Wayland & X11) beserta penyesuaian clipboard, notifikasi desktop, dan warna terminal.

---

## 🖥️ Multi-OS Support

| Fitur | Linux | macOS | Windows |
| :--- | :--- | :--- | :--- |
| **Launcher** | `./start.sh` & `./play.sh` | `./start.sh` & `./play.sh` | `start.bat` & `play.bat` *(Double-click)* |
| **Clipboard** | `wl-paste` (Wayland) / `xclip` / `xsel` | `pbpaste` | Native Win32 Ctypes *(0% CPU, secepat kilat)* |
| **Notifikasi** | `notify-send` | AppleScript Notification Center | Windows Toast / Balloon Tip |
| **Terminal** | ANSI Colors UTF-8 | ANSI Colors UTF-8 | Virtual Terminal Processing + UTF-8 auto-fix |

---

## 🚀 Cara Menjalankan

### 1. Prasyarat
Pastikan sistem Anda telah memiliki:
- **Python 3.8+**
- **FFmpeg & FFprobe**
  - *Ubuntu/Debian:* `sudo apt install ffmpeg`
  - *Arch Linux:* `sudo pacman -S ffmpeg`
  - *macOS:* `brew install ffmpeg`
  - *Windows:* Unduh dari [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) dan tambahkan ke PATH.

Install dependensi Python:
```bash
pip install -r requirements.txt
```

---

### 2. Menjalankan Downloader

#### Di Windows:
Cukup klik ganda (**double-click**) file **`start.bat`**.

#### Di Linux / macOS:
```bash
./start.sh
```

#### Atau langsung via Python:
```bash
python main.py
```

Setelah aplikasi berjalan, cukup **COPY (Ctrl + C)** link video atau playlist dari YouTube. Unduhan akan berjalan otomatis!

---

### 3. Menjalankan Web Player Lokal

Buka browser dan nikmati koleksi video offline dengan tampilan YouTube modern:

#### Di Windows:
Klik ganda (**double-click**) file **`play.bat`**.

#### Di Linux / macOS:
```bash
./play.sh
```

Player otomatis terbuka di browser pada: **[http://localhost:8888](http://localhost:8888)**

---

## ⌨️ Shortcut Keyboard Web Player

| Tombol | Fungsi |
| :---: | :--- |
| **`Spasi` / `K`** | Play / Pause |
| **`J` / `L`** | Mundur 10 detik / Maju 10 detik |
| **`←` / `→`** | Mundur 5 detik / Maju 5 detik |
| **`↑` / `↓`** | Tambah / Kurangi volume |
| **`M`** | Mute / Unmute audio |
| **`F`** | Fullscreen |
| **`T`** | Theater Mode |
| **`A`** | **Ganti Trek Audio (Original ⟷ Sulih Suara Indonesia)** |
| **`0` - `9`** | Lompat ke 0% - 90% durasi video |

---

## ⚙️ Konfigurasi (`config.json`)

Anda dapat menyesuaikan preferensi unduhan di file `config.json`:

```json
{
  "download_dir": "downloads",
  "format_container": "mp4",
  "embed_thumbnail": true,
  "save_thumbnail_file": false,
  "embed_metadata": true,
  "max_resolution": null,
  "desktop_notifications": true,
  "prevent_re_download": true,
  "clipboard_check_interval": 0.8,
  "max_retries": 25,
  "retry_delay_seconds": 5,
  "auto_retry_on_network_loss": true,
  "multi_audio": true,
  "download_indonesian_dub": true
}
```

- **`max_resolution`**: Set `null` untuk kualitas tertinggi (4K/2K), atau angka (contoh: `1080`, `720`) untuk membatasi kuota.
- **`save_thumbnail_file`**: `false` menghasilkan hanya 1 file video rapi dengan cover art di dalamnya.
- **`multi_audio` & `download_indonesian_dub`**: Mengunduh trek sulih suara otomatis jika tersedia.

---

## 🛠️ Perintah Terminal Tambahan

- **Unduh link langsung tanpa lewat clipboard:**
  ```bash
  python main.py "https://www.youtube.com/watch?v=..."
  ```
- **Paksa unduh ulang video yang sudah ada di riwayat:**
  ```bash
  python main.py --force
  ```
- **Bersihkan sisa antrean yang tersimpan:**
  ```bash
  python main.py --clear-queue
  ```
- **Bersihkan riwayat unduhan:**
  ```bash
  python main.py --clear-history
  ```

---

## 📄 Lisensi
Proyek ini dilisensikan di bawah lisensi [MIT](LICENSE).
Bebas digunakan, dimodifikasi, dan didistribusikan untuk keperluan pribadi maupun edukasi.
