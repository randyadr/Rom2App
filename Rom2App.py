#!/usr/bin/env python3
"""
Rom2App — Unified ROM AppImage Builder
Supports: PS1 · PS2 · PSP · GameCube · Xbox (OG) · PS3 · Xbox 360 · Wii U · Switch
"""

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import threading
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ─── Constants ────────────────────────────────────────────────────────────────

APP_VERSION = "1.0.4-rom-appimage-arch-patch"
# File pickers start here when nothing has been selected yet.
DEFAULT_START_DIR = "/mnt" if os.path.isdir("/mnt") else str(Path.home())
CONFIG_DIR  = Path.home() / ".config" / "rom2app"
CONFIG_FILE = CONFIG_DIR / "settings.json"
CACHE_DIR   = CONFIG_DIR / "cache"
LOG_DIR     = Path.home() / ".local" / "share" / "rom2app"
LOG_FILE    = LOG_DIR / "rom2app.log"
LOCAL_APP_DIR    = Path.home() / ".local/share/applications"
LOCAL_ICON_BASE  = Path.home() / ".local/share/icons/hicolor"

DEFAULT_STEAMGRIDDB_KEY = "cb04fd6d4724b473d2706ae4269de8e8"
STEAMGRIDDB_API_BASE    = "https://www.steamgriddb.com/api/v2"

ICON_SIZES = [16, 22, 24, 32, 48, 64, 96, 128, 256, 512]

# PS3 Store ID Database - Maps Sony Store content IDs to game titles
PS3_STORE_IDS = {
    "NPEB01152": "Game Title 1",
    "NPUA80316": "Game Title 2", 
    "NPUA80664": "Game Title 3",
    "NPUA80875": "Game Title 4",
    # Add more PS3 Store IDs here as needed
    # Format: Store ID (region prefix + ID): Game Name
    # Region prefixes: NPEA/NPEB = Europe, NPUA = America, NPJA = Japan, NPKA = Korea, etc.
}

PLATFORMS = {
    "PS1": {
        "label": "PlayStation 1",
        "emulator_hint": "DuckStation",
        "exts": {".cue", ".bin", ".img", ".ecm", ".pbp", ".chd", ".zip", ".7z"},
        "data_exts": {".bin", ".img", ".ecm"},
        "cover_urls": [
            "https://raw.githubusercontent.com/xlenore/psx-covers/main/covers/3d/{serial}.png",
            "https://raw.githubusercontent.com/xlenore/psx-covers/main/covers/default/{serial}.jpg",
            "https://raw.githubusercontent.com/xlenore/psx-covers/main/covers/default/{serial}.png",
        ],
        "title_db_urls": [
            "https://github.com/niemasd/GameDB-PSX/releases/latest/download/PSX.titles.json",
            "https://raw.githubusercontent.com/niemasd/GameDB-PSX/main/PSX.titles.json",
        ],
        "app_id_prefix": "ps1app",
        "stable_dir_name": "rom-appimage-ps1",
        "cover_mode": "serial",
        "launch_flag": "",
    },
    "PS2": {
        "label": "PlayStation 2",
        "emulator_hint": "PCSX2",
        "exts": {".iso", ".bin", ".cue", ".img", ".mdf", ".nrg", ".chd", ".cso", ".zso", ".gz", ".isz", ".pbp", ".ecm", ".zip", ".7z"},
        "data_exts": {".bin", ".img", ".ecm"},
        "cover_urls": [
            "https://raw.githubusercontent.com/xlenore/ps2-covers/main/covers/3d/{serial}.png",
            "https://raw.githubusercontent.com/xlenore/ps2-covers/main/covers/default/{serial}.jpg",
        ],
        "title_db_urls": [
            "https://github.com/niemasd/GameDB-PS2/releases/latest/download/PS2.titles.json",
            "https://raw.githubusercontent.com/niemasd/GameDB-PS2/main/PS2.titles.json",
        ],
        "app_id_prefix": "ps2app",
        "stable_dir_name": "rom-appimage-ps2",
        "cover_mode": "serial",
        "launch_flag": "",
    },
    "PSP": {
        "label": "PlayStation Portable",
        "emulator_hint": "PPSSPP",
        "exts": {".iso", ".cso", ".chd", ".pbp"},
        "data_exts": set(),
        "cover_urls": [
            "https://raw.githubusercontent.com/libretro-thumbnails/Sony%20-%20PlayStation%20Portable/master/Named_Boxarts/{title}.png",
        ],
        "title_db_urls": [
            "https://github.com/niemasd/GameDB-PSP/releases/latest/download/PSP.titles.json",
            "https://raw.githubusercontent.com/niemasd/GameDB-PSP/main/PSP.titles.json",
        ],
        "app_id_prefix": "pspapp",
        "stable_dir_name": "rom-appimage-psp",
        "cover_mode": "title",
        "launch_flag": "",
    },
    "GameCube": {
        "label": "Nintendo GameCube",
        "emulator_hint": "Dolphin",
        "exts": {".iso", ".gcm", ".gcz", ".rvz", ".ciso", ".wbfs"},
        "data_exts": set(),
        "cover_urls": [
            "https://raw.githubusercontent.com/libretro-thumbnails/Nintendo%20-%20GameCube/master/Named_Boxarts/{title}.png",
        ],
        "title_db_urls": [],
        "app_id_prefix": "gcapp",
        "stable_dir_name": "rom-appimage-gamecube",
        "cover_mode": "title",
        "launch_flag": "-e",
    },
    "Xbox": {
        "label": "Xbox (Original)",
        "emulator_hint": "xemu",
        "exts": {".iso", ".xiso"},
        "data_exts": set(),
        "cover_urls": [
            "https://raw.githubusercontent.com/libretro-thumbnails/Microsoft%20-%20Xbox/master/Named_Boxarts/{title}.png",
        ],
        "title_db_urls": [],
        "app_id_prefix": "xboxapp",
        "stable_dir_name": "rom-appimage-xbox",
        "cover_mode": "title",
        "launch_flag": "-dvd_path",
    },
    "PS3": {
        "label": "PlayStation 3",
        "emulator_hint": "RPCS3",
        "exts": {".iso", ".pkg"},
        "data_exts": set(),
        "cover_urls": [
            "https://raw.githubusercontent.com/xlenore/ps3-covers/main/covers/default/{serial}.jpg",
            "https://raw.githubusercontent.com/libretro-thumbnails/Sony%20-%20PlayStation%203/master/Named_Boxarts/{title}.png",
        ],
        "title_db_urls": [
            "https://github.com/niemasd/GameDB-PS3/releases/latest/download/PS3.titles.json",
            "https://raw.githubusercontent.com/niemasd/GameDB-PS3/main/PS3.titles.json",
        ],
        "app_id_prefix": "ps3app",
        "stable_dir_name": "rom-appimage-ps3",
        "cover_mode": "serial",
        "launch_flag": "",
    },
    "Xbox360": {
        "label": "Xbox 360",
        "emulator_hint": "Xenia",
        "exts": {".iso", ".xex", ".zar"},
        "data_exts": set(),
        "cover_urls": [
            "https://raw.githubusercontent.com/libretro-thumbnails/Microsoft%20-%20Xbox%20360/master/Named_Boxarts/{title}.png",
        ],
        "title_db_urls": [],
        "app_id_prefix": "x360app",
        "stable_dir_name": "rom-appimage-xbox360",
        "cover_mode": "title",
        "launch_flag": "",
    },
    "WiiU": {
        "label": "Nintendo Wii U",
        "emulator_hint": "Cemu",
        "exts": {".wud", ".wux", ".iso", ".rpx", ".wua"},
        "data_exts": set(),
        "cover_urls": [
            "https://raw.githubusercontent.com/libretro-thumbnails/Nintendo%20-%20Wii%20U/master/Named_Boxarts/{title}.png",
        ],
        "title_db_urls": [],
        "app_id_prefix": "wiiuapp",
        "stable_dir_name": "rom-appimage-wiiu",
        "cover_mode": "title",
        "launch_flag": "",
    },
    "Switch": {
        "label": "Nintendo Switch",
        "emulator_hint": "Ryujinx",
        "exts": {".nsp", ".xci", ".nca", ".nro"},
        "data_exts": set(),
        "cover_urls": [
            "https://raw.githubusercontent.com/libretro-thumbnails/Nintendo%20-%20Nintendo%20Switch/master/Named_Boxarts/{title}.png",
        ],
        "title_db_urls": [],
        "app_id_prefix": "switchapp",
        "stable_dir_name": "rom-appimage-switch",
        "cover_mode": "title",
        "launch_flag": "",
        "no_extract": True,
    },
}

# ─── Themes ───────────────────────────────────────────────────────────────────
# Each theme defines the full palette. The active palette lives in COLORS, which
# widgets read directly; switching themes updates COLORS in place and rebuilds
# the UI so the new colours take effect everywhere.
THEMES = {
    "Midnight": {
        "bg":         "#1e1e2e", "sidebar":    "#161622", "card":       "#252538",
        "card_hover": "#2e2e48", "accent":     "#6C63FF", "accent2":    "#A78BFA",
        "success":    "#4ADE80", "warning":    "#FACC15", "danger":     "#F87171",
        "text":       "#E2E8F0", "text_dim":   "#94A3B8", "border":     "#334155",
        "input_bg":   "#1a1a2e", "log_bg":     "#0f0f1a", "log_fg":     "#A0C4FF",
    },
    "Light": {
        "bg":         "#F4F4F8", "sidebar":    "#E8E8F0", "card":       "#FFFFFF",
        "card_hover": "#ECECF6", "accent":     "#6C63FF", "accent2":    "#8B7CF6",
        "success":    "#16A34A", "warning":    "#CA8A04", "danger":     "#DC2626",
        "text":       "#1E1E2E", "text_dim":   "#64748B", "border":     "#CBD5E1",
        "input_bg":   "#FFFFFF", "log_bg":     "#F1F1F6", "log_fg":     "#1E3A8A",
    },
    "Dracula": {
        "bg":         "#282A36", "sidebar":    "#21222C", "card":       "#343746",
        "card_hover": "#3C3F51", "accent":     "#BD93F9", "accent2":    "#FF79C6",
        "success":    "#50FA7B", "warning":    "#F1FA8C", "danger":     "#FF5555",
        "text":       "#F8F8F2", "text_dim":   "#9CA3AF", "border":     "#44475A",
        "input_bg":   "#1E1F29", "log_bg":     "#191A21", "log_fg":     "#8BE9FD",
    },
    "Nord": {
        "bg":         "#2E3440", "sidebar":    "#272C36", "card":       "#3B4252",
        "card_hover": "#434C5E", "accent":     "#88C0D0", "accent2":    "#81A1C1",
        "success":    "#A3BE8C", "warning":    "#EBCB8B", "danger":     "#BF616A",
        "text":       "#ECEFF4", "text_dim":   "#9AA5B5", "border":     "#4C566A",
        "input_bg":   "#272C36", "log_bg":     "#21262E", "log_fg":     "#8FBCBB",
    },
    "Solarized Dark": {
        "bg":         "#002B36", "sidebar":    "#00252E", "card":       "#073642",
        "card_hover": "#0A4252", "accent":     "#268BD2", "accent2":    "#2AA198",
        "success":    "#859900", "warning":    "#B58900", "danger":     "#DC322F",
        "text":       "#EEE8D5", "text_dim":   "#93A1A1", "border":     "#094D5C",
        "input_bg":   "#00252E", "log_bg":     "#001E26", "log_fg":     "#93A1A1",
    },
    "Monokai": {
        "bg":         "#272822", "sidebar":    "#1E1F1C", "card":       "#3E3D32",
        "card_hover": "#49483E", "accent":     "#F92672", "accent2":    "#FD971F",
        "success":    "#A6E22E", "warning":    "#E6DB74", "danger":     "#F92672",
        "text":       "#F8F8F2", "text_dim":   "#9E9E9E", "border":     "#49483E",
        "input_bg":   "#1E1F1C", "log_bg":     "#141411", "log_fg":     "#66D9EF",
    },
    "Gruvbox Dark": {
        "bg":         "#282828", "sidebar":    "#1D2021", "card":       "#3C3836",
        "card_hover": "#504945", "accent":     "#B8BB26", "accent2":    "#FABD2F",
        "success":    "#B8BB26", "warning":    "#FABD2F", "danger":     "#FB4934",
        "text":       "#EBD5B7", "text_dim":   "#928374", "border":     "#504945",
        "input_bg":   "#1D2021", "log_bg":     "#0F0E0C", "log_fg":     "#83A598",
    },
    "Tokyo Night": {
        "bg":         "#1A1B26", "sidebar":    "#0F1117", "card":       "#2E3150",
        "card_hover": "#3D4166", "accent":     "#7AA2F7", "accent2":    "#BB9AF7",
        "success":    "#9ECE6A", "warning":    "#E0AF68", "danger":     "#F7768E",
        "text":       "#C0CAF5", "text_dim":   "#656B83", "border":     "#3D3D54",
        "input_bg":   "#0F1117", "log_bg":     "#0B0E14", "log_fg":     "#7DCFFF",
    },
    "Onedark Pro": {
        "bg":         "#282C34", "sidebar":    "#21252B", "card":       "#3E4451",
        "card_hover": "#484E55", "accent":     "#61AFEF", "accent2":    "#56B6C2",
        "success":    "#98C379", "warning":    "#E5C07B", "danger":     "#E06C75",
        "text":       "#ABB2BF", "text_dim":   "#5C6370", "border":     "#3E4451",
        "input_bg":   "#1E2227", "log_bg":     "#12131A", "log_fg":     "#56B6C2",
    },
    "Material Darker": {
        "bg":         "#212121", "sidebar":    "#1A1A1A", "card":       "#2C2C2C",
        "card_hover": "#373737", "accent":     "#82B1FF", "accent2":    "#B39DDB",
        "success":    "#C3E88D", "warning":    "#FFD54F", "danger":     "#FF5252",
        "text":       "#EEFFFF", "text_dim":   "#9E9E9E", "border":     "#424242",
        "input_bg":   "#1A1A1A", "log_bg":     "#0D0D0D", "log_fg":     "#80DEEA",
    },
    "Synthwave": {
        "bg":         "#0F0B1E", "sidebar":    "#0A0415", "card":       "#1A1030",
        "card_hover": "#2D1B4E", "accent":     "#FF1654", "accent2":    "#FF006E",
        "success":    "#39FF14", "warning":    "#FFFD38", "danger":     "#FF1654",
        "text":       "#FADADD", "text_dim":   "#B19CD9", "border":     "#441D62",
        "input_bg":   "#0A0415", "log_bg":     "#050209", "log_fg":     "#00FFFF",
    },
    "Catppuccin Mocha": {
        "bg":         "#1e1e2e", "sidebar":    "#181825", "card":       "#313244",
        "card_hover": "#45475A", "accent":     "#89B4FA", "accent2":    "#CBA6F7",
        "success":    "#A6E3A1", "warning":    "#F9E2AF", "danger":     "#F38BA8",
        "text":       "#CDD6F4", "text_dim":   "#9399B2", "border":     "#45475A",
        "input_bg":   "#181825", "log_bg":     "#11111B", "log_fg":     "#89DCEB",
    },
    "Forest Green": {
        "bg":         "#0D2818", "sidebar":    "#0A200F", "card":       "#1A3D2A",
        "card_hover": "#245836", "accent":     "#4CAF50", "accent2":    "#81C784",
        "success":    "#66BB6A", "warning":    "#FDD835", "danger":     "#E53935",
        "text":       "#E8F5E9", "text_dim":   "#A1D5A1", "border":     "#2E5C3F",
        "input_bg":   "#0A200F", "log_bg":     "#050F0A", "log_fg":     "#80C883",
    },
    "High Contrast": {
        "bg":         "#000000", "sidebar":    "#0A0A0A", "card":       "#1F1F1F",
        "card_hover": "#333333", "accent":     "#00FF00", "accent2":    "#00CCFF",
        "success":    "#00FF00", "warning":    "#FFFF00", "danger":     "#FF0000",
        "text":       "#FFFFFF", "text_dim":   "#AAAAAA", "border":     "#555555",
        "input_bg":   "#0A0A0A", "log_bg":     "#000000", "log_fg":     "#00FFFF",
    },
    "Pastel Dreams": {
        "bg":         "#F5E6E8", "sidebar":    "#EDDBDC", "card":       "#FFF5F7",
        "card_hover": "#FFE8ED", "accent":     "#D291BC", "accent2":    "#E8B4D9",
        "success":    "#98D8C8", "warning":    "#F7DC6F", "danger":     "#F8989C",
        "text":       "#5A4A52", "text_dim":   "#9B8B93", "border":     "#E0D0D5",
        "input_bg":   "#FFF5F7", "log_bg":     "#F9EFF1", "log_fg":     "#7B6BA8",
    },
    "Ocean Blue": {
        "bg":         "#0A1E3E", "sidebar":    "#061528", "card":       "#1A3A5C",
        "card_hover": "#2A5A8C", "accent":     "#4FC3F7", "accent2":    "#81D4FA",
        "success":    "#66BB6A", "warning":    "#FFD54F", "danger":     "#EF5350",
        "text":       "#E1F5FE", "text_dim":   "#80DEEA", "border":     "#2A5A8C",
        "input_bg":   "#061528", "log_bg":     "#030D1A", "log_fg":     "#4FC3F7",
    },
    "Cherry": {
        "bg":         "#291F35", "sidebar":    "#1F1528", "card":       "#3E3348",
        "card_hover": "#524066", "accent":     "#E75480", "accent2":    "#FF1744",
        "success":    "#7CFC00", "warning":    "#FFD700", "danger":     "#E75480",
        "text":       "#F5F5F5", "text_dim":   "#B8A8B8", "border":     "#524066",
        "input_bg":   "#1F1528", "log_bg":     "#0D0A15", "log_fg":     "#FF69B4",
    },
}
DEFAULT_THEME = "Midnight"

# Active palette — populated from the saved theme at startup.
COLORS = dict(THEMES[DEFAULT_THEME])

# Cover-art preview thumbnail sizes (width, height) — larger = bigger preview.
PREVIEW_SIZES = {
    "Small":       (80, 120),
    "Medium":      (130, 190),
    "Large":       (170, 240),
    "Extra Large": (220, 310),
}
DEFAULT_PREVIEW = "Large"

PLATFORM_COLORS = {
    "PS1":      "#0070D1",
    "PS2":      "#00439C",
    "PSP":      "#003791",
    "GameCube": "#6A0DAD",
    "Xbox":     "#107C10",
    "N64":      "#B22222",
    "PS3":      "#003087",
    "Xbox360":  "#52B043",
    "WiiU":     "#009AC7",
    "Switch":   "#E4000F",
}

# ─── Utility helpers ──────────────────────────────────────────────────────────

def make_executable(path: Path):
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

def shell_quote(value: str) -> str:
    return "'" + str(value).replace("'", "'\"'\"'") + "'"

def sanitize_name(name: str, fallback="Game") -> str:
    name = re.sub(r"[^\w\s().,\-:&+'!\[\]]", "", str(name).strip())
    name = re.sub(r"\s+", " ", name)
    return name or fallback

def slugify(name: str, fallback="game") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(name).lower())
    return re.sub(r"-+", "-", slug).strip("-") or fallback

def stable_app_id(platform: str, app_name: str, rom_path: Path) -> str:
    prefix = PLATFORMS[platform]["app_id_prefix"]
    digest = hashlib.sha1(str(rom_path).encode("utf-8", errors="ignore")).hexdigest()[:8]
    return f"{prefix}-{slugify(app_name)}-{digest}"

def filesize(path: Path) -> int:
    try:
        return Path(path).stat().st_size
    except Exception:
        return 0

def human_bytes(n) -> str:
    try:
        n = float(n)
    except Exception:
        return str(n)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024

def free_bytes(path: Path) -> int:
    try:
        return shutil.disk_usage(str(path)).free
    except Exception:
        return 0

def md5sum(path: Path) -> str:
    h = hashlib.md5()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def copy_with_progress(src: Path, dst: Path, logger=None, stop_check=None):
    src, dst = Path(src), Path(dst)
    total = filesize(src)
    copied = 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("rb") as fsrc, dst.open("wb") as fdst:
        while True:
            if stop_check and stop_check():
                dst.unlink(missing_ok=True)
                raise RuntimeError("Cancelled by user")
            chunk = fsrc.read(64 * 1024 * 1024)
            if not chunk:
                break
            fdst.write(chunk)
            copied += len(chunk)
            if logger and total:
                logger(f"  Copying {src.name}: {human_bytes(copied)} / {human_bytes(total)} ({copied*100//total}%)")
    try:
        shutil.copystat(src, dst)
    except Exception:
        pass

def _dir_size(path: Path) -> int:
    """Total size of all files under a directory."""
    total = 0
    for p in Path(path).rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except Exception:
                pass
    return total

def _check_disk_space(dest_dir: Path, needed: int, logger=None):
    """Raise if there isn't enough free space (plus 15% headroom) at dest_dir."""
    free = free_bytes(dest_dir)
    required = int(needed * 1.15)
    if free < required:
        raise RuntimeError(
            f"Not enough disk space: need ~{human_bytes(required)}, "
            f"only {human_bytes(free)} free at {dest_dir}"
        )

def copy_tree_with_progress(src: Path, dst: Path, logger=None, stop_check=None):
    """Recursively copy a directory tree, preserving structure, with progress."""
    src, dst = Path(src), Path(dst)
    all_files = [p for p in src.rglob("*") if p.is_file()]
    grand_total = sum((f.stat().st_size for f in all_files if f.exists()), 0)
    done = 0
    dst.mkdir(parents=True, exist_ok=True)
    for f in all_files:
        if stop_check and stop_check():
            raise RuntimeError("Cancelled by user")
        rel = f.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        size = f.stat().st_size if f.exists() else 0
        with f.open("rb") as fsrc, target.open("wb") as fdst:
            while True:
                if stop_check and stop_check():
                    target.unlink(missing_ok=True)
                    raise RuntimeError("Cancelled by user")
                chunk = fsrc.read(32 * 1024 * 1024)
                if not chunk:
                    break
                fdst.write(chunk)
                done += len(chunk)
        try:
            shutil.copystat(f, target)
        except Exception:
            pass
        if logger and grand_total:
            pct = done * 100 // grand_total
            logger(f"  Injecting: {human_bytes(done)} / {human_bytes(grand_total)} ({pct}%) — {rel}")

# ─── Serial / title detection helpers ────────────────────────────────────────

def _ps_serial_from_text(text: str) -> str | None:
    text = str(text).upper()
    prefixes = (
        "SCUS|SLUS|SLES|SCES|SLPS|SLPM|SLKA|PBPX|PAPX|PCPX|SCPS|SCAJ|"
        "TCPS|PUPX|ESPM|PDPX|PCPD|NPUD|NPEF|NPUJ|NPUA|NPEE|SCKA|SLAJ|"
        "SCED|SLED|SIPS|ALCH|CPCS|GUST|PBGP|SCCS|SCPM|SCPN|SCZS"
    )
    patterns = [
        rf"\b({prefixes})[_\-. ]?(\d{{3}})[_\-. ]?(\d{{2}})\b",
        rf"\b({prefixes})[_\-. ]?(\d{{5}})\b",
        rf"BOOT2?\s*=\s*CDROM0:\\\s*({prefixes})[_\-. ]?(\d{{3}})[_\-. ]?(\d{{2}})",
        rf"BOOT2?\s*=\s*CDROM0:\\\s*({prefixes})[_\-. ]?(\d{{5}})",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if not m:
            continue
        if len(m.groups()) >= 3 and m.group(3).isdigit():
            raw = f"{m.group(1)}-{m.group(2)}{m.group(3)}"
        else:
            raw = f"{m.group(1)}-{m.group(2)}"
        return _normalize_ps_serial(raw)
    return None

def _normalize_ps_serial(serial: str) -> str | None:
    if not serial:
        return None
    serial = serial.upper().strip().replace("_", "-").replace(".", "-").replace(" ", "-")
    serial = re.sub(r"-+", "-", serial)
    m = re.search(r"\b([A-Z0-9]{3,5})-(\d{3})-?(\d{2})\b", serial)
    if m:
        return f"{m.group(1)}-{m.group(2)}{m.group(3)}"
    m = re.search(r"\b([A-Z0-9]{3,5})-(\d{5})\b", serial)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return serial

def _ps_serial_variants(serial: str) -> list[str]:
    serial = _normalize_ps_serial(serial)
    if not serial:
        return []
    compact = serial.replace("-", "")
    variants = [serial, compact, serial.lower(), compact.lower()]
    m = re.match(r"^([A-Z0-9]{3,5})-(\d{3})(\d{2})$", serial)
    if m:
        p, a, b = m.groups()
        variants += [f"{p}_{a}.{b}", f"{p}_{a}{b}", f"{p}.{a}.{b}", f"{p}-{a}.{b}", f"{p}-{a}-{b}", f"{p} {a}.{b}"]
    out = []
    for item in variants:
        for c in (item, item.upper(), item.lower()):
            if c and c not in out:
                out.append(c)
    return out

def _serial_key(serial: str) -> str | None:
    serial = _normalize_ps_serial(serial)
    return re.sub(r"[^A-Z0-9]", "", serial.upper()) if serial else None

def detect_serial(platform: str, path: Path) -> str | None:
    """Detect game serial from file, platform-aware."""
    path = Path(path)
    if platform in ("PS1", "PS2"):
        serial = _ps_serial_from_text(path.name)
        if serial:
            return serial
        try:
            size = path.stat().st_size
            read_size = min(size, 192_000_000)
            with path.open("rb") as f:
                head = f.read(read_size)
            serial = _ps_serial_from_text(head.decode("latin-1", errors="ignore"))
            if serial:
                return serial
            if size > read_size:
                with path.open("rb") as f:
                    f.seek(max(0, size - 96_000_000))
                    tail = f.read(96_000_000)
                return _ps_serial_from_text(tail.decode("latin-1", errors="ignore"))
        except Exception:
            return None
        return None
    elif platform == "PSP":
        # PSP serial looks like ULUS-10001
        m = re.search(r"\b([A-Z]{4}-\d{5})\b", path.name.upper())
        if m:
            return m.group(1)
        try:
            size = path.stat().st_size
            with path.open("rb") as f:
                head = f.read(min(size, 16_000_000))
            m = re.search(rb"([A-Z]{4}-\d{5})", head)
            if m:
                return m.group(1).decode("ascii")
        except Exception:
            pass
        return None
    elif platform == "GameCube":
        try:
            with path.open("rb") as f:
                header = f.read(8)
            if len(header) >= 6:
                raw = header[:6].decode("ascii", errors="ignore").strip()
                if re.fullmatch(r"[A-Z0-9]{4,6}", raw.upper()):
                    return raw.upper()
        except Exception:
            pass
        return None
    elif platform == "Xbox":
        try:
            with path.open("rb") as f:
                head = f.read(0x200)
            if len(head) >= 0x120 and head[:4] == b"XBEH":
                base = int.from_bytes(head[0x104:0x108], "little")
                cert_addr = int.from_bytes(head[0x118:0x11C], "little")
                cert_off = cert_addr - base
                if 0 < cert_off < 64 * 1024 * 1024:
                    with path.open("rb") as f:
                        f.seek(cert_off)
                        cert = f.read(0xA0)
                    title_id = int.from_bytes(cert[0x08:0x0C], "little")
                    if title_id:
                        return f"{title_id:08X}"
        except Exception:
            pass
        return None
    elif platform == "PS3":
        # PS3 serial format: BCUS-98174, BCES-00001, BLUS-30000, etc.
        PS3_PREFIXES = (
            "BCAS|BCJB|BCJS|BCES|BCKS|BCUS|BLAS|BLJM|BLJS|BLKS|BLES|BLUS|"
            "NPHB|NPJA|NPEA|NPUA|NPUB|NPJB|NPHB|NPJJ|NPUG|NPEG"
        )
        pat = rf"\b({PS3_PREFIXES})[-_]?(\d{{5}})\b"
        # Try folder/file name first (e.g. "BLES00461 - Skate 2")
        m = re.search(pat, path.name.upper())
        if m:
            return f"{m.group(1)}-{m.group(2)}"
        # PS3 extracted ISO folder — read serial from PARAM.SFO
        if path.is_dir() and (path / "PS3_GAME").exists():
            sfo = path / "PS3_GAME" / "PARAM.SFO"
            if sfo.is_file():
                try:
                    data = sfo.read_bytes()
                    m = re.search(pat.encode(), data.upper())
                    if m:
                        s = m.group(0).decode("ascii").replace("_", "-")
                        m2 = re.match(rf"({PS3_PREFIXES})(\d{{5}})", s.replace("-", ""))
                        if m2:
                            return f"{m2.group(1)}-{m2.group(2)}"
                        return s
                except Exception:
                    pass
            return None
        # For .pkg files, content ID is at offset 0x30
        if path.suffix.lower() == ".pkg":
            try:
                with path.open("rb") as f:
                    head = f.read(0x80)
                if len(head) >= 0x60 and head[:4] == b"\x7fPKG":
                    content_id = head[0x30:0x60].decode("ascii", errors="ignore")
                    m = re.search(pat, content_id.upper())
                    if m:
                        return f"{m.group(1)}-{m.group(2)}"
            except Exception:
                pass
        # Scan first few MB of ISO for embedded serial
        if path.is_file():
            try:
                size = path.stat().st_size
                with path.open("rb") as f:
                    chunk = f.read(min(size, 8_000_000))
                m = re.search(pat.encode(), chunk.upper())
                if m:
                    s = m.group(0).decode("ascii").replace("_", "-")
                    # Ensure dash separator
                    m2 = re.match(rf"({PS3_PREFIXES})(\d{{5}})", s.replace("-", ""))
                    if m2:
                        return f"{m2.group(1)}-{m2.group(2)}"
                    return s
            except Exception:
                pass
        return None
    elif platform == "Xbox360":
        # Try XEX2 executable header for TitleID
        if path.suffix.lower() == ".xex":
            try:
                with path.open("rb") as f:
                    head = f.read(0x200)
                if len(head) >= 0x18 and head[:4] == b"XEX2":
                    # Walk optional headers looking for execution ID (key 0x00040006)
                    opt_count = int.from_bytes(head[0x14:0x18], "big")
                    opt_off = 0x18
                    for _ in range(min(opt_count, 32)):
                        if opt_off + 8 > len(head):
                            break
                        key = int.from_bytes(head[opt_off:opt_off+4], "big")
                        val = int.from_bytes(head[opt_off+4:opt_off+8], "big")
                        if key == 0x00040006:  # Execution ID
                            with path.open("rb") as f:
                                f.seek(val)
                                exec_id = f.read(0x18)
                            if len(exec_id) >= 8:
                                title_id = int.from_bytes(exec_id[4:8], "big")
                                if title_id:
                                    return f"{title_id:08X}"
                            break
                        opt_off += 8
            except Exception:
                pass
        # Scan ISO for XEX2 magic and nearby title ID
        try:
            size = path.stat().st_size
            with path.open("rb") as f:
                chunk = f.read(min(size, 4_000_000))
            pos = chunk.find(b"XEX2")
            if pos != -1 and pos + 0x20 <= len(chunk):
                opt_count = int.from_bytes(chunk[pos+0x14:pos+0x18], "big")
                opt_off = pos + 0x18
                for _ in range(min(opt_count, 32)):
                    if opt_off + 8 > len(chunk):
                        break
                    key = int.from_bytes(chunk[opt_off:opt_off+4], "big")
                    val = int.from_bytes(chunk[opt_off+4:opt_off+8], "big")
                    if key == 0x00040006 and val + 0x18 <= len(chunk):
                        title_id = int.from_bytes(chunk[val+4:val+8], "big")
                        if title_id:
                            return f"{title_id:08X}"
                        break
                    opt_off += 8
        except Exception:
            pass
        return None
    elif platform == "WiiU":
        # Try extracting 16-hex-digit TitleID from filename
        m = re.search(r"\b([0-9A-Fa-f]{16})\b", path.name)
        if m:
            return m.group(1).upper()
        # Try reading WUX/WUD header
        try:
            with path.open("rb") as f:
                head = f.read(0x200)
            # WUX magic
            if head[:4] == b"WUX0":
                tid = head[0x10:0x18]
                tid_int = int.from_bytes(tid, "big")
                if tid_int:
                    return f"{tid_int:016X}"
        except Exception:
            pass
        return None
    elif platform == "Switch":
        # Try extracting Switch TitleID (starts with 0100) from filename
        m = re.search(r"\b(01[0-9A-Fa-f]{14})\b", path.name)
        if m:
            return m.group(1).upper()
        # Try NSP/XCI header
        try:
            with path.open("rb") as f:
                head = f.read(0x200)
            # NCA magic or PFS0 header
            if head[:4] == b"PFS0":
                # Try to find title ID in first 512 bytes
                for i in range(0, min(len(head) - 8, 0x100), 4):
                    val = int.from_bytes(head[i:i+8], "little")
                    if 0x0100000000000000 <= val <= 0x01FFFFFFFFFFFFFF:
                        return f"{val:016X}"
        except Exception:
            pass
        return None

def detect_internal_title(platform: str, path: Path) -> str | None:
    """Extract internal game title from binary for platforms that support it."""
    path = Path(path)
    if platform == "Xbox":
        try:
            with path.open("rb") as f:
                head = f.read(0x200)
            if len(head) >= 0x120 and head[:4] == b"XBEH":
                base = int.from_bytes(head[0x104:0x108], "little")
                cert_addr = int.from_bytes(head[0x118:0x11C], "little")
                cert_off = cert_addr - base
                if 0 < cert_off < 64 * 1024 * 1024:
                    with path.open("rb") as f:
                        f.seek(cert_off)
                        cert = f.read(0xA0)
                    raw = cert[0x0C:0x0C + 80]
                    title = raw.decode("utf-16le", errors="ignore").split("\0", 1)[0]
                    return re.sub(r"\s+", " ", title).strip() or None
        except Exception:
            pass
    elif platform == "GameCube":
        try:
            with path.open("rb") as f:
                f.seek(0x20)
                raw = f.read(64)
            title = raw.decode("ascii", errors="ignore").split("\0", 1)[0].strip()
            return title or None
        except Exception:
            pass
    elif platform == "PS3":
        # Try Store ID lookup first
        store_id = detect_ps3_store_id(path)
        if store_id:
            title = lookup_ps3_store_id(store_id)
            if title:
                return title
        # PS3 extracted ISO folder — read TITLE from PARAM.SFO
        if path.is_dir() and (path / "PS3_GAME").exists():
            sfo = path / "PS3_GAME" / "PARAM.SFO"
            if sfo.is_file():
                try:
                    title = _read_sfo_title(sfo)
                    if title:
                        return title
                except Exception:
                    pass
        return None
    elif platform == "WiiU":
        # Wii U game folder — read TITLE from meta/meta.xml or PARAM.SFO
        if path.is_dir():
            # Try meta.xml first (Wii U standard location)
            meta_xml = path / "meta" / "meta.xml"
            if meta_xml.is_file():
                try:
                    title = _read_wiiu_meta_title(meta_xml)
                    if title:
                        return title
                except Exception:
                    pass
            # Try PARAM.SFO as fallback
            sfo = path / "meta" / "PARAM.SFO"
            if sfo.is_file():
                try:
                    title = _read_sfo_title(sfo)
                    if title:
                        return title
                except Exception:
                    pass
        return None

def _read_sfo_title(sfo_path: Path) -> str | None:
    """Parse a PS3 PARAM.SFO file and return the TITLE field."""
    try:
        data = Path(sfo_path).read_bytes()
        if data[:4] != b"\x00PSF":
            return None
        key_table_start = int.from_bytes(data[0x08:0x0C], "little")
        data_table_start = int.from_bytes(data[0x0C:0x10], "little")
        num_entries = int.from_bytes(data[0x10:0x14], "little")
        for i in range(num_entries):
            entry = 0x14 + i * 0x10
            key_off = int.from_bytes(data[entry:entry + 2], "little")
            data_len = int.from_bytes(data[entry + 4:entry + 8], "little")
            data_off = int.from_bytes(data[entry + 0x0C:entry + 0x10], "little")
            key_start = key_table_start + key_off
            key_end = data.index(b"\x00", key_start)
            key = data[key_start:key_end].decode("ascii", errors="ignore")
            if key == "TITLE":
                val_start = data_table_start + data_off
                val = data[val_start:val_start + data_len]
                title = val.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
                return re.sub(r"\s+", " ", title).strip() or None
    except Exception:
        pass
    return None

def _read_wiiu_meta_title(meta_xml_path: Path) -> str | None:
    """Parse a Wii U meta.xml file and return the game title."""
    try:
        root = ET.parse(meta_xml_path).getroot()
        # Wii U meta.xml structure: <menu><arg><dt attr="Title">GameTitle</dt></arg></menu>
        for elem in root.iter():
            if elem.tag.endswith("dt") and elem.get("attr") == "Title":
                title = (elem.text or "").strip()
                return re.sub(r"\s+", " ", title).strip() or None
    except Exception:
        pass
    return None

# ─── ROM file collection (CUE + BIN bundling) ────────────────────────────────

def _find_wiiu_rpx(game_folder: Path) -> Path | None:
    """Find the main .rpx executable in a Wii U game folder."""
    code_dir = game_folder / "code"
    if not code_dir.exists():
        return None
    # Look for .rpx files, prefer "app.rpx" or variants
    rpx_files = sorted(code_dir.glob("*.rpx"))
    if rpx_files:
        # Prefer app.rpx or app_variant.rpx
        for rpx in rpx_files:
            if rpx.name.startswith("app"):
                return rpx
        # Return first .rpx found if no app.rpx
        return rpx_files[0]
    return None

def collect_rom(platform: str, rom: Path) -> dict:
    """Return {"launch": Path, "bundle_files": [Path, ...]}"""
    rom = Path(rom)
    data_exts = PLATFORMS[platform]["data_exts"]

    # PS3 extracted ISO folders (containing PS3_GAME subdirectory)
    if platform == "PS3" and rom.is_dir() and (rom / "PS3_GAME").exists():
        # Return the folder itself as the launch path
        return {"launch": rom, "bundle_files": [rom]}

    # Wii U game folders (containing code/ and/or meta/ subdirectories)
    if platform == "WiiU" and rom.is_dir() and ((rom / "code").exists() or (rom / "meta").exists()):
        # Return the folder itself as the launch path
        return {"launch": rom, "bundle_files": [rom]}

    if rom.suffix.lower() == ".cue":
        bundle = [rom]
        try:
            text = rom.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            text = rom.read_text(encoding="latin-1", errors="ignore")
        for m in re.finditer(r'FILE\s+"([^"]+)"', text, re.IGNORECASE):
            ref = rom.parent / m.group(1)
            if ref.is_file() and ref.suffix.lower() in data_exts:
                bundle.append(ref)
        return {"launch": rom, "bundle_files": bundle}

    return {"launch": rom, "bundle_files": [rom]}

# ─── Title DB & Cover ─────────────────────────────────────────────────────────

_title_db_cache: dict[str, dict] = {}

def load_title_db(platform: str, force=False) -> dict:
    urls = PLATFORMS[platform]["title_db_urls"]
    if not urls:
        return {}
    cache_key = platform
    if not force and cache_key in _title_db_cache:
        return _title_db_cache[cache_key]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{platform}.titles.json"
    if force or not cache_file.exists():
        for url in urls:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Rom2App"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
                cache_file.write_bytes(data)
                break
            except Exception:
                continue
    if not cache_file.exists():
        return {}
    raw = json.loads(cache_file.read_text(errors="ignore"))
    db = {}
    for k, v in raw.items():
        serial = _normalize_ps_serial(k) or k
        if isinstance(v, list):
            db[serial] = v[0] if v else ""
        elif isinstance(v, dict):
            db[serial] = v.get("title") or v.get("name") or ""
        else:
            db[serial] = str(v)
    _title_db_cache[cache_key] = db
    return db

def lookup_title(platform: str, serial: str) -> str | None:
    serial = _normalize_ps_serial(serial) or serial
    if not serial:
        return None
    try:
        db = load_title_db(platform)
        return db.get(serial) or None
    except Exception:
        return None

def lookup_ps3_store_id(store_id: str) -> str | None:
    """Lookup PS3 game title by PlayStation Store ID (e.g., NPUA80316)."""
    if not store_id:
        return None
    store_id = store_id.strip().upper()
    return PS3_STORE_IDS.get(store_id) or None

def detect_ps3_store_id(path: Path) -> str | None:
    """Detect PS3 Store ID from file path or folder name."""
    path = Path(path)
    # Pattern for Store IDs: NP[A-Z][A-Z]\d{5}
    m = re.search(r"(NP[A-Z]{2}\d{5})", path.name.upper())
    if m:
        return m.group(1)
    # Check PARAM.SFO for Store ID if it's a PS3 game folder
    if path.is_dir() and (path / "PS3_GAME").exists():
        try:
            sfo = path / "PS3_GAME" / "PARAM.SFO"
            if sfo.is_file():
                data = sfo.read_bytes()
                m = re.search(rb"(NP[A-Z]{2}\d{5})", data.upper())
                if m:
                    return m.group(1).decode("ascii")
        except Exception:
            pass
    return None

def redump_lookup(dat_path: Path, rom_md5: str) -> dict | None:
    try:
        root = ET.parse(dat_path).getroot()
        for game in root.iter("game"):
            for rom in game.iter("rom"):
                if rom.attrib.get("md5", "").lower() == rom_md5.lower():
                    text = " ".join([game.attrib.get("name", ""), rom.attrib.get("serial", "")])
                    return {"game": game.attrib.get("name", ""), "serial": _ps_serial_from_text(text)}
    except Exception:
        pass
    return None

def _download_url(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Rom2App"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
        if len(data) < 1000:
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return True
    except Exception:
        return False

def download_cover(platform: str, serial: str | None, title: str | None, dest: Path) -> str | None:
    """Try to download cover art. Returns the URL that worked, or None."""
    from PIL import Image
    templates = PLATFORMS[platform]["cover_urls"]
    mode = PLATFORMS[platform]["cover_mode"]
    tmp = dest.with_suffix(".tmp.download")

    candidates = []
    if mode == "serial" and serial:
        variants = _ps_serial_variants(serial)
        for tmpl in templates:
            for v in variants:
                candidates.append(tmpl.format(serial=v, title=title or ""))
    elif mode == "title" and title:
        # Sanitize for URL
        safe_title = re.sub(r"[^\w\s\-()&]", "", title).strip()
        for tmpl in templates:
            candidates.append(tmpl.format(title=safe_title, serial=serial or ""))
    # Also try SteamGridDB as fallback
    if title:
        candidates.append(f"_steamgriddb:{title}")

    for url in candidates:
        if url.startswith("_steamgriddb:"):
            query = url[len("_steamgriddb:"):]
            used = _try_steamgriddb(query, tmp)
            if used:
                try:
                    with Image.open(tmp) as img:
                        img.convert("RGBA").save(dest, "PNG")
                    tmp.unlink(missing_ok=True)
                    return used
                except Exception:
                    tmp.unlink(missing_ok=True)
            continue
        if _download_url(url, tmp):
            try:
                with Image.open(tmp) as img:
                    img.convert("RGBA").save(dest, "PNG")
                tmp.unlink(missing_ok=True)
                return url
            except Exception:
                tmp.unlink(missing_ok=True)
    return None

def _try_steamgriddb(query: str, dest: Path) -> str | None:
    try:
        search_url = f"{STEAMGRIDDB_API_BASE}/search/autocomplete/{urllib.parse.quote(query)}"
        req = urllib.request.Request(search_url, headers={
            "Authorization": f"Bearer {DEFAULT_STEAMGRIDDB_KEY}",
            "User-Agent": "Rom2App",
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        games = data.get("data", [])
        if not games:
            return None
        game_id = games[0]["id"]
        grids_url = f"{STEAMGRIDDB_API_BASE}/grids/game/{game_id}?dimensions=600x900"
        req2 = urllib.request.Request(grids_url, headers={
            "Authorization": f"Bearer {DEFAULT_STEAMGRIDDB_KEY}",
            "User-Agent": "Rom2App",
        })
        with urllib.request.urlopen(req2, timeout=15) as r:
            grids = json.loads(r.read())
        grid_data = grids.get("data", [])
        if not grid_data:
            return None
        img_url = grid_data[0]["url"]
        if _download_url(img_url, dest):
            return img_url
    except Exception:
        pass
    return None

# ─── Icon helpers ─────────────────────────────────────────────────────────────

def create_placeholder_icon(dest: Path, platform: str = ""):
    from PIL import Image, ImageDraw
    color = PLATFORM_COLORS.get(platform, "#444")
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    img = Image.new("RGBA", (512, 512), (r, g, b, 255))
    d = ImageDraw.Draw(img)
    d.rectangle((40, 40, 472, 472), outline=(255, 255, 255, 120), width=10)
    short = {
        "PS1": "PS1", "PS2": "PS2", "PSP": "PSP",
        "GameCube": "GC", "Xbox": "XBX",
        "N64": "N64", "PS3": "PS3", "Xbox360": "X360",
        "WiiU": "WiiU", "Switch": "NSW",
    }.get(platform, "ROM")
    d.text((200, 220), short, fill=(255, 255, 255, 200))
    img.save(dest, "PNG")

def save_icon(source: Path, dest: Path, size: int):
    from PIL import Image
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as img:
        img = img.convert("RGBA")
        img.thumbnail((size, size))
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.alpha_composite(img, ((size - img.width) // 2, (size - img.height) // 2))
        canvas.save(dest, "PNG")

def install_appdir_icons(appdir: Path, app_id: str, source_icon: Path):
    root_icon = appdir / f"{app_id}.png"
    save_icon(source_icon, root_icon, 256)
    dir_icon = appdir / ".DirIcon"
    if dir_icon.exists() or dir_icon.is_symlink():
        dir_icon.unlink()
    shutil.copy2(root_icon, dir_icon)
    for size in ICON_SIZES:
        icon_path = appdir / "usr/share/icons/hicolor" / f"{size}x{size}/apps/{app_id}.png"
        save_icon(source_icon, icon_path, size)
    save_icon(source_icon, appdir / f"usr/share/pixmaps/{app_id}.png", 256)

def install_kde_launcher(appimage_path: Path, app_name: str, app_id: str, source_icon: Path):
    LOCAL_APP_DIR.mkdir(parents=True, exist_ok=True)
    for size in ICON_SIZES:
        save_icon(source_icon, LOCAL_ICON_BASE / f"{size}x{size}/apps/{app_id}.png", size)
    desktop_file = LOCAL_APP_DIR / f"{app_id}.desktop"
    desktop_file.write_text(
        f"[Desktop Entry]\nVersion=1.0\nType=Application\nName={app_name}\n"
        f"Comment={app_name}\nExec={shell_quote(str(appimage_path))} %f\n"
        f"Icon={app_id}\nCategories=Game;Emulator;\nTerminal=false\nStartupNotify=true\n"
    )
    make_executable(desktop_file)
    _run_quiet(["gtk-update-icon-cache", "-f", "-t", str(LOCAL_ICON_BASE)])
    for cmd in ["kbuildsycoca6", "kbuildsycoca5"]:
        _run_quiet([cmd])

def _run_quiet(args):
    """Run a command, ignoring it entirely if the binary isn't installed."""
    try:
        subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (FileNotFoundError, OSError):
        pass

def refresh_desktop_caches():
    for cmd in ["kbuildsycoca6", "kbuildsycoca5"]:
        _run_quiet([cmd])


# ─── AppImage artwork patching helpers ───────────────────────────────────────

def is_appimage_path(path: Path) -> bool:
    return Path(path).suffix.lower() == ".appimage"


def find_appimagetool() -> str:
    tool = shutil.which("appimagetool")
    if not tool:
        raise RuntimeError("appimagetool was not found in PATH. Install appimagetool first, then try Patch AppImage Icon again.")
    return tool

def appimagetool_env_for_rebuild(appimage_path: Path | None = None) -> dict:
    """Return an environment that forces appimagetool to use one architecture.

    Some AppImages extract into an AppDir that contains more than one arch marker.
    appimagetool then fails unless ARCH is explicitly set. This uses the current
    machine architecture, normalized to the names appimagetool expects.
    """
    env = os.environ.copy()
    raw_arch = ""
    try:
        raw_arch = subprocess.check_output(["uname", "-m"], text=True).strip()
    except Exception:
        raw_arch = "x86_64"
    arch_map = {
        "amd64": "x86_64",
        "x64": "x86_64",
        "x86-64": "x86_64",
        "i386": "i686",
        "i486": "i686",
        "i586": "i686",
        "arm64": "aarch64",
        "armv8": "aarch64",
    }
    env["ARCH"] = arch_map.get(raw_arch.lower(), raw_arch or "x86_64")
    return env


def _locate_desktop_file_in_appdir(appdir: Path) -> Path | None:
    for item in Path(appdir).rglob("*.desktop"):
        if item.is_file():
            return item
    return None


def _rewrite_desktop_icon_to_diricon(appdir: Path):
    desktop = _locate_desktop_file_in_appdir(appdir)
    if not desktop:
        return
    try:
        lines = desktop.read_text(encoding="utf-8", errors="ignore").splitlines(True)
        out = []
        changed = False
        for line in lines:
            if line.strip().startswith("Icon="):
                out.append("Icon=.DirIcon\n")
                changed = True
            else:
                out.append(line)
        if not changed:
            out.append("Icon=.DirIcon\n")
        desktop.write_text("".join(out), encoding="utf-8")
    except Exception as e:
        raise RuntimeError(f"Could not rewrite desktop Icon= line: {e}")


def _appimage_icon_targets(appdir: Path) -> list[Path]:
    targets: list[Path] = []
    # Root icon names used by AppImages and launchers.
    for name in [".DirIcon", ".DirIcon.png"]:
        targets.append(appdir / name)
    # Existing common icon locations. Replacing these makes the rebuilt AppImage
    # show the new thumbnail in more file managers and desktop menus.
    for root in [appdir / "usr/share/icons", appdir / "share/icons", appdir / "usr/share/pixmaps", appdir / "share/pixmaps"]:
        if root.exists():
            for item in root.rglob("*"):
                if item.is_file() and item.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".xpm"}:
                    targets.append(item)
    # If no icon-folder images existed, still create a hicolor app icon.
    desktop = _locate_desktop_file_in_appdir(appdir)
    app_id = desktop.stem if desktop else "patched-appimage"
    targets.append(appdir / "usr/share/icons/hicolor/256x256/apps" / f"{app_id}.png")
    # De-dupe while preserving order.
    seen = set()
    clean = []
    for t in targets:
        key = str(t)
        if key not in seen:
            seen.add(key)
            clean.append(t)
    return clean


def _target_icon_size(target: Path) -> int:
    """Pick a sane PNG size for an AppImage icon target so patching does not bloat the rebuilt AppImage."""
    text = str(target).lower()
    m = re.search(r"(\d{2,4})x\1", text)
    if m:
        return max(16, min(1024, int(m.group(1))))
    for size in [1024, 512, 256, 128, 96, 64, 48, 32, 24, 22, 16]:
        if str(size) in text:
            return size
    return 256


def _save_icon_png_for_target(source_image, target: Path):
    """Save artwork as a resized square PNG appropriate for the target icon path."""
    from PIL import Image
    size = _target_icon_size(target)
    img = source_image.convert("RGBA")
    img.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(img, ((size - img.width) // 2, (size - img.height) // 2))
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target, "PNG", optimize=True)


def _safe_patch_temp_parent(appimage_path: Path) -> Path:
    """Use the AppImage folder for extraction/rebuild so /tmp RAM disks do not run out of space."""
    parent = Path(appimage_path).parent
    try:
        test = parent / ".rom2app-write-test"
        test.write_text("ok")
        test.unlink(missing_ok=True)
        return parent
    except Exception:
        return Path(tempfile.gettempdir())


def patch_appimage_artwork(appimage_path: Path, artwork_path: Path, logger=None, create_backup: bool = True) -> list[str]:
    """Extract an AppImage next to itself, replace icon files, rebuild it, and optionally keep a .bak backup."""
    from PIL import Image
    appimage_path = Path(appimage_path)
    artwork_path = Path(artwork_path)
    if not appimage_path.is_file() or not is_appimage_path(appimage_path):
        raise RuntimeError("Patch AppImage Icon requires a .AppImage file target.")
    if not artwork_path.is_file():
        raise RuntimeError("Artwork image does not exist.")
    appimagetool = find_appimagetool()
    temp_parent = _safe_patch_temp_parent(appimage_path)
    app_size = filesize(appimage_path)
    # A rebuild needs room for extraction + rebuilt file; backup needs another full copy.
    estimated_needed = int(app_size * (4.0 if create_backup else 3.0))
    free = free_bytes(temp_parent)
    if free and app_size and free < estimated_needed:
        raise RuntimeError(
            "Not enough free disk space to safely patch this AppImage.\n\n"
            f"Temp/rebuild location: {temp_parent}\n"
            f"AppImage size: {human_bytes(app_size)}\n"
            f"Estimated free space needed: {human_bytes(estimated_needed)}\n"
            f"Free space available: {human_bytes(free)}\n\n"
            "Fixes: move the AppImage to a drive with more free space, free up space, "
            "or enable 'Patch AppImages without creating .bak backup files' in Options and try again."
        )
    if logger:
        logger(f"Patching AppImage artwork: {appimage_path.name}")
        logger(f"  Using temp/rebuild folder: {temp_parent}")
        if not create_backup:
            logger("  Backup disabled for this patch.", "warn")
    with tempfile.TemporaryDirectory(prefix="rom2app-appimage-patch-", dir=str(temp_parent)) as tmp:
        tmpdir = Path(tmp)
        work = tmpdir / "work"
        work.mkdir(parents=True, exist_ok=True)
        make_executable(appimage_path)
        result = subprocess.run(
            [str(appimage_path), "--appimage-extract"],
            cwd=str(work), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError("Failed to extract AppImage.\n\n" + result.stderr[-4000:])
        appdir = work / "squashfs-root"
        if not appdir.exists():
            raise RuntimeError("Extraction finished, but squashfs-root was not found.")
        _rewrite_desktop_icon_to_diricon(appdir)
        replaced = []
        with Image.open(artwork_path) as img:
            for target in _appimage_icon_targets(appdir):
                try:
                    # Keep all replacement bytes as PNG. Extensionless .DirIcon with PNG bytes is valid.
                    _save_icon_png_for_target(img, target)
                    replaced.append(str(target.relative_to(appdir)))
                except Exception as e:
                    if logger:
                        logger(f"  Could not replace {target}: {e}", "warn")
        if not replaced:
            raise RuntimeError("No icon targets could be written inside the AppImage.")
        rebuilt = tmpdir / appimage_path.name
        rebuild_env = appimagetool_env_for_rebuild(appimage_path)
        if logger:
            logger(f"  Running appimagetool with ARCH={rebuild_env.get('ARCH', '')}…")
        result = subprocess.run(
            [appimagetool, str(appdir), str(rebuilt)],
            cwd=str(tmpdir), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300, env=rebuild_env,
        )
        if result.returncode != 0 or not rebuilt.exists():
            raise RuntimeError("appimagetool failed to rebuild the AppImage.\n\nSTDOUT:\n" + result.stdout[-3000:] + "\n\nSTDERR:\n" + result.stderr[-4000:])
        backup = None
        if create_backup:
            backup = appimage_path.with_name(appimage_path.name + ".bak")
            counter = 1
            while backup.exists():
                backup = appimage_path.with_name(appimage_path.name + f".bak.{counter}")
                counter += 1
            shutil.copy2(appimage_path, backup)
        shutil.copy2(rebuilt, appimage_path)
        make_executable(appimage_path)
        if logger:
            if backup:
                logger(f"  Backup saved: {backup}")
            logger(f"  Replaced {len(replaced)} icon target(s) inside the AppImage.")
        return replaced

# ─── AppRun script builder ────────────────────────────────────────────────────

def make_apprun(platform: str, app_id: str, rom_name: str, rom_names: list[str],
                extra_args: str = "", fast_launch: bool = False,
                external_rom_path: str | None = None,
                is_ps3_folder: bool = False,
                is_wiiu_folder: bool = False) -> str:
    stable_dir = PLATFORMS[platform]["stable_dir_name"]

    # For Wii U, we use -f -g for .wux/.wud files, or just -g for .rpx folders.
    if platform == "WiiU" and not is_wiiu_folder:
        launch_flag = "-f -g"
        flag_prefix = launch_flag + " "
    elif is_wiiu_folder:
        launch_flag = ""
        flag_prefix = ""
    else:
        launch_flag = PLATFORMS[platform].get("launch_flag", "")
        flag_prefix = (launch_flag + " ") if launch_flag else ""

    copy_cmds = "\n".join(
        f'if [ ! -f "$STABLE_DIR/{n}" ]; then\n    cp "$SRC_DIR/{n}" "$STABLE_DIR/{n}"\nfi'
        for n in rom_names
    )

    # PS3 extracted ISO folder — EXTERNAL: point RPCS3 at EBOOT.BIN in original folder.
    if is_ps3_folder and external_rom_path:
        target = '--no-gui "$ORIG_ROM/PS3_GAME/USRDIR/EBOOT.BIN"'
        ext_block = f'ORIG_ROM={shell_quote(external_rom_path)}\n'
        ext_block += (
            'if [ ! -d "$ORIG_ROM" ]; then\n'
            '    echo "PS3 game folder not found: $ORIG_ROM" >&2\n'
            '    exit 1\nfi\n'
            'if [ ! -f "$ORIG_ROM/PS3_GAME/USRDIR/EBOOT.BIN" ]; then\n'
            '    echo "EBOOT.BIN not found in: $ORIG_ROM/PS3_GAME/USRDIR/" >&2\n'
            '    exit 1\nfi\n'
        )
        copy_block = ""
    # PS3 extracted ISO folder — INJECTED: game lives inside the AppImage mount.
    elif is_ps3_folder:
        target = '--no-gui "$SRC_DIR/$ROM_NAME/PS3_GAME/USRDIR/EBOOT.BIN"'
        ext_block = (
            'if [ ! -f "$SRC_DIR/$ROM_NAME/PS3_GAME/USRDIR/EBOOT.BIN" ]; then\n'
            '    echo "Injected EBOOT.BIN missing: $SRC_DIR/$ROM_NAME/PS3_GAME/USRDIR/EBOOT.BIN" >&2\n'
            '    exit 1\nfi\n'
        )
        copy_block = ""
    # Wii U game folder — EXTERNAL: point Cemu at the .rpx file.
    elif is_wiiu_folder and external_rom_path:
        target = '-g "$WIIU_RPX_PLACEHOLDER"'
        ext_block = f'ORIG_ROM={shell_quote(external_rom_path)}\n'
        ext_block += (
            'RPX_FILE=$(find "$ORIG_ROM/code" -maxdepth 1 -name "*.rpx" 2>/dev/null | head -1)\n'
            'if [ -z "$RPX_FILE" ]; then\n'
            '    echo "No .rpx file found in: $ORIG_ROM/code/" >&2\n'
            '    exit 1\nfi\n'
            'WIIU_RPX_PLACEHOLDER="$RPX_FILE"\n'
        )
        copy_block = ""
    # Wii U game folder — INJECTED: point to .rpx file inside the AppImage mount.
    elif is_wiiu_folder:
        target = '-g "$WIIU_RPX_PLACEHOLDER"'
        ext_block = (
            'RPX_FILE=$(find "$SRC_DIR/$ROM_NAME/code" -maxdepth 1 -name "*.rpx" 2>/dev/null | head -1)\n'
            'if [ -z "$RPX_FILE" ]; then\n'
            '    echo "No .rpx file found in injected game: $SRC_DIR/$ROM_NAME/code/" >&2\n'
            '    exit 1\nfi\n'
            'WIIU_RPX_PLACEHOLDER="$RPX_FILE"\n'
        )
        copy_block = ""
    elif external_rom_path:
        target = '"$ORIG_ROM"'
        ext_block = f'ORIG_ROM={shell_quote(external_rom_path)}\n'
        ext_block += (
            'if [ ! -f "$ORIG_ROM" ]; then\n'
            '    echo "ROM not found: $ORIG_ROM" >&2\n'
            '    exit 1\nfi\n'
        )
        copy_block = ""
    elif fast_launch:
        target = '"$SRC_DIR/$ROM_NAME"'
        ext_block = ""
        copy_block = ""
    else:
        target = '"$STABLE_DIR/$ROM_NAME"'
        ext_block = ""
        copy_block = copy_cmds

    if fast_launch:
        # Fast launch now truly runs the embedded emulator directly from the
        # mounted AppImage. It does not copy emulator.AppImage to
        # ~/.local/share. Any older per-game stable folder for this AppImage is
        # removed on launch, so stale folders also disappear after crashes.
        return f"""#!/bin/sh
set -eu
APP_ID={shell_quote(app_id)}
ROM_NAME={shell_quote(rom_name)}
EXTRA_ARGS={shell_quote(extra_args)}
HERE="$(dirname "$(readlink -f "$0")")"
SRC_DIR="$HERE/usr/share/$APP_ID"
LEGACY_STABLE_DIR="$HOME/.local/share/{stable_dir}/$APP_ID"

# Clean up the old Rom2App runtime folder for this game, if an older build made it.
if [ -n "$APP_ID" ] && [ -d "$LEGACY_STABLE_DIR" ]; then
    rm -rf "$LEGACY_STABLE_DIR" 2>/dev/null || true
fi

RUN_DIR="${{TMPDIR:-/tmp}}/rom2app-${{APP_ID}}-$$"
rm -rf "$RUN_DIR" 2>/dev/null || true
mkdir -p "$RUN_DIR"
cleanup() {{
    if [ -n "${{RUN_DIR:-}}" ] && [ -d "$RUN_DIR" ]; then
        rm -rf "$RUN_DIR" 2>/dev/null || true
    fi
}}
trap cleanup EXIT INT TERM HUP

{ext_block}
cd "$RUN_DIR"
export APPIMAGE_SILENT_INSTALL=1
export APPIMAGELAUNCHER_DISABLE=1
export XDG_DATA_HOME="$HOME/.local/share"
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_CACHE_HOME="$HOME/.cache"
"$SRC_DIR/emulator.AppImage" {flag_prefix}{target} $EXTRA_ARGS
ROM2APP_STATUS=$?
cleanup
exit "$ROM2APP_STATUS"
"""

    return f"""#!/bin/sh
set -eu
APP_ID={shell_quote(app_id)}
ROM_NAME={shell_quote(rom_name)}
EXTRA_ARGS={shell_quote(extra_args)}
HERE="$(dirname "$(readlink -f "$0")")"
SRC_DIR="$HERE/usr/share/$APP_ID"
STABLE_DIR="$HOME/.local/share/{stable_dir}/$APP_ID"
mkdir -p "$STABLE_DIR"
if [ ! -f "$STABLE_DIR/emulator.AppImage" ]; then
    cp "$SRC_DIR/emulator.AppImage" "$STABLE_DIR/emulator.AppImage"
    chmod +x "$STABLE_DIR/emulator.AppImage"
fi
{ext_block}{copy_block}
cd "$STABLE_DIR"
export APPIMAGE_SILENT_INSTALL=1
export APPIMAGELAUNCHER_DISABLE=1
export XDG_DATA_HOME="$HOME/.local/share"
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_CACHE_HOME="$HOME/.cache"
exec "$STABLE_DIR/emulator.AppImage" {flag_prefix}{target} $EXTRA_ARGS
"""


# ─── Existing AppImage patcher ────────────────────────────────────────────────

def _patch_apprun_for_fast_mount(apprun_text: str) -> tuple[str, bool]:
    """Patch an existing Rom2App AppRun so it runs emulator.AppImage from the
    AppImage mount instead of copying it into ~/.local/share first.

    This version also re-patches AppRuns made by the older broken patcher that
    could fail with: RUN_DIR: parameter not set.
    """
    if 'SRC_DIR="$HERE/usr/share/$APP_ID"' not in apprun_text or 'emulator.AppImage' not in apprun_text:
        raise RuntimeError("This does not look like a Rom2App AppRun.")

    original = apprun_text
    text = apprun_text

    stable_match = re.search(r'^(?:STABLE_DIR|LEGACY_STABLE_DIR)="\$HOME/\.local/share/([^"]+)/\$APP_ID"\n', text, re.MULTILINE)
    stable_rel = stable_match.group(1) if stable_match else ""

    # Remove any old/broken patch block first, then insert a known-good one.
    text = re.sub(
        r'\n?# Clean up the old Rom2App runtime folder.*?\n(?:exec |"\$SRC_DIR/emulator\.AppImage")',
        '\n@@ROM2APP_EXEC_MARKER@@',
        text,
        flags=re.DOTALL,
        count=1,
    )

    # Convert STABLE_DIR to LEGACY_STABLE_DIR, or add it if missing.
    text = re.sub(r'^STABLE_DIR="\$HOME/\.local/share/[^"]+/\$APP_ID"\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^LEGACY_STABLE_DIR="\$HOME/\.local/share/[^"]+/\$APP_ID"\n', '', text, flags=re.MULTILINE)
    insert_after = 'SRC_DIR="$HERE/usr/share/$APP_ID"\n'
    legacy_line = f'LEGACY_STABLE_DIR="$HOME/.local/share/{stable_rel}/$APP_ID"\n' if stable_rel else 'LEGACY_STABLE_DIR=""\n'
    if insert_after in text:
        text = text.replace(insert_after, insert_after + legacy_line, 1)

    # Remove old copy-to-stable commands for emulator and bundled ROM files.
    text = re.sub(
        r'mkdir -p "\$STABLE_DIR"\n'
        r'if \[ ! -f "\$STABLE_DIR/emulator\.AppImage" \]; then\n'
        r'    cp "\$SRC_DIR/emulator\.AppImage" "\$STABLE_DIR/emulator\.AppImage"\n'
        r'    chmod \+x "\$STABLE_DIR/emulator\.AppImage"\n'
        r'fi\n',
        '', text, count=1)
    text = re.sub(
        r'if \[ ! -f "\$STABLE_DIR/[^"]+" \]; then\n'
        r'    cp "\$SRC_DIR/[^"]+" "\$STABLE_DIR/[^"]+"\n'
        r'fi\n',
        '', text)

    text = text.replace('cd "$STABLE_DIR"\n', '')
    text = text.replace('cd "$RUN_DIR"\n', '')
    text = text.replace('"$STABLE_DIR/emulator.AppImage"', '"$SRC_DIR/emulator.AppImage"')
    text = text.replace('"$STABLE_DIR/$ROM_NAME"', '"$SRC_DIR/$ROM_NAME"')
    text = re.sub(r'"\$STABLE_DIR/([^"]+)"', r'"$SRC_DIR/\1"', text)

    cleanup_block = """# Clean up the old Rom2App runtime folder for this game, if an older build made it.
if [ -n "${LEGACY_STABLE_DIR:-}" ] && [ -d "$LEGACY_STABLE_DIR" ]; then
    rm -rf "$LEGACY_STABLE_DIR" 2>/dev/null || true
fi

RUN_DIR="${TMPDIR:-/tmp}/rom2app-${APP_ID}-$$"
rm -rf "$RUN_DIR" 2>/dev/null || true
mkdir -p "$RUN_DIR"
cleanup() {
    if [ -n "${RUN_DIR:-}" ] && [ -d "$RUN_DIR" ]; then
        rm -rf "$RUN_DIR" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM HUP
cd "$RUN_DIR"
"""

    marker = 'export APPIMAGE_SILENT_INSTALL=1\n'
    if marker not in text:
        raise RuntimeError("Could not find Rom2App launch environment block.")
    text = text.replace(marker, cleanup_block + marker, 1)

    # Replace exec with a normal child process so the EXIT trap runs after the emulator closes.
    text = text.replace('@@ROM2APP_EXEC_MARKER@@', '"$SRC_DIR/emulator.AppImage"', 1)
    text = text.replace('exec "$SRC_DIR/emulator.AppImage"', '"$SRC_DIR/emulator.AppImage"')

    # Ensure the script exits with the emulator's status after cleanup.
    if 'ROM2APP_STATUS=$?' not in text:
        text = text.rstrip() + '\nROM2APP_STATUS=$?\ncleanup\nexit "$ROM2APP_STATUS"\n'

    return text, text != original

def patch_existing_appimage(appimage_path: Path, logger=None, stop_check=None, create_backup: bool = True) -> bool:
    """Extract, patch AppRun, and rebuild one existing Rom2App AppImage in place."""
    def log(msg):
        if logger:
            logger(msg)

    appimage_path = Path(appimage_path)
    if not appimage_path.is_file():
        raise RuntimeError(f"Not a file: {appimage_path}")
    if appimage_path.suffix.lower() != ".appimage":
        raise RuntimeError(f"Not an AppImage: {appimage_path.name}")

    appimagetool = shutil.which("appimagetool")
    if not appimagetool:
        raise RuntimeError("appimagetool is not installed or not in PATH.")

    log(f"▸ Patching: {appimage_path.name}")
    work_parent = appimage_path.parent / ".rom2app-patch-work"
    work_parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="patch-", dir=str(work_parent)) as tmpdir:
        tmp = Path(tmpdir)
        extractor = tmp / appimage_path.name
        shutil.copy2(appimage_path, extractor)
        make_executable(extractor)

        proc = subprocess.run([str(extractor), "--appimage-extract"], cwd=str(tmp), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if proc.returncode != 0:
            raise RuntimeError("Could not extract AppImage. It may be unsupported or corrupted.")
        if stop_check and stop_check():
            raise RuntimeError("Cancelled")

        appdir = tmp / "squashfs-root"
        apprun = appdir / "AppRun"
        if not apprun.is_file():
            raise RuntimeError("Extracted AppImage has no AppRun.")

        old = apprun.read_text(errors="ignore")
        new, changed = _patch_apprun_for_fast_mount(old)
        if not changed:
            log("  Already patched — skipped.")
            return False
        apprun.write_text(new)
        make_executable(apprun)

        if create_backup:
            backup = appimage_path.with_suffix(appimage_path.suffix + ".bak")
            n = 2
            while backup.exists():
                backup = appimage_path.with_name(appimage_path.name + f".bak{n}")
                n += 1
            shutil.copy2(appimage_path, backup)
            log(f"  Backup: {backup.name}")
        else:
            log("  Backup disabled — patching without .bak file.")

        out_tmp = tmp / appimage_path.name
        env = appimagetool_env_for_rebuild(appimage_path)
        proc = subprocess.Popen([appimagetool, str(appdir), str(out_tmp)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        while True:
            if stop_check and stop_check():
                proc.terminate()
                proc.wait()
                raise RuntimeError("Cancelled")
            line = proc.stdout.readline() if proc.stdout else ""
            if line:
                log(f"  {line.rstrip()}")
            elif proc.poll() is not None:
                break
        if proc.wait() != 0:
            raise RuntimeError(f"appimagetool failed (code {proc.returncode})")

        shutil.copy2(out_tmp, appimage_path)
        make_executable(appimage_path)
        log("  ✓ Patched in place.")
        return True

# ─── Core build function ──────────────────────────────────────────────────────

def build_appimage(
    platform: str,
    rom: Path,
    app_name: str,
    emulator: Path,
    output_dir: Path,
    serial: str | None = None,
    icon_path: Path | None = None,
    auto_cover: bool = True,
    fast_launch: bool = False,
    external_rom: bool = False,
    extra_args: str = "",
    create_launcher: bool = True,
    logger=None,
    stop_check=None,
) -> Path:
    def log(msg):
        if logger:
            logger(msg)

    info = collect_rom(platform, rom)
    rom = info["launch"]
    app_name = sanitize_name(app_name)
    app_id = stable_app_id(platform, app_name, rom)
    output_file = output_dir / f"{app_name}.AppImage"
    if output_file.exists():
        base, n = output_file.stem, 2
        while output_file.exists():
            output_file = output_dir / f"{base} ({n}).AppImage"
            n += 1

    # Force Switch to always use external ROM mode (no extraction)
    if platform == "Switch":
        external_rom = True
        log(f"▸ [Switch] Forcing external ROM mode for direct playback (no extraction)")

    # Detect PS3 extracted ISO folder
    is_ps3_folder = (platform == "PS3" and rom.is_dir() and (rom / "PS3_GAME").exists())
    if is_ps3_folder:
        if external_rom:
            log(f"▸ [PS3] Extracted ISO folder — external mode (launcher points to EBOOT.BIN)")
        else:
            log(f"▸ [PS3] Extracted ISO folder — injecting full game into AppImage")

    # Detect Wii U game folder
    is_wiiu_folder = (platform == "WiiU" and rom.is_dir() and ((rom / "code").exists() or (rom / "meta").exists()))
    if is_wiiu_folder:
        rpx_file = _find_wiiu_rpx(rom)
        if not rpx_file:
            log(f"▸ [Wii U] WARNING: No .rpx file found in code/ folder")
        if external_rom:
            log(f"▸ [Wii U] Game folder — external mode (launcher points to .rpx file)")
        else:
            log(f"▸ [Wii U] Game folder — injecting full game into AppImage")

    log(f"▸ Building: {app_name}")
    log(f"  Platform:  {platform}")
    log(f"  ROM:       {rom}")
    log(f"  Serial:    {serial or '—'}")
    log(f"  Output:    {output_file}")

    work_parent = output_dir / ".rom2app-work"
    work_parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="build-", dir=str(work_parent)) as tmpdir:
        temp = Path(tmpdir)
        appdir = temp / f"{app_id}.AppDir"
        data_dir = appdir / "usr" / "share" / app_id
        (appdir / "usr" / "share" / "applications").mkdir(parents=True)
        data_dir.mkdir(parents=True)
        source_icon = temp / "icon.png"

        shutil.copy2(emulator, data_dir / "emulator.AppImage")
        make_executable(data_dir / "emulator.AppImage")

        # Embed or reference ROM
        rom_files = info["bundle_files"]
        ext_path = str(rom.resolve()) if external_rom else None

        if is_ps3_folder and not external_rom:
            # Inject the entire PS3 game folder into the AppImage, preserving structure
            game_dest = data_dir / rom.name
            total = _dir_size(rom)
            log(f"  Injecting PS3 game folder ({human_bytes(total)})…")
            _check_disk_space(temp, total, log)
            copy_tree_with_progress(rom, game_dest, logger=log, stop_check=stop_check)
            log(f"  ✓ PS3 game injected into AppImage.")
        elif is_wiiu_folder and not external_rom:
            # Inject the entire Wii U game folder into the AppImage, preserving structure
            game_dest = data_dir / rom.name
            total = _dir_size(rom)
            log(f"  Injecting Wii U game folder ({human_bytes(total)})…")
            _check_disk_space(temp, total, log)
            copy_tree_with_progress(rom, game_dest, logger=log, stop_check=stop_check)
            log(f"  ✓ Wii U game injected into AppImage.")
        elif not external_rom:
            log(f"  Bundling {len(rom_files)} file(s)…")
            for rf in rom_files:
                if stop_check and stop_check():
                    raise RuntimeError("Cancelled")
                tgt = data_dir / rf.name
                if not tgt.exists():
                    copy_with_progress(rf, tgt, logger=log, stop_check=stop_check)
        else:
            if is_ps3_folder:
                log("  PS3 folder stays external — launcher points to EBOOT.BIN.")
            else:
                log("  ROM will stay external (small AppImage).")

        # Icon
        icon_done = False
        if icon_path and icon_path.is_file():
            try:
                from PIL import Image
                with Image.open(icon_path) as img:
                    img.convert("RGBA").save(source_icon, "PNG")
                icon_done = True
                log("  ✓ Using provided icon.")
            except Exception as e:
                log(f"  ✗ Icon error: {e}")

        if not icon_done and auto_cover:
            title = detect_internal_title(platform, rom)
            if serial:
                title = title or lookup_title(platform, serial)
            used_url = download_cover(platform, serial, title or app_name, source_icon)
            if used_url:
                icon_done = True
                log(f"  ✓ Cover art downloaded.")
            else:
                log("  ✗ Cover art not found.")

        if not icon_done:
            create_placeholder_icon(source_icon, platform)
            log("  ✓ Using placeholder icon.")

        install_appdir_icons(appdir, app_id, source_icon)

        # AppRun
        apprun = appdir / "AppRun"
        apprun.write_text(make_apprun(
            platform, app_id, rom.name,
            [p.name for p in rom_files],
            extra_args=extra_args,
            fast_launch=fast_launch,
            external_rom_path=ext_path,
            is_ps3_folder=is_ps3_folder,
            is_wiiu_folder=is_wiiu_folder,
        ))
        make_executable(apprun)

        # Desktop file
        desktop_text = (
            f"[Desktop Entry]\nVersion=1.0\nType=Application\n"
            f"Name={app_name}\nComment={app_name}\nExec=AppRun\nIcon={app_id}\n"
            f"Categories=Game;Emulator;\nTerminal=false\nStartupNotify=true\n"
            f"X-AppImage-Name={app_name}\nX-AppImage-Version=1.0\nX-AppImage-Icon={app_id}\n"
        )
        root_desktop = appdir / f"{app_id}.desktop"
        root_desktop.write_text(desktop_text)
        shutil.copy2(root_desktop, appdir / "usr" / "share" / "applications" / f"{app_id}.desktop")

        # Run appimagetool
        log("  Running appimagetool…")
        env = appimagetool_env_for_rebuild(output_file)
        proc = subprocess.Popen(
            ["appimagetool", str(appdir), str(output_file)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env
        )
        while True:
            if stop_check and stop_check():
                proc.terminate()
                proc.wait()
                raise RuntimeError("Cancelled")
            line = proc.stdout.readline() if proc.stdout else ""
            if line:
                log(f"  {line.rstrip()}")
            elif proc.poll() is not None:
                break
        if proc.wait() != 0:
            raise RuntimeError(f"appimagetool failed (code {proc.returncode})")

        make_executable(output_file)
        log(f"  ✓ AppImage created: {output_file.name}")

        if create_launcher:
            try:
                install_kde_launcher(output_file.resolve(), app_name, app_id, source_icon)
                log("  ✓ KDE launcher installed.")
            except Exception as e:
                log(f"  ✗ KDE launcher failed: {e}")

        refresh_desktop_caches()
        return output_file



# ─── Tk Artwork Manager ──────────────────────────────────────────────────────

class ArtworkManager(tk.Toplevel):
    """SteamGridDB/local artwork picker for the currently selected platform ROM."""
    def __init__(self, app: "Rom2App"):
        super().__init__(app)
        self.app = app
        self.results: list[dict] = []
        self.thumb_refs: list[object] = []
        self.selected_index: int | None = None

        self.title("Artwork Manager")
        self.geometry("980x720")
        self.minsize(760, 520)
        self.configure(bg=COLORS["bg"])
        self.transient(app)

        self.platform = app.platform.get()
        self.rom_path = Path(app.rom_path.get()) if app.rom_path.get() else None
        self.is_appimage_target = bool(self.rom_path and self.rom_path.is_file() and is_appimage_path(self.rom_path))
        self.detected_title, self.detected_serial = self._detect_current_rom()
        initial_query = sanitize_name(app.app_name.get() or self.detected_title or (self.rom_path.stem if self.rom_path else ""))

        header = tk.Frame(self, bg=COLORS["bg"])
        header.pack(fill="x", padx=18, pady=(16, 10))
        title = f"Artwork Manager — {'AppImage' if self.is_appimage_target else PLATFORMS[self.platform]['label']}"
        tk.Label(header, text=title, bg=COLORS["bg"], fg=COLORS["text"],
                 font=("Helvetica Neue", 17, "bold")).pack(anchor="w")
        target_text = str(self.rom_path) if self.rom_path else "No target selected"
        target_label = "Target AppImage" if self.is_appimage_target else "Target ROM"
        tk.Label(header, text=f"{target_label}: {target_text}", bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=("Helvetica Neue", 9), wraplength=900, justify="left").pack(anchor="w", pady=(3, 0))

        search_card = tk.Frame(self, bg=COLORS["card"], padx=14, pady=12)
        search_card.pack(fill="x", padx=18, pady=(0, 12))

        row = tk.Frame(search_card, bg=COLORS["card"])
        row.pack(fill="x")
        tk.Label(row, text="Search:", bg=COLORS["card"], fg=COLORS["text_dim"],
                 font=("Helvetica Neue", 10), width=10, anchor="w").pack(side="left")
        self.search_text = tk.StringVar(value=initial_query)
        tk.Entry(row, textvariable=self.search_text, bg=COLORS["input_bg"], fg=COLORS["text"],
                 insertbackground=COLORS["text"], relief="flat", bd=0,
                 font=("Helvetica Neue", 11)).pack(side="left", fill="x", expand=True, padx=(0, 8))
        tk.Button(row, text="✨ Smart Detect", bg=COLORS["accent"], fg="white",
                  font=("Helvetica Neue", 10, "bold"), relief="flat", bd=0, padx=10, pady=5,
                  command=self.smart_detect).pack(side="left", padx=(0, 6))
        tk.Button(row, text="🔍 Search", bg=COLORS["card_hover"], fg=COLORS["text"],
                  font=("Helvetica Neue", 10), relief="flat", bd=0, padx=10, pady=5,
                  command=self.manual_search).pack(side="left", padx=(0, 6))
        tk.Button(row, text="📁 Local Image", bg=COLORS["card_hover"], fg=COLORS["text"],
                  font=("Helvetica Neue", 10), relief="flat", bd=0, padx=10, pady=5,
                  command=self.use_local_image).pack(side="left")

        row2 = tk.Frame(search_card, bg=COLORS["card"])
        row2.pack(fill="x", pady=(10, 0))
        tk.Label(row2, text="Artwork:", bg=COLORS["card"], fg=COLORS["text_dim"],
                 font=("Helvetica Neue", 10), width=10, anchor="w").pack(side="left")
        self.art_type = tk.StringVar(value="grid")
        ttk.Combobox(row2, textvariable=self.art_type, state="readonly",
                     values=["grid", "hero", "logo", "icon"], width=12).pack(side="left", padx=(0, 8))
        tk.Button(row2, text="⬇ Use Selected", bg=COLORS["success"], fg="white",
                  font=("Helvetica Neue", 10, "bold"), relief="flat", bd=0, padx=10, pady=5,
                  command=self.use_selected).pack(side="left", padx=(0, 6))
        tk.Button(row2, text="🌐 Auto Cover for This Platform", bg=COLORS["card_hover"], fg=COLORS["text"],
                  font=("Helvetica Neue", 10), relief="flat", bd=0, padx=10, pady=5,
                  command=self.use_platform_auto_cover).pack(side="left", padx=(0, 6))
        tk.Button(row2, text="🧹 Clear Custom Icon", bg=COLORS["card_hover"], fg=COLORS["text"],
                  font=("Helvetica Neue", 10), relief="flat", bd=0, padx=10, pady=5,
                  command=self.clear_custom_icon).pack(side="left", padx=(0, 6))
        patch_text = "🛠 Patch AppImage Icon" if self.is_appimage_target else "🛠 Patch AppImage Icon (select .AppImage)"
        tk.Button(row2, text=patch_text, bg=COLORS["danger"], fg="white",
                  font=("Helvetica Neue", 10, "bold"), relief="flat", bd=0, padx=10, pady=5,
                  command=self.patch_appimage_icon).pack(side="left")

        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        self.canvas = tk.Canvas(body, bg=COLORS["log_bg"], highlightthickness=1,
                                highlightbackground=COLORS["border"])
        self.scrollbar = tk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.results_frame = tk.Frame(self.canvas, bg=COLORS["log_bg"])
        self.results_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas_window = self.canvas.create_window((0, 0), window=self.results_frame, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.canvas_window, width=e.width))
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.status = tk.Label(self, text="Ready.", bg=COLORS["bg"], fg=COLORS["text_dim"],
                               font=("Helvetica Neue", 10), anchor="w")
        self.status.pack(fill="x", padx=18, pady=(0, 12))

        self.bind("<Return>", lambda e: self.manual_search())
        if self.rom_path and self.rom_path.exists() and initial_query:
            self.after(150, self.smart_detect)

    def _detect_current_rom(self) -> tuple[str | None, str | None]:
        if not self.rom_path or not self.rom_path.exists():
            return None, None
        if self.is_appimage_target:
            return sanitize_name(self.rom_path.stem), None
        serial = detect_serial(self.platform, self.rom_path)
        title = detect_internal_title(self.platform, self.rom_path)
        if serial and self.platform in ("PS1", "PS2", "PSP", "PS3"):
            title = title or lookup_title(self.platform, serial)
        return title, serial

    def _set_status(self, text: str, error: bool = False):
        self.status.configure(text=text, fg=COLORS["danger"] if error else COLORS["text_dim"])
        self.update_idletasks()

    def _api_key(self) -> str:
        return DEFAULT_STEAMGRIDDB_KEY

    def _steamgriddb_request(self, endpoint: str) -> dict:
        url = f"{STEAMGRIDDB_API_BASE}/{endpoint.lstrip('/')}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self._api_key()}",
            "User-Agent": "Rom2App",
        })
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))

    def _steamgriddb_search_games(self, query: str) -> list[dict]:
        encoded = urllib.parse.quote(query)
        errors = []
        for endpoint in (f"search/autocomplete/{encoded}", f"search/{encoded}"):
            try:
                data = self._steamgriddb_request(endpoint)
                games = data.get("data", [])
                if games:
                    return games
            except Exception as e:
                errors.append(str(e))
        if errors:
            raise RuntimeError("SteamGridDB search failed: " + " | ".join(errors))
        return []

    def _art_endpoint(self, art_type: str, game_id) -> str:
        mapping = {"grid": "grids", "hero": "heroes", "logo": "logos", "icon": "icons"}
        return f"{mapping.get(str(art_type).lower(), 'grids')}/game/{game_id}"

    def smart_detect(self):
        title, serial = self._detect_current_rom()
        query = sanitize_name(self.app.app_name.get() or title or (self.rom_path.stem if self.rom_path else ""))
        if not query:
            messagebox.showinfo("No Target", "Select a ROM or .AppImage first. The Artwork Manager uses the selected file for the current platform.", parent=self)
            return
        self.search_text.set(query)
        self.manual_search()

    def manual_search(self):
        query = sanitize_name(self.search_text.get())
        if not query:
            messagebox.showinfo("Missing Search", "Enter a search term first.", parent=self)
            return
        try:
            self._set_status("Searching SteamGridDB…")
            games = self._steamgriddb_search_games(query)
            if not games:
                self._set_status("No SteamGridDB matches found.")
                return
            game = games[0]
            if len(games) > 1:
                labels = [f"{g.get('name', 'Unknown')}  [ID {g.get('id')}]" for g in games[:25]]
                picked = tk.StringVar(value=labels[0])
                dlg = tk.Toplevel(self)
                dlg.title("Choose SteamGridDB Match")
                dlg.configure(bg=COLORS["bg"])
                dlg.transient(self)
                dlg.grab_set()
                tk.Label(dlg, text="Multiple matches were found. Pick the right one:", bg=COLORS["bg"], fg=COLORS["text"], padx=16, pady=12).pack(anchor="w")
                box = tk.Listbox(dlg, bg=COLORS["log_bg"], fg=COLORS["text"], selectbackground=COLORS["accent"], width=58, height=min(12, len(labels)), relief="flat")
                box.pack(fill="both", expand=True, padx=16, pady=(0, 10))
                for label in labels:
                    box.insert("end", label)
                box.selection_set(0)
                chosen = {"idx": None}
                def accept():
                    sel = box.curselection()
                    chosen["idx"] = sel[0] if sel else 0
                    dlg.destroy()
                tk.Button(dlg, text="Use Selected", bg=COLORS["accent"], fg="white", relief="flat", padx=12, pady=6, command=accept).pack(pady=(0, 12))
                box.bind("<Double-Button-1>", lambda e: accept())
                self.wait_window(dlg)
                if chosen["idx"] is None:
                    self._set_status("No game selected.")
                    return
                game = games[chosen["idx"]]
            self._set_status(f"Loading artwork for {game.get('name', game.get('id'))}…")
            data = self._steamgriddb_request(self._art_endpoint(self.art_type.get(), game.get("id")))
            images = data.get("data", [])
            self.populate_results(images)
            self._set_status(f"{len(images)} artwork result(s) loaded.")
        except Exception as e:
            self._set_status("SteamGridDB search failed.", True)
            messagebox.showwarning("Artwork Search Failed", str(e), parent=self)

    def populate_results(self, images: list[dict]):
        for child in self.results_frame.winfo_children():
            child.destroy()
        self.thumb_refs.clear()
        self.results = images[:80]
        self.selected_index = None
        if not self.results:
            tk.Label(self.results_frame, text="No artwork found.", bg=COLORS["log_bg"], fg=COLORS["text_dim"], font=("Helvetica Neue", 12)).pack(pady=30)
            return
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cols = 4
        for i, item in enumerate(self.results):
            url = item.get("thumb") or item.get("url")
            full_url = item.get("url") or url
            cell = tk.Frame(self.results_frame, bg=COLORS["card"], padx=8, pady=8, highlightthickness=1, highlightbackground=COLORS["border"])
            cell.grid(row=i // cols, column=i % cols, padx=8, pady=8, sticky="n")
            try:
                ext = Path(urllib.parse.urlparse(url).path).suffix or ".jpg"
                thumb = CACHE_DIR / (hashlib.sha256(url.encode()).hexdigest() + ext)
                if not thumb.exists():
                    _download_url(url, thumb)
                from PIL import Image, ImageTk
                img = Image.open(thumb).convert("RGBA")
                img.thumbnail((175, 245), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.thumb_refs.append(photo)
                lbl = tk.Label(cell, image=photo, bg=COLORS["card"], cursor="hand2")
            except Exception:
                lbl = tk.Label(cell, text="Preview\nfailed", bg=COLORS["card"], fg=COLORS["text_dim"], width=20, height=10, cursor="hand2")
            lbl.pack()
            caption = tk.Label(cell, text=f"{item.get('style', 'art')} #{i+1}", bg=COLORS["card"], fg=COLORS["text"], font=("Helvetica Neue", 9))
            caption.pack(pady=(6, 0))
            def select(idx=i, selected_cell=cell):
                self.selected_index = idx
                for c in self.results_frame.winfo_children():
                    c.configure(highlightbackground=COLORS["border"], bg=COLORS["card"])
                    for sub in c.winfo_children():
                        try:
                            sub.configure(bg=COLORS["card"])
                        except Exception:
                            pass
                selected_cell.configure(highlightbackground=COLORS["accent"], bg=COLORS["card_hover"])
                for sub in selected_cell.winfo_children():
                    try:
                        sub.configure(bg=COLORS["card_hover"])
                    except Exception:
                        pass
                self._set_status(f"Selected artwork #{idx+1}. Click Use Selected to assign it.")
            for widget in (cell, lbl, caption):
                widget.bind("<Button-1>", lambda e, idx=i: select(idx))
                widget.bind("<Double-Button-1>", lambda e, idx=i: (select(idx), self.use_selected()))
            if i == 0:
                self.after(10, select)

    def _download_selected_to_cache(self) -> Path | None:
        if self.selected_index is None or self.selected_index >= len(self.results):
            messagebox.showinfo("No Selection", "Select artwork first.", parent=self)
            return None
        url = self.results[self.selected_index].get("url") or self.results[self.selected_index].get("thumb")
        if not url:
            return None
        ext = Path(urllib.parse.urlparse(url).path).suffix or ".png"
        dest = CACHE_DIR / (hashlib.sha256(url.encode()).hexdigest() + ext)
        if not dest.exists() and not _download_url(url, dest):
            raise RuntimeError("Could not download selected artwork.")
        return dest

    def _assign_icon(self, path: Path):
        from PIL import Image
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        rom_key = str(self.rom_path.resolve() if self.rom_path and self.rom_path.exists() else self.search_text.get())
        dest = CACHE_DIR / f"custom-{hashlib.sha1((self.platform + ':' + rom_key).encode()).hexdigest()[:16]}.png"
        with Image.open(path) as img:
            img.convert("RGBA").save(dest, "PNG")
        self.app.icon_path.set(str(dest))
        self.app._display_preview(self.app._single_preview_canvas, dest)
        self.app.log(f"Artwork Manager: custom icon set for {self.platform}: {dest}")
        self._set_status(f"Custom icon set: {dest.name}")

    def use_selected(self):
        try:
            path = self._download_selected_to_cache()
            if path:
                self._assign_icon(path)
        except Exception as e:
            messagebox.showwarning("Artwork Download Failed", str(e), parent=self)

    def use_platform_auto_cover(self):
        if not self.rom_path or not self.rom_path.exists():
            messagebox.showinfo("No Target", "Select a ROM or .AppImage first. This uses the current target selection.", parent=self)
            return
        if self.is_appimage_target:
            self.smart_detect()
            return
        try:
            self._set_status("Downloading best platform cover…")
            title, serial = self._detect_current_rom()
            title = title or self.app.app_name.get() or self.rom_path.stem
            dest = CACHE_DIR / f"auto-{hashlib.sha1((self.platform + ':' + str(self.rom_path)).encode()).hexdigest()[:16]}.png"
            used = download_cover(self.platform, serial, title, dest)
            if not used:
                raise RuntimeError("No platform cover found. Try SteamGridDB Search or Local Image.")
            self._assign_icon(dest)
            self._set_status("Platform cover assigned.")
        except Exception as e:
            self._set_status("Platform cover failed.", True)
            messagebox.showwarning("Auto Cover Failed", str(e), parent=self)

    def use_local_image(self):
        p = filedialog.askopenfilename(parent=self, initialdir=str(Path.home()),
                                       filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")])
        if p:
            self._assign_icon(Path(p))

    def patch_appimage_icon(self):
        if not self.is_appimage_target or not self.rom_path:
            messagebox.showinfo("Not an AppImage", "Select a .AppImage target first.", parent=self)
            return
        artwork = Path(self.app.icon_path.get()) if self.app.icon_path.get() else None
        if not artwork or not artwork.is_file():
            messagebox.showinfo("Select Artwork First", "Choose artwork with Search, Smart Detect, Use Selected, or Local Image before patching the AppImage.", parent=self)
            return
        if not messagebox.askyesno(
            "Patch AppImage Icon?",
            "This will extract and rebuild the selected AppImage with the current artwork as its thumbnail/icon.\n\n"
            + ("No .bak backup will be created because that option is enabled. Continue?" if self.app.no_patch_backups.get() else "A .bak backup will be created next to the original AppImage. Continue?"),
            parent=self,
        ):
            return
        try:
            self._set_status("Patching AppImage icon…")
            replaced = patch_appimage_artwork(self.rom_path, artwork, logger=self.app.log, create_backup=not self.app.no_patch_backups.get())
            self._set_status(f"Patched AppImage icon ({len(replaced)} target files replaced).")
            messagebox.showinfo("AppImage Patched", f"Artwork was patched into:\n{self.rom_path}\n\nReplaced {len(replaced)} icon target(s).", parent=self)
        except Exception as e:
            self._set_status("AppImage patch failed.", True)
            messagebox.showerror("Patch Failed", str(e), parent=self)

    def clear_custom_icon(self):
        self.app.icon_path.set("")
        try:
            self.app._update_single_preview()
        except Exception:
            pass
        self._set_status("Custom icon cleared.")


# ─── GUI ──────────────────────────────────────────────────────────────────────

class Rom2App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Rom2App")
        self.geometry("1160x820")
        self.minsize(900, 700)
        self.configure(bg=COLORS["bg"])

        self.stop_requested = False
        self.scanned_batch: list[dict] = []
        self._build_in_progress = False

        # Settings vars
        self.platform     = tk.StringVar(value="PS1")
        # Each console keeps its own emulator AppImage. `emulator_path` is the
        # one currently shown (for the active platform); `emulator_paths` holds
        # the saved selection for every platform.
        self.emulator_paths: dict[str, str] = {}
        self.rom_paths: dict[str, str] = {}
        self.icon_paths: dict[str, str] = {}
        self.app_names: dict[str, str] = {}
        self.serials: dict[str, str] = {}
        self.emulator_path = tk.StringVar()
        self.rom_path      = tk.StringVar()
        self.icon_path     = tk.StringVar()
        self.redump_path   = tk.StringVar()
        self.output_dir    = tk.StringVar(value=str(Path.home() / "Desktop"))
        self.app_name      = tk.StringVar()
        self.serial        = tk.StringVar()
        self.extra_args    = tk.StringVar()
        self.auto_cover    = tk.BooleanVar(value=True)
        self.create_launcher = tk.BooleanVar(value=True)
        self.fast_launch   = tk.BooleanVar(value=False)
        self.external_rom  = tk.BooleanVar(value=False)
        self.build_both    = tk.BooleanVar(value=False)
        self.batch_folder  = tk.StringVar()
        self.batch_recursive = tk.BooleanVar(value=True)
        self.no_patch_backups = tk.BooleanVar(value=False)
        # Appearance settings
        self.theme         = tk.StringVar(value=DEFAULT_THEME)
        self.preview_scale = tk.StringVar(value=DEFAULT_PREVIEW)
        self._settings_win = None

        self._loading = True
        self.load_settings()
        self._build_ui()
        self._setup_autosave()
        self._loading = False
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.log(f"Rom2App {APP_VERSION} ready  ·  Platform: {self.platform.get()}")
        self.log("Per-platform ROM/AppImage fields enabled. Artwork Manager can patch selected .AppImage icons using safer temp-space checks and ARCH-fixed appimagetool rebuilds.")

    # ── Settings persistence ──────────────────────────────────────────────────

    def load_settings(self):
        try:
            d = json.loads(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else {}
            self.platform.set(d.get("platform", "PS1"))
            # Per-platform emulators (with migration from the old single value)
            self.emulator_paths = {
                k: v for k, v in dict(d.get("emulator_paths", {})).items()
                if isinstance(v, str)
            }
            cur = self.platform.get()
            legacy = d.get("emulator_path", "")
            if cur not in self.emulator_paths and legacy:
                self.emulator_paths[cur] = legacy
            self.emulator_path.set(self.emulator_paths.get(cur, ""))
            # Per-platform ROM/artwork/name state (with migration from older single shared values)
            self.rom_paths = {k: v for k, v in dict(d.get("rom_paths", {})).items() if isinstance(v, str)}
            self.icon_paths = {k: v for k, v in dict(d.get("icon_paths", {})).items() if isinstance(v, str)}
            self.app_names = {k: v for k, v in dict(d.get("app_names", {})).items() if isinstance(v, str)}
            self.serials = {k: v for k, v in dict(d.get("serials", {})).items() if isinstance(v, str)}
            if cur not in self.rom_paths and d.get("rom_path", ""):
                self.rom_paths[cur] = d.get("rom_path", "")
            if cur not in self.icon_paths and d.get("icon_path", ""):
                self.icon_paths[cur] = d.get("icon_path", "")
            if cur not in self.app_names and d.get("app_name", ""):
                self.app_names[cur] = d.get("app_name", "")
            if cur not in self.serials and d.get("serial", ""):
                self.serials[cur] = d.get("serial", "")
            self.rom_path.set(self.rom_paths.get(cur, ""))
            self.icon_path.set(self.icon_paths.get(cur, ""))
            self.redump_path.set(d.get("redump_path", ""))
            self.output_dir.set(d.get("output_dir", str(Path.home() / "Desktop")))
            self.app_name.set(self.app_names.get(cur, d.get("app_name", "")))
            self.serial.set(self.serials.get(cur, d.get("serial", "")))
            self.extra_args.set(d.get("extra_args", ""))
            self.auto_cover.set(d.get("auto_cover", True))
            self.create_launcher.set(d.get("create_launcher", True))
            self.fast_launch.set(d.get("fast_launch", False))
            self.external_rom.set(d.get("external_rom", False))
            self.build_both.set(d.get("build_both", False))
            self.batch_folder.set(d.get("batch_folder", ""))
            self.batch_recursive.set(d.get("batch_recursive", True))
            self.no_patch_backups.set(d.get("no_patch_backups", False))
            self.theme.set(d.get("theme", DEFAULT_THEME))
            self.preview_scale.set(d.get("preview_scale", DEFAULT_PREVIEW))
            self._apply_theme(self.theme.get())
        except Exception:
            pass

    def save_settings(self, *_):
        if self._loading:
            return
        # Keep per-platform dictionaries in sync with whatever is shown for the active platform.
        current_platform = self.platform.get()
        self.emulator_paths[current_platform] = self.emulator_path.get()
        self.rom_paths[current_platform] = self.rom_path.get()
        self.icon_paths[current_platform] = self.icon_path.get()
        self.app_names[current_platform] = self.app_name.get()
        self.serials[current_platform] = self.serial.get()
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps({
            "platform": self.platform.get(),
            "emulator_paths": self.emulator_paths,
            "emulator_path": self.emulator_path.get(),
            "rom_paths": self.rom_paths,
            "icon_paths": self.icon_paths,
            "app_names": self.app_names,
            "serials": self.serials,
            "rom_path": self.rom_path.get(),
            "icon_path": self.icon_path.get(),
            "redump_path": self.redump_path.get(),
            "output_dir": self.output_dir.get(),
            "app_name": self.app_name.get(),
            "serial": self.serial.get(),
            "extra_args": self.extra_args.get(),
            "auto_cover": self.auto_cover.get(),
            "create_launcher": self.create_launcher.get(),
            "fast_launch": self.fast_launch.get(),
            "external_rom": self.external_rom.get(),
            "build_both": self.build_both.get(),
            "batch_folder": self.batch_folder.get(),
            "batch_recursive": self.batch_recursive.get(),
            "no_patch_backups": self.no_patch_backups.get(),
            "theme": self.theme.get(),
            "preview_scale": self.preview_scale.get(),
        }, indent=2))

    def _setup_autosave(self):
        for v in [self.platform, self.emulator_path, self.rom_path, self.icon_path,
                  self.redump_path, self.output_dir, self.app_name, self.serial,
                  self.extra_args, self.auto_cover, self.create_launcher,
                  self.fast_launch, self.external_rom, self.build_both,
                  self.batch_folder, self.batch_recursive, self.no_patch_backups,
                  self.theme, self.preview_scale]:
            v.trace_add("write", self.save_settings)

    def _on_close(self):
        self.save_settings()
        self.destroy()

    # ── Appearance / themes ───────────────────────────────────────────────────

    def _apply_theme(self, name: str):
        """Swap the active palette in place."""
        palette = THEMES.get(name, THEMES[DEFAULT_THEME])
        COLORS.clear()
        COLORS.update(palette)
        try:
            self.configure(bg=COLORS["bg"])
        except Exception:
            pass

    def _preview_dims(self) -> tuple[int, int]:
        return PREVIEW_SIZES.get(self.preview_scale.get(), PREVIEW_SIZES[DEFAULT_PREVIEW])

    def _rebuild_ui(self):
        """Tear down and recreate the whole UI so a new theme/preview size applies."""
        # Preserve the current log contents across the rebuild
        log_text = ""
        try:
            log_text = self._log_widget.get("1.0", "end-1c")
        except Exception:
            pass
        try:
            self._root_frame.destroy()
        except Exception:
            pass
        was_loading = self._loading
        self._loading = True            # avoid autosave churn while rebuilding
        self._build_ui()
        self._update_sidebar_selection()
        self._update_platform_ui()
        try:
            self._update_single_preview()
        except Exception:
            pass
        if log_text.strip():
            try:
                self._log_widget.insert("end", log_text + "\n")
                self._log_widget.see("end")
            except Exception:
                pass
        self._loading = was_loading

    def _open_settings(self):
        # If already open, just bring it to the front
        if self._settings_win is not None and tk.Toplevel.winfo_exists(self._settings_win):
            self._settings_win.lift()
            self._settings_win.focus_force()
            return

        win = tk.Toplevel(self)
        self._settings_win = win
        win.title("Settings")
        win.configure(bg=COLORS["bg"])
        win.geometry("420x300")
        win.resizable(False, False)
        win.transient(self)

        def _on_dialog_close():
            self._settings_win = None
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", _on_dialog_close)

        tk.Label(win, text="⚙  Settings", bg=COLORS["bg"], fg=COLORS["text"],
                 font=("Helvetica Neue", 16, "bold")).pack(anchor="w", padx=20, pady=(18, 4))
        tk.Label(win, text="Appearance", bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=("Helvetica Neue", 9, "bold")).pack(anchor="w", padx=20, pady=(8, 6))

        card = tk.Frame(win, bg=COLORS["card"], padx=16, pady=14)
        card.pack(fill="x", padx=20)

        # Theme row
        theme_row = tk.Frame(card, bg=COLORS["card"])
        theme_row.pack(fill="x", pady=6)
        tk.Label(theme_row, text="Theme:", bg=COLORS["card"], fg=COLORS["text"],
                 font=("Helvetica Neue", 11), width=14, anchor="w").pack(side="left")
        theme_box = ttk.Combobox(theme_row, textvariable=self.theme, state="readonly",
                                 values=list(THEMES.keys()), width=18)
        theme_box.pack(side="left", fill="x", expand=True)
        theme_box.bind("<<ComboboxSelected>>", self._on_theme_change)

        # Preview-size row
        prev_row = tk.Frame(card, bg=COLORS["card"])
        prev_row.pack(fill="x", pady=6)
        tk.Label(prev_row, text="Cover preview:", bg=COLORS["card"], fg=COLORS["text"],
                 font=("Helvetica Neue", 11), width=14, anchor="w").pack(side="left")
        prev_box = ttk.Combobox(prev_row, textvariable=self.preview_scale, state="readonly",
                                values=list(PREVIEW_SIZES.keys()), width=18)
        prev_box.pack(side="left", fill="x", expand=True)
        prev_box.bind("<<ComboboxSelected>>", self._on_preview_change)

        tk.Label(win, text="Changes apply instantly.", bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=("Helvetica Neue", 9)).pack(anchor="w", padx=20, pady=(12, 0))

        tk.Button(win, text="Close", bg=COLORS["accent"], fg="white",
                  font=("Helvetica Neue", 11, "bold"), relief="flat", bd=0,
                  padx=16, pady=8, cursor="hand2", activebackground=COLORS["accent2"],
                  command=_on_dialog_close).pack(side="bottom", anchor="e", padx=20, pady=18)

    def _on_theme_change(self, *_):
        self._apply_theme(self.theme.get())
        self.save_settings()
        self._rebuild_ui()
        # Reopen the settings dialog so it picks up the new theme colours
        if self._settings_win is not None:
            try:
                self._settings_win.destroy()
            except Exception:
                pass
            self._settings_win = None
            self.after(20, self._open_settings)

    def _on_preview_change(self, *_):
        self.save_settings()
        self._rebuild_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self._setup_styles()

        # Root layout: sidebar + main
        root_frame = tk.Frame(self, bg=COLORS["bg"])
        root_frame.pack(fill="both", expand=True)
        self._root_frame = root_frame

        self._build_sidebar(root_frame)

        main = tk.Frame(root_frame, bg=COLORS["bg"])
        main.pack(side="left", fill="both", expand=True)

        self._build_header(main)
        self._build_main_content(main)

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        bg   = COLORS["bg"]
        card = COLORS["card"]
        acc  = COLORS["accent"]
        txt  = COLORS["text"]
        dim  = COLORS["text_dim"]
        inp  = COLORS["input_bg"]
        bor  = COLORS["border"]

        style.configure(".", background=bg, foreground=txt, font=("SF Pro Text", 11) if self._has_font("SF Pro Text") else ("Helvetica Neue", 11))
        style.configure("TFrame", background=bg)
        style.configure("Card.TFrame", background=card)
        style.configure("TLabel", background=bg, foreground=txt)
        style.configure("Dim.TLabel", background=card, foreground=dim)
        style.configure("Card.TLabel", background=card, foreground=txt)
        style.configure("TEntry", fieldbackground=inp, foreground=txt, bordercolor=bor, insertcolor=txt, padding=6)
        style.configure("TCheckbutton", background=card, foreground=txt)
        style.configure("TCombobox", fieldbackground=inp, foreground=txt, selectbackground=acc, padding=6)
        style.map("TCombobox", fieldbackground=[("readonly", inp)])
        style.configure("Accent.TButton", background=acc, foreground="#FFFFFF", padding=(12, 8), relief="flat", borderwidth=0)
        style.map("Accent.TButton", background=[("active", COLORS["accent2"]), ("disabled", bor)])
        style.configure("Ghost.TButton", background=card, foreground=txt, padding=(12, 8), relief="flat", borderwidth=1)
        style.map("Ghost.TButton", background=[("active", COLORS["card_hover"])])
        style.configure("Danger.TButton", background=COLORS["danger"], foreground="#FFFFFF", padding=(10, 8), relief="flat")
        style.map("Danger.TButton", background=[("active", "#ef4444")])
        style.configure("TSeparator", background=COLORS["border"])
        style.configure("TNotebook", background=COLORS["bg"], tabmargins=[0, 0, 0, 0])
        style.configure("TNotebook.Tab", background=COLORS["sidebar"], foreground=dim, padding=[16, 10], font=("Helvetica Neue", 10))
        style.map("TNotebook.Tab", background=[("selected", card)], foreground=[("selected", txt)])

    def _has_font(self, name):
        try:
            import tkinter.font as tkfont
            return name in tkfont.families()
        except Exception:
            return False

    def _build_sidebar(self, parent):
        sidebar = tk.Frame(parent, bg=COLORS["sidebar"], width=190)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Logo area
        logo_frame = tk.Frame(sidebar, bg=COLORS["sidebar"])
        logo_frame.pack(fill="x", pady=(24, 8), padx=16)
        tk.Label(logo_frame, text="🎮", bg=COLORS["sidebar"], fg=COLORS["text"],
                 font=("Helvetica Neue", 28)).pack(anchor="w")
        tk.Label(logo_frame, text="Rom2App", bg=COLORS["sidebar"], fg=COLORS["text"],
                 font=("Helvetica Neue", 15, "bold")).pack(anchor="w", pady=(4, 0))
        tk.Label(logo_frame, text=f"v{APP_VERSION}", bg=COLORS["sidebar"], fg=COLORS["text_dim"],
                 font=("Helvetica Neue", 9)).pack(anchor="w")

        tk.Frame(sidebar, bg=COLORS["border"], height=1).pack(fill="x", padx=16, pady=16)

        # Settings entry
        settings_btn = tk.Label(sidebar, text="⚙  Settings", bg=COLORS["sidebar"],
                                fg=COLORS["text_dim"], font=("Helvetica Neue", 11),
                                cursor="hand2", anchor="w")
        settings_btn.pack(fill="x", padx=16, pady=(0, 8))
        settings_btn.bind("<Button-1>", lambda e: self._open_settings())
        settings_btn.bind("<Enter>", lambda e: settings_btn.configure(fg=COLORS["text"]))
        settings_btn.bind("<Leave>", lambda e: settings_btn.configure(fg=COLORS["text_dim"]))

        # Platform selector
        tk.Label(sidebar, text="PLATFORM", bg=COLORS["sidebar"], fg=COLORS["text_dim"],
                 font=("Helvetica Neue", 9, "bold")).pack(anchor="w", padx=16, pady=(0, 8))

        self._platform_btns = {}
        for plat in PLATFORMS:
            color = PLATFORM_COLORS[plat]
            btn_frame = tk.Frame(sidebar, bg=COLORS["sidebar"])
            btn_frame.pack(fill="x", padx=12, pady=2)
            dot = tk.Label(btn_frame, text="●", bg=COLORS["sidebar"], fg=color,
                           font=("Helvetica Neue", 8))
            dot.pack(side="left", padx=(4, 6))
            lbl = PLATFORMS[plat]["label"]
            btn = tk.Label(btn_frame, text=lbl, bg=COLORS["sidebar"], fg=COLORS["text"],
                           font=("Helvetica Neue", 11), cursor="hand2", anchor="w")
            btn.pack(side="left", fill="x", expand=True)
            btn_frame.bind("<Button-1>", lambda e, p=plat: self._select_platform(p))
            btn.bind("<Button-1>", lambda e, p=plat: self._select_platform(p))
            dot.bind("<Button-1>", lambda e, p=plat: self._select_platform(p))
            self._platform_btns[plat] = (btn_frame, btn, dot, color)

        tk.Frame(sidebar, bg=COLORS["border"], height=1).pack(fill="x", padx=16, pady=16)

        # Status area
        self._status_label = tk.Label(sidebar, text="Idle", bg=COLORS["sidebar"],
                                      fg=COLORS["success"], font=("Helvetica Neue", 10),
                                      wraplength=160, justify="left")
        self._status_label.pack(anchor="w", padx=16, pady=(0, 8))

        # Stop button
        stop_btn = tk.Button(sidebar, text="⏹  Stop Build",
                             bg=COLORS["danger"], fg="white",
                             font=("Helvetica Neue", 10, "bold"),
                             relief="flat", bd=0, padx=8, pady=6,
                             cursor="hand2", activebackground="#ef4444",
                             command=self._request_stop)
        stop_btn.pack(fill="x", padx=12, pady=4)

        self._update_sidebar_selection()

    def _select_platform(self, plat: str):
        prev = self.platform.get()
        if plat == prev:
            return
        # Remember all shown per-platform fields for the platform we're leaving…
        self.emulator_paths[prev] = self.emulator_path.get()
        self.rom_paths[prev] = self.rom_path.get()
        self.icon_paths[prev] = self.icon_path.get()
        self.app_names[prev] = self.app_name.get()
        self.serials[prev] = self.serial.get()
        # …then switch and restore the selections saved for the new platform.
        self._loading = True            # suppress autosave churn during the swap
        self.platform.set(plat)
        self.emulator_path.set(self.emulator_paths.get(plat, ""))
        self.rom_path.set(self.rom_paths.get(plat, ""))
        self.icon_path.set(self.icon_paths.get(plat, ""))
        self.app_name.set(self.app_names.get(plat, ""))
        self.serial.set(self.serials.get(plat, ""))
        self._loading = False
        self.save_settings()
        self._update_sidebar_selection()
        self._update_platform_ui()

    def _update_sidebar_selection(self):
        current = self.platform.get()
        for plat, (frame, lbl, dot, color) in self._platform_btns.items():
            if plat == current:
                frame.configure(bg=COLORS["card"])
                lbl.configure(bg=COLORS["card"], fg=COLORS["text"], font=("Helvetica Neue", 11, "bold"))
                dot.configure(bg=COLORS["card"])
            else:
                frame.configure(bg=COLORS["sidebar"])
                lbl.configure(bg=COLORS["sidebar"], fg=COLORS["text_dim"], font=("Helvetica Neue", 11))
                dot.configure(bg=COLORS["sidebar"])

    def _update_platform_ui(self):
        plat = self.platform.get()
        info = PLATFORMS[plat]
        self._platform_header_label.configure(text=info["label"])
        color = PLATFORM_COLORS[plat]
        self._platform_stripe.configure(bg=color)
        emulator_label = f"{info['emulator_hint']} AppImage:"
        self._emulator_row_label.configure(text=emulator_label)
        exts_text = "  ".join(sorted(info["exts"]))
        self._exts_label.configure(text=f"Supported: {exts_text}")
        # Show/hide external-ROM options for platforms with large files
        has_external = plat in ("GameCube", "Xbox", "PSP", "PS3", "Xbox360", "WiiU", "Switch")
        if has_external:
            self._ext_rom_frame.pack(fill="x", padx=20, pady=2)
            self._build_both_frame.pack(fill="x", padx=20, pady=2)
        else:
            self._ext_rom_frame.pack_forget()
            self._build_both_frame.pack_forget()
        self.log(f"Platform switched → {info['label']}")

    def _build_header(self, parent):
        header = tk.Frame(parent, bg=COLORS["bg"])
        header.pack(fill="x", padx=24, pady=(20, 0))

        left = tk.Frame(header, bg=COLORS["bg"])
        left.pack(side="left", fill="x", expand=True)

        self._platform_stripe = tk.Frame(left, bg=PLATFORM_COLORS.get(self.platform.get(), COLORS["accent"]), width=4)
        self._platform_stripe.pack(side="left", fill="y", padx=(0, 12))

        title_frame = tk.Frame(left, bg=COLORS["bg"])
        title_frame.pack(side="left")
        self._platform_header_label = tk.Label(title_frame,
                                               text=PLATFORMS[self.platform.get()]["label"],
                                               bg=COLORS["bg"], fg=COLORS["text"],
                                               font=("Helvetica Neue", 20, "bold"))
        self._platform_header_label.pack(anchor="w")
        self._exts_label = tk.Label(title_frame, text="", bg=COLORS["bg"],
                                    fg=COLORS["text_dim"], font=("Helvetica Neue", 10))
        self._exts_label.pack(anchor="w")

        # Build action buttons
        btns = tk.Frame(header, bg=COLORS["bg"])
        btns.pack(side="right")
        self._build_single_btn = tk.Button(btns, text="▶  Build Single",
                                           bg=COLORS["accent"], fg="white",
                                           font=("Helvetica Neue", 11, "bold"),
                                           relief="flat", bd=0, padx=14, pady=8,
                                           cursor="hand2", activebackground=COLORS["accent2"],
                                           command=self._build_single)
        self._build_single_btn.pack(side="left", padx=(0, 8))
        self._build_batch_btn = tk.Button(btns, text="⚡  Build Batch",
                                          bg=COLORS["card"], fg=COLORS["text"],
                                          font=("Helvetica Neue", 11),
                                          relief="flat", bd=0, padx=14, pady=8,
                                          cursor="hand2", activebackground=COLORS["card_hover"],
                                          command=self._build_batch)
        self._build_batch_btn.pack(side="left", padx=(0, 8))
        self._patch_appimages_btn = tk.Button(btns, text="🩹  Patch AppImages",
                                             bg=COLORS["card"], fg=COLORS["text"],
                                             font=("Helvetica Neue", 11),
                                             relief="flat", bd=0, padx=14, pady=8,
                                             cursor="hand2", activebackground=COLORS["card_hover"],
                                             command=self._patch_appimages)
        self._patch_appimages_btn.pack(side="left", padx=(0, 10))

        self._no_patch_backup_check = tk.Checkbutton(
            btns,
            text="No .bak backups",
            variable=self.no_patch_backups,
            bg=COLORS["bg"],
            fg=COLORS["text_dim"],
            selectcolor=COLORS["card"],
            activebackground=COLORS["bg"],
            activeforeground=COLORS["text"],
            font=("Helvetica Neue", 10),
            relief="flat",
            cursor="hand2",
            command=self.save_settings,
        )
        self._no_patch_backup_check.pack(side="left")

        tk.Frame(parent, bg=COLORS["border"], height=1).pack(fill="x", padx=24, pady=12)

    def _build_main_content(self, parent):
        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        self._build_single_tab(notebook)
        self._build_batch_tab(notebook)
        self._build_options_tab(notebook)
        self._build_log_tab(notebook)

        self._update_platform_ui()

    def _card_frame(self, parent):
        f = tk.Frame(parent, bg=COLORS["card"], padx=16, pady=12)
        f.pack(fill="x", pady=(0, 10))
        return f

    def _section_label(self, parent, text):
        tk.Label(parent, text=text.upper(), bg=COLORS["bg"],
                 fg=COLORS["text_dim"], font=("Helvetica Neue", 9, "bold")).pack(
                     anchor="w", padx=4, pady=(12, 4))

    def _file_row(self, parent, label, var, pick_cmd, hint=""):
        row = tk.Frame(parent, bg=COLORS["card"])
        row.pack(fill="x", pady=4)
        tk.Label(row, text=label, bg=COLORS["card"], fg=COLORS["text_dim"],
                 font=("Helvetica Neue", 10), width=22, anchor="w").pack(side="left")
        entry = tk.Entry(row, textvariable=var, bg=COLORS["input_bg"], fg=COLORS["text"],
                         insertbackground=COLORS["text"], relief="flat", bd=0, font=("Helvetica Neue", 11))
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        btn = tk.Button(row, text="Browse", bg=COLORS["border"], fg=COLORS["text"],
                        font=("Helvetica Neue", 10), relief="flat", bd=0, padx=10, pady=4,
                        cursor="hand2", activebackground=COLORS["card_hover"],
                        command=pick_cmd)
        btn.pack(side="right")
        if hint:
            tk.Label(parent, text=hint, bg=COLORS["card"], fg=COLORS["text_dim"],
                     font=("Helvetica Neue", 9)).pack(anchor="w", pady=(0, 4))
        return entry

    def _check_row(self, parent, text, var):
        f = tk.Frame(parent, bg=COLORS["card"])
        f.pack(fill="x", pady=3)
        cb = tk.Checkbutton(f, text=text, variable=var, bg=COLORS["card"],
                             fg=COLORS["text"], selectcolor=COLORS["input_bg"],
                             activebackground=COLORS["card"], font=("Helvetica Neue", 11),
                             relief="flat", bd=0, cursor="hand2")
        cb.pack(anchor="w")
        return f

    def _build_single_tab(self, notebook):
        frame = tk.Frame(notebook, bg=COLORS["bg"])
        notebook.add(frame, text="  Single ROM  ")
        
        # Top section - scrollable content
        content_frame = tk.Frame(frame, bg=COLORS["bg"])
        content_frame.pack(fill="both", expand=True)
        
        canvas = tk.Canvas(content_frame, bg=COLORS["bg"], highlightthickness=0)
        scroll = tk.Scrollbar(content_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=COLORS["bg"])
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(inner_id, width=e.width))

        # Emulator section
        self._section_label(inner, "Emulator")
        emulator_card = self._card_frame(inner)
        emulator_lbl = tk.Label(emulator_card, text="", bg=COLORS["card"], fg=COLORS["text_dim"],
                                font=("Helvetica Neue", 10), width=22, anchor="w")
        emulator_lbl.pack(side="left")
        self._emulator_row_label = emulator_lbl
        emulator_row = tk.Frame(emulator_card, bg=COLORS["card"])
        emulator_row.pack(fill="x")
        self._file_row(emulator_card, "Emulator AppImage:", self.emulator_path, self._pick_emulator)

        # ROM section
        self._section_label(inner, "ROM / AppImage File")
        rom_card = self._card_frame(inner)
        self._file_row(rom_card, "ROM / AppImage:", self.rom_path, self._pick_rom,
                       hint="Each platform keeps its own ROM or .AppImage selection.")
        # App name + serial row
        name_row = tk.Frame(rom_card, bg=COLORS["card"])
        name_row.pack(fill="x", pady=6)
        tk.Label(name_row, text="App name:", bg=COLORS["card"], fg=COLORS["text_dim"],
                 font=("Helvetica Neue", 10), width=22, anchor="w").pack(side="left")
        tk.Entry(name_row, textvariable=self.app_name, bg=COLORS["input_bg"], fg=COLORS["text"],
                 insertbackground=COLORS["text"], relief="flat", bd=0,
                 font=("Helvetica Neue", 11)).pack(side="left", fill="x", expand=True, padx=(0, 8))
        serial_row = tk.Frame(rom_card, bg=COLORS["card"])
        serial_row.pack(fill="x", pady=4)
        tk.Label(serial_row, text="Serial / ID:", bg=COLORS["card"], fg=COLORS["text_dim"],
                 font=("Helvetica Neue", 10), width=22, anchor="w").pack(side="left")
        tk.Entry(serial_row, textvariable=self.serial, bg=COLORS["input_bg"], fg=COLORS["text"],
                 insertbackground=COLORS["text"], relief="flat", bd=0,
                 font=("Helvetica Neue", 11), width=22).pack(side="left", padx=(0, 12))
        tk.Button(serial_row, text="🔍  Auto-Detect", bg=COLORS["accent2"], fg="white",
                  font=("Helvetica Neue", 10), relief="flat", bd=0, padx=10, pady=4,
                  cursor="hand2", activebackground=COLORS["accent"],
                  command=self._smart_detect).pack(side="left")

        # Artwork
        self._section_label(inner, "Artwork")
        art_card = self._card_frame(inner)
        self._file_row(art_card, "Custom icon:", self.icon_path, self._pick_icon,
                       hint="Leave blank to auto-download cover art from the internet.")
        art_btn_row = tk.Frame(art_card, bg=COLORS["card"])
        art_btn_row.pack(fill="x", pady=(8, 2))
        tk.Label(art_btn_row, text="", bg=COLORS["card"], width=22).pack(side="left")
        tk.Button(art_btn_row, text="🎨  Artwork Manager", bg=COLORS["accent2"], fg="white",
                  font=("Helvetica Neue", 10, "bold"), relief="flat", bd=0, padx=12, pady=5,
                  cursor="hand2", activebackground=COLORS["accent"],
                  command=self._open_artwork_manager).pack(side="left")

        # Output
        self._section_label(inner, "Output")
        out_card = self._card_frame(inner)
        self._file_row(out_card, "Output folder:", self.output_dir, self._pick_output)
        self._file_row(out_card, "Redump DAT/XML:", self.redump_path, self._pick_redump,
                       hint="Optional — improves serial detection via MD5 matching.")
        extra_row = tk.Frame(out_card, bg=COLORS["card"])
        extra_row.pack(fill="x", pady=4)
        tk.Label(extra_row, text="Extra emulator args:", bg=COLORS["card"], fg=COLORS["text_dim"],
                 font=("Helvetica Neue", 10), width=22, anchor="w").pack(side="left")
        tk.Entry(extra_row, textvariable=self.extra_args, bg=COLORS["input_bg"], fg=COLORS["text"],
                 insertbackground=COLORS["text"], relief="flat", bd=0,
                 font=("Helvetica Neue", 11)).pack(side="left", fill="x", expand=True)

        # Bottom section - Fixed preview in bottom left corner
        preview_frame = tk.Frame(frame, bg=COLORS["bg"])
        preview_frame.pack(fill="x", padx=16, pady=(8, 12))
        
        tk.Label(preview_frame, text="Cover Art", bg=COLORS["bg"], fg=COLORS["text_dim"],
                font=("Helvetica Neue", 8, "bold")).pack(anchor="w")
        
        self._single_preview_canvas = tk.Canvas(preview_frame, bg=COLORS["input_bg"], 
                                               width=self._preview_dims()[0], height=self._preview_dims()[1],
                                               highlightthickness=1, highlightbackground=COLORS["border"])
        self._single_preview_canvas.pack(anchor="w", pady=(2, 0))
        self._single_preview_image = None

    def _build_batch_tab(self, notebook):
        frame = tk.Frame(notebook, bg=COLORS["bg"])
        notebook.add(frame, text="  Batch Build  ")

        # Top section - ROM folder controls
        top_frame = tk.Frame(frame, bg=COLORS["bg"])
        top_frame.pack(fill="x", padx=16, pady=(12, 8))

        self._section_label(top_frame, "ROM Folder")
        batch_card = self._card_frame(top_frame)
        self._file_row(batch_card, "ROM folder:", self.batch_folder, self._pick_batch_folder)
        self._check_row(batch_card, "Scan subfolders recursively", self.batch_recursive)

        btn_row = tk.Frame(batch_card, bg=COLORS["card"])
        btn_row.pack(fill="x", pady=(10, 4))
        tk.Button(btn_row, text="🔍  Scan Folder", bg=COLORS["card_hover"], fg=COLORS["text"],
                  font=("Helvetica Neue", 11), relief="flat", bd=0, padx=12, pady=6,
                  cursor="hand2", command=self._auto_scan_batch).pack(side="left", padx=(0, 8))
        tk.Button(btn_row, text="♻  Refresh Databases", bg=COLORS["card_hover"], fg=COLORS["text"],
                  font=("Helvetica Neue", 11), relief="flat", bd=0, padx=12, pady=6,
                  cursor="hand2", command=self._refresh_databases).pack(side="left")

        # Middle section - ROM list (takes most of space)
        list_section = tk.Frame(frame, bg=COLORS["bg"])
        list_section.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        
        self._section_label(list_section, "Scanned ROMs")
        list_card = tk.Frame(list_section, bg=COLORS["card"], padx=16, pady=12)
        list_card.pack(fill="both", expand=True, pady=(0, 0))

        list_scroll = tk.Scrollbar(list_card)
        list_scroll.pack(side="right", fill="y")
        self._batch_list = tk.Listbox(list_card, bg=COLORS["log_bg"], fg=COLORS["text"],
                                      selectbackground=COLORS["accent"],
                                      font=("Courier New", 10), relief="flat", bd=0,
                                      yscrollcommand=list_scroll.set)
        self._batch_list.pack(fill="both", expand=True)
        self._batch_list.bind("<<ListboxSelect>>", self._on_batch_rom_select)
        list_scroll.config(command=self._batch_list.yview)

        # Bottom section - Count label and small preview thumbnail
        bottom_frame = tk.Frame(frame, bg=COLORS["bg"])
        bottom_frame.pack(fill="x", padx=16, pady=(0, 12))

        self._batch_count_label = tk.Label(bottom_frame, text="No ROMs scanned yet.",
                                           bg=COLORS["bg"], fg=COLORS["text_dim"],
                                           font=("Helvetica Neue", 10))
        self._batch_count_label.pack(anchor="w", pady=(4, 8))

        # Bottom left - Small preview thumbnail
        preview_container = tk.Frame(bottom_frame, bg=COLORS["bg"])
        preview_container.pack(anchor="w")
        
        tk.Label(preview_container, text="Cover Art", bg=COLORS["bg"], fg=COLORS["text_dim"],
                font=("Helvetica Neue", 8, "bold")).pack(anchor="w")
        
        self._batch_preview_canvas = tk.Canvas(preview_container, bg=COLORS["input_bg"], 
                                              width=self._preview_dims()[0], height=self._preview_dims()[1],
                                              highlightthickness=1, highlightbackground=COLORS["border"])
        self._batch_preview_canvas.pack(pady=(2, 0))
        self._batch_preview_image = None

    def _build_options_tab(self, notebook):
        frame = tk.Frame(notebook, bg=COLORS["bg"])
        notebook.add(frame, text="  Options  ")
        canvas = tk.Canvas(frame, bg=COLORS["bg"], highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        inner = tk.Frame(canvas, bg=COLORS["bg"])
        canvas.create_window((0, 0), window=inner, anchor="nw")

        self._section_label(inner, "Build Behaviour")
        opt_card = self._card_frame(inner)
        self._check_row(opt_card, "Auto-download cover art (Libretro / SteamGridDB)", self.auto_cover)
        self._check_row(opt_card, "Create KDE desktop launcher after build", self.create_launcher)
        self._check_row(opt_card, "Fast launch — play ROM directly from AppImage mount (no copy)", self.fast_launch)
        self._check_row(opt_card, "Patch AppImages without creating .bak backup files", self.no_patch_backups)

        self._ext_rom_frame = self._check_row(opt_card, "Keep ROM external — AppImage has only emulator + launcher (uncheck to inject/embed the full game, incl. PS3 folders)", self.external_rom)
        self._build_both_frame = self._check_row(opt_card, "Build both: one embedded AppImage AND one external AppImage", self.build_both)

    def _build_log_tab(self, notebook):
        frame = tk.Frame(notebook, bg=COLORS["bg"])
        notebook.add(frame, text="  Build Log  ")

        toolbar = tk.Frame(frame, bg=COLORS["bg"])
        toolbar.pack(fill="x", pady=(8, 4))
        tk.Button(toolbar, text="Clear Log", bg=COLORS["card"], fg=COLORS["text"],
                  font=("Helvetica Neue", 10), relief="flat", bd=0, padx=10, pady=4,
                  cursor="hand2", command=lambda: self._log_widget.delete("1.0", "end")
                  ).pack(side="right")
        tk.Label(toolbar, text="Build output", bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=("Helvetica Neue", 10)).pack(side="left")

        log_frame = tk.Frame(frame, bg=COLORS["log_bg"])
        log_frame.pack(fill="both", expand=True)
        scroll = tk.Scrollbar(log_frame)
        scroll.pack(side="right", fill="y")
        self._log_widget = tk.Text(log_frame, bg=COLORS["log_bg"], fg=COLORS["log_fg"],
                                   insertbackground=COLORS["text"],
                                   font=("Courier New", 10), relief="flat", bd=0,
                                   state="normal", yscrollcommand=scroll.set,
                                   wrap="word", padx=12, pady=12)
        self._log_widget.pack(fill="both", expand=True)
        scroll.config(command=self._log_widget.yview)
        self._log_widget.tag_configure("success", foreground=COLORS["success"])
        self._log_widget.tag_configure("error",   foreground=COLORS["danger"])
        self._log_widget.tag_configure("warn",    foreground=COLORS["warning"])
        self._log_widget.tag_configure("dim",     foreground=COLORS["text_dim"])

    # ── Logging ───────────────────────────────────────────────────────────────

    def log(self, msg: str, tag: str = ""):
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        if not tag:
            if msg.startswith("  ✓"):
                tag = "success"
            elif msg.startswith("  ✗") or "ERROR" in msg.upper() or "FAILED" in msg.upper():
                tag = "error"
            elif msg.startswith("  ") and not msg.startswith("  ▸"):
                tag = "dim"
        self._log_widget.insert("end", line, tag)
        self._log_widget.see("end")
        self.update_idletasks()
        # Also write to log file
        try:
            with LOG_FILE.open("a", errors="ignore") as f:
                f.write(line)
        except Exception:
            pass

    def _set_status(self, text: str, color: str = None):
        self._status_label.configure(text=text, fg=color or COLORS["text_dim"])
        self.update_idletasks()

    # ── File pickers ──────────────────────────────────────────────────────────

    def _update_single_preview(self):
        """Update the cover art preview for the single ROM tab"""
        try:
            rom_path = Path(self.rom_path.get())
            if not rom_path.exists():
                self._clear_preview(self._single_preview_canvas)
                return
            
            plat = self.platform.get()
            serial = self.serial.get().strip() or None
            title = detect_internal_title(plat, rom_path)
            
            # Try to get cover
            cover_file = CACHE_DIR / "preview_cover.png"
            cover_file.parent.mkdir(parents=True, exist_ok=True)
            
            if serial and plat in ("PS1", "PS2", "PSP", "PS3"):
                title = title or lookup_title(plat, serial)
            
            if download_cover(plat, serial, title or rom_path.stem, cover_file):
                self._display_preview(self._single_preview_canvas, cover_file)
            else:
                self._clear_preview(self._single_preview_canvas)
        except Exception as e:
            self._clear_preview(self._single_preview_canvas)
    
    def _on_batch_rom_select(self, event):
        """Handle batch ROM selection to show preview"""
        selection = self._batch_list.curselection()
        if not selection:
            self._clear_preview(self._batch_preview_canvas)
            return
        
        try:
            item = self.scanned_batch[selection[0]]
            rom_path = item["rom"]
            serial = item["serial"]
            plat = self.platform.get()
            title = item["app_name"]
            
            cover_file = CACHE_DIR / "preview_cover_batch.png"
            cover_file.parent.mkdir(parents=True, exist_ok=True)
            
            if download_cover(plat, serial, title, cover_file):
                self._display_preview(self._batch_preview_canvas, cover_file)
            else:
                self._clear_preview(self._batch_preview_canvas)
        except Exception as e:
            self._clear_preview(self._batch_preview_canvas)
    
    def _display_preview(self, canvas, image_path):
        """Display an image on the preview canvas"""
        try:
            from PIL import Image, ImageTk
            img = Image.open(image_path)
            # Get canvas size and fit image appropriately
            canvas_width = canvas.winfo_width()
            canvas_height = canvas.winfo_height()
            if canvas_width < 100:  # Small thumbnail (batch tab)
                img.thumbnail((canvas_width - 4, canvas_height - 4), Image.Resampling.LANCZOS)
                center_x = canvas_width // 2
                center_y = canvas_height // 2
            else:  # Large preview (single tab)
                img.thumbnail((canvas_width - 8, canvas_height - 8), Image.Resampling.LANCZOS)
                center_x = canvas_width // 2
                center_y = canvas_height // 2
            
            photo = ImageTk.PhotoImage(img)
            canvas.delete("all")
            canvas.create_image(center_x, center_y, image=photo)
            canvas.image = photo  # Keep a reference
        except Exception:
            self._clear_preview(canvas)
    
    def _clear_preview(self, canvas):
        """Clear the preview canvas"""
        canvas.delete("all")
        pw, ph = self._preview_dims()
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()
        center_x = canvas_width // 2 if canvas_width > 1 else pw // 2
        center_y = canvas_height // 2 if canvas_height > 1 else ph // 2
        canvas.create_text(center_x, center_y, text="No preview", 
                          fill=COLORS["text_dim"], font=("Helvetica Neue", 8 if pw < 100 else 10))

    def _initial_dir(self, val="") -> str:
        if val:
            p = Path(val)
            if p.is_file():
                return str(p.parent)
            if p.is_dir():
                return str(p)
        return DEFAULT_START_DIR

    def _pick_emulator(self):
        p = filedialog.askopenfilename(initialdir=self._initial_dir(self.emulator_path.get()),
                                       filetypes=[("AppImage", "*.AppImage"), ("All files", "*.*")])
        if p:
            self.emulator_path.set(p)

    def _ask_file_or_folder(self, plat: str) -> str | None:
        """Ask the user whether to pick a ROM file or a game folder.
        Returns 'file', 'folder', or None if cancelled."""
        dlg = tk.Toplevel(self)
        dlg.title("Select ROM / AppImage Type")
        dlg.transient(self)
        dlg.resizable(False, False)
        dlg.configure(bg=COLORS["bg"])
        dlg.grab_set()

        choice = {"value": None}

        if plat == "WiiU":
            prompt = "Wii U: pick a ROM / AppImage file (.wux/.wud/.iso/.AppImage)\nor an extracted game folder (with code/ and meta/)?"
            file_label = "ROM / AppImage File (.wux/.wud/.AppImage)"
        else:  # PS3
            prompt = "PS3: pick a ROM / AppImage file (.iso/.pkg/.AppImage)\nor an extracted game folder (with PS3_GAME)?"
            file_label = "ROM / AppImage File (.iso/.pkg/.AppImage)"

        tk.Label(dlg, text=prompt, bg=COLORS["bg"], fg=COLORS["text"],
                 justify="center", padx=20, pady=16).pack()

        btn_frame = tk.Frame(dlg, bg=COLORS["bg"])
        btn_frame.pack(padx=20, pady=(0, 16))

        def choose(val):
            choice["value"] = val
            dlg.destroy()

        tk.Button(btn_frame, text=file_label, width=32,
                  command=lambda: choose("file")).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Game Folder", width=16,
                  command=lambda: choose("folder")).pack(side="left", padx=6)

        # Center on parent
        dlg.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - dlg.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{x}+{y}")

        self.wait_window(dlg)
        return choice["value"]

    def _pick_rom_file(self, plat: str):
        """Open a file picker for the given platform's ROM extensions."""
        exts = PLATFORMS[plat]["exts"]
        patterns = " ".join(f"*{e}" for e in sorted(exts)) + " *.AppImage *.appimage"
        ftypes = [("ROM/AppImage files", patterns), ("AppImages", "*.AppImage *.appimage"), ("All files", "*.*")]
        p = filedialog.askopenfilename(initialdir=self._initial_dir(self.rom_path.get()), filetypes=ftypes)
        if p:
            self.rom_path.set(p)
            self.app_name.set(Path(p).stem)
            self._smart_detect()
            self._update_single_preview()

    def _pick_ps3_folder(self):
        p = filedialog.askdirectory(initialdir=self._initial_dir(self.rom_path.get()))
        if p:
            rom_path = Path(p)
            if (rom_path / "PS3_GAME").exists():
                self.rom_path.set(p)
                self.app_name.set(rom_path.name)
                self._smart_detect()
                self._update_single_preview()
            else:
                messagebox.showerror("Invalid PS3 Folder", "Selected folder must contain PS3_GAME subdirectory")

    def _pick_wiiu_folder(self):
        p = filedialog.askdirectory(initialdir=self._initial_dir(self.rom_path.get()))
        if p:
            rom_path = Path(p)
            has_code = (rom_path / "code").exists()
            has_meta = (rom_path / "meta").exists()
            if has_code or has_meta:
                if has_code:
                    rpx_files = list((rom_path / "code").glob("*.rpx"))
                    if not rpx_files:
                        messagebox.showerror("Invalid Wii U Folder", "Selected folder has code/ but no .rpx files found")
                        return
                self.rom_path.set(p)
                self.app_name.set(rom_path.name)
                self._smart_detect()
                self._update_single_preview()
            else:
                messagebox.showerror("Invalid Wii U Folder", "Selected folder must contain code/ and/or meta/ subdirectory")

    def _pick_rom(self):
        plat = self.platform.get()

        # PS3 and Wii U support BOTH a ROM file and an extracted game folder.
        if plat in ("PS3", "WiiU"):
            kind = self._ask_file_or_folder(plat)
            if kind == "file":
                self._pick_rom_file(plat)
            elif kind == "folder":
                if plat == "PS3":
                    self._pick_ps3_folder()
                else:
                    self._pick_wiiu_folder()
            # None = cancelled, do nothing
        else:
            # All other platforms use file selection only
            self._pick_rom_file(plat)

    def _open_artwork_manager(self):
        rom = Path(self.rom_path.get()) if self.rom_path.get() else None
        plat = self.platform.get()
        is_ps3_folder = bool(rom and plat == "PS3" and rom.is_dir() and (rom / "PS3_GAME").exists())
        is_wiiu_folder = bool(rom and plat == "WiiU" and rom.is_dir() and ((rom / "code").exists() or (rom / "meta").exists()))
        if not rom or (not rom.is_file() and not is_ps3_folder and not is_wiiu_folder):
            messagebox.showinfo(
                "Select ROM First",
                "Select a ROM or .AppImage in the ROM file field for the current platform first.\n\n"
                "The Artwork Manager uses the currently selected platform and that file as its target.",
            )
            return
        ArtworkManager(self)

    def _pick_icon(self):
        p = filedialog.askopenfilename(initialdir=self._initial_dir(self.icon_path.get()),
                                       filetypes=[("Images", "*.png *.jpg *.jpeg"), ("All files", "*.*")])
        if p:
            self.icon_path.set(p)

    def _pick_redump(self):
        p = filedialog.askopenfilename(initialdir=self._initial_dir(self.redump_path.get()),
                                       filetypes=[("DAT/XML", "*.dat *.xml"), ("All files", "*.*")])
        if p:
            self.redump_path.set(p)

    def _pick_output(self):
        p = filedialog.askdirectory(initialdir=self._initial_dir(self.output_dir.get()))
        if p:
            self.output_dir.set(p)

    def _pick_batch_folder(self):
        p = filedialog.askdirectory(initialdir=self._initial_dir(self.batch_folder.get()))
        if p:
            self.batch_folder.set(p)

    # ── Detection ─────────────────────────────────────────────────────────────

    def _smart_detect(self):
        rom = Path(self.rom_path.get())
        plat = self.platform.get()
        is_ps3_folder = (plat == "PS3" and rom.is_dir() and (rom / "PS3_GAME").exists())
        is_wiiu_folder = (plat == "WiiU" and rom.is_dir() and ((rom / "code").exists() or (rom / "meta").exists()))
        if is_appimage_path(rom) and rom.is_file():
            self.app_name.set(sanitize_name(rom.stem))
            self.serial.set("")
            self.log(f"Auto-detecting AppImage target: {rom.name}")
            return
        if not rom.is_file() and not is_ps3_folder and not is_wiiu_folder:
            return
        self.log(f"Auto-detecting: {rom.name}")
        serial = detect_serial(plat, rom)
        title = detect_internal_title(plat, rom)
        if serial and plat in ("PS1", "PS2", "PSP", "PS3"):
            title = title or lookup_title(plat, serial)
        if serial:
            self.serial.set(serial)
            self.log(f"  Serial: {serial}")
        if title:
            self.app_name.set(sanitize_name(title))
            self.log(f"  Title:  {title}")
        # Try redump (file-based ROMs only — folders have no single MD5)
        redump = Path(self.redump_path.get())
        if rom.is_file() and redump.is_file() and (not serial or not title):
            try:
                result = redump_lookup(redump, md5sum(rom))
                if result:
                    if not serial:
                        self.serial.set(result.get("serial") or "")
                    if not title:
                        self.app_name.set(sanitize_name(result.get("game") or rom.stem))
                    self.log("  Redump match found.")
            except Exception as e:
                self.log(f"  Redump lookup failed: {e}", "warn")
        if not title and not serial:
            self.log("  No match found — using filename.", "warn")

    # ── Batch scan ────────────────────────────────────────────────────────────

    def _auto_scan_batch(self):
        folder = Path(self.batch_folder.get())
        if not folder.is_dir():
            messagebox.showerror("Error", "Select a valid ROM folder first.")
            return
        plat = self.platform.get()
        exts = PLATFORMS[plat]["exts"]
        data_exts = PLATFORMS[plat]["data_exts"]
        self.log(f"Scanning {folder} for {plat} ROMs…")
        self._batch_list.delete(0, "end")
        self.scanned_batch = []
        glob = "**/*" if self.batch_recursive.get() else "*"
        
        candidates = []
        
        # For PS3, also look for game folders (containing PS3_GAME)
        if plat == "PS3":
            for item in folder.glob(glob):
                if item.is_dir() and (item / "PS3_GAME").exists():
                    candidates.append(item)
        
        # For Wii U, also look for game folders (containing code/ and/or meta/)
        if plat == "WiiU":
            for item in folder.glob(glob):
                if item.is_dir() and ((item / "code").exists() or (item / "meta").exists()):
                    candidates.append(item)
        
        # Add regular file candidates
        for p in folder.glob(glob):
            if p.is_file() and p.suffix.lower() in exts and p.suffix.lower() not in data_exts:
                candidates.append(p)
        
        candidates = sorted(set(candidates))  # Remove duplicates and sort
        
        for rom in candidates:
            serial = detect_serial(plat, rom)
            title = detect_internal_title(plat, rom)
            if serial and plat in ("PS1", "PS2", "PSP", "PS3"):
                title = title or lookup_title(plat, serial)
            name = sanitize_name(title or rom.stem)
            self.scanned_batch.append({"rom": rom, "app_name": name, "serial": serial})
            rom_type = "folder" if rom.is_dir() else rom.suffix.lower()
            self._batch_list.insert("end", f"  {name}  [{rom.name}] ({rom_type})")
        count = len(self.scanned_batch)
        self._batch_count_label.configure(text=f"{count} ROM{'s' if count != 1 else ''} found.")
        self.log(f"Scan complete — {count} ROM(s) found.")
        self._clear_preview(self._batch_preview_canvas)

    # ── Database refresh ──────────────────────────────────────────────────────

    def _refresh_databases(self):
        plat = self.platform.get()
        self.log("Refreshing title database…")
        try:
            load_title_db(plat, force=True)
            self.log("  ✓ Title database refreshed.")
        except Exception as e:
            self.log(f"  ✗ Database error: {e}", "error")

    # ── Build actions ─────────────────────────────────────────────────────────

    def _validate_common(self) -> bool:
        if not Path(self.emulator_path.get()).is_file():
            messagebox.showerror("Missing Emulator", "Please select the emulator AppImage.")
            return False
        if not Path(self.output_dir.get()).is_dir():
            messagebox.showerror("Missing Output Folder", "Please select an output folder.")
            return False
        return True

    def _request_stop(self):
        self.stop_requested = True
        self._set_status("Stopping…", COLORS["warning"])
        self.log("⏹  Stop requested.")

    def _build_single(self):
        if self._build_in_progress:
            messagebox.showwarning("Build in Progress", "A build is already running.")
            return
        if not self._validate_common():
            return
        rom = Path(self.rom_path.get())
        plat = self.platform.get()
        # PS3 accepts a game folder (containing PS3_GAME); Wii U accepts a game folder (containing code/ and/or meta/); everything else needs a file
        is_ps3_folder = (plat == "PS3" and rom.is_dir() and (rom / "PS3_GAME").exists())
        is_wiiu_folder = (plat == "WiiU" and rom.is_dir() and ((rom / "code").exists() or (rom / "meta").exists()))
        
        # Additional validation for Wii U: must have .rpx file
        if is_wiiu_folder and not _find_wiiu_rpx(rom):
            messagebox.showerror("Missing .rpx", "No .rpx file found in code/ folder.\nMake sure the Wii U game folder has code/ with at least one .rpx file.")
            return
        
        if not rom.is_file() and not is_ps3_folder and not is_wiiu_folder:
            if plat == "PS3":
                messagebox.showerror("Missing ROM", "Select a PS3 .iso/.pkg file, or a game folder containing PS3_GAME.")
            elif plat == "WiiU":
                messagebox.showerror("Missing ROM", "Select a Wii U .wud/.wux/.iso file, or a game folder with code/ containing .rpx files.")
            else:
                messagebox.showerror("Missing ROM", "Please select a ROM file.")
            return
        self.stop_requested = False
        app_name = sanitize_name(self.app_name.get() or rom.stem)
        serial = self.serial.get().strip() or None
        icon = Path(self.icon_path.get()) if self.icon_path.get() else None
        self.log(f"\n{'═'*60}")
        self.log(f"▸ BUILD SINGLE  —  {plat}  —  {app_name}")
        self._set_status("Building…", COLORS["accent"])
        self._build_in_progress = True

        def run():
            try:
                if self.build_both.get() and plat in ("GameCube", "Xbox", "PSP", "PS3", "Xbox360", "WiiU", "Switch"):
                    for ext_flag, suffix in [(False, " Embedded"), (True, " External")]:
                        if self.stop_requested:
                            break
                        build_appimage(
                            platform=plat,
                            rom=rom,
                            app_name=app_name + suffix,
                            emulator=Path(self.emulator_path.get()),
                            output_dir=Path(self.output_dir.get()),
                            serial=serial,
                            icon_path=icon,
                            auto_cover=self.auto_cover.get(),
                            fast_launch=self.fast_launch.get(),
                            external_rom=ext_flag,
                            extra_args=self.extra_args.get().strip(),
                            create_launcher=self.create_launcher.get(),
                            logger=self.log,
                            stop_check=lambda: self.stop_requested,
                        )
                else:
                    build_appimage(
                        platform=plat,
                        rom=rom,
                        app_name=app_name,
                        emulator=Path(self.emulator_path.get()),
                        output_dir=Path(self.output_dir.get()),
                        serial=serial,
                        icon_path=icon,
                        auto_cover=self.auto_cover.get(),
                        fast_launch=self.fast_launch.get(),
                        external_rom=self.external_rom.get(),
                        extra_args=self.extra_args.get().strip(),
                        create_launcher=self.create_launcher.get(),
                        logger=self.log,
                        stop_check=lambda: self.stop_requested,
                    )
                self.after(0, lambda: self._build_done("Single build complete!", success=True))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda m=msg: self._build_done(f"Build failed: {m}", success=False))

        threading.Thread(target=run, daemon=True).start()

    def _build_batch(self):
        if self._build_in_progress:
            messagebox.showwarning("Build in Progress", "A build is already running.")
            return
        if not self._validate_common():
            return
        if not self.scanned_batch:
            self._auto_scan_batch()
        if not self.scanned_batch:
            messagebox.showinfo("No ROMs", "No ROMs were found. Check the batch folder and scan first.")
            return
        self.stop_requested = False
        plat = self.platform.get()
        self.log(f"\n{'═'*60}")
        self.log(f"▸ BUILD BATCH  —  {plat}  —  {len(self.scanned_batch)} ROMs")
        self._set_status("Batch building…", COLORS["accent"])
        self._build_in_progress = True

        def run():
            built = failed = 0
            for i, item in enumerate(self.scanned_batch, 1):
                if self.stop_requested:
                    self.after(0, lambda: self.log("⏹  Batch stopped by user."))
                    break
                self.after(0, lambda n=item["app_name"], idx=i, total=len(self.scanned_batch):
                           self.log(f"\n[{idx}/{total}] {n}"))
                self.after(0, lambda n=item["app_name"], idx=i, total=len(self.scanned_batch):
                           self._set_status(f"[{idx}/{total}] {n}", COLORS["accent"]))
                try:
                    build_appimage(
                        platform=plat,
                        rom=item["rom"],
                        app_name=item["app_name"],
                        emulator=Path(self.emulator_path.get()),
                        output_dir=Path(self.output_dir.get()),
                        serial=item["serial"],
                        icon_path=None,
                        auto_cover=self.auto_cover.get(),
                        fast_launch=self.fast_launch.get(),
                        external_rom=self.external_rom.get(),
                        extra_args=self.extra_args.get().strip(),
                        create_launcher=self.create_launcher.get(),
                        logger=self.log,
                        stop_check=lambda: self.stop_requested,
                    )
                    built += 1
                except Exception as e:
                    failed += 1
                    self.after(0, lambda m=str(e): self.log(f"  ✗ FAILED: {m}", "error"))
            self.after(0, lambda: self._build_done(
                f"Batch complete — ✓ {built} built, ✗ {failed} failed", success=failed == 0
            ))

        threading.Thread(target=run, daemon=True).start()


    def _patch_appimages(self):
        if self._build_in_progress:
            messagebox.showwarning("Build in Progress", "A build or patch is already running.")
            return
        paths = filedialog.askopenfilenames(
            title="Select Rom2App AppImages to patch",
            initialdir=self.output_dir.get() or str(Path.home()),
            filetypes=[("AppImages", "*.AppImage"), ("All files", "*")],
        )
        if not paths:
            folder = filedialog.askdirectory(
                title="Or select a folder to patch all .AppImage files inside",
                initialdir=self.output_dir.get() or str(Path.home()),
            )
            if not folder:
                return
            paths = sorted(str(p) for p in Path(folder).glob("*.AppImage"))
            if not paths:
                messagebox.showinfo("No AppImages", "No .AppImage files were found in that folder.")
                return

        self.stop_requested = False
        self._build_in_progress = True
        self._set_status("Patching AppImages…", COLORS["accent"])
        self.log(f"\n{'═'*60}")
        self.log(f"▸ PATCH APPIMAGES  —  {len(paths)} file(s)")

        def run():
            patched = skipped = failed = 0
            for i, path in enumerate(paths, 1):
                if self.stop_requested:
                    self.after(0, lambda: self.log("⏹  Patch stopped by user."))
                    break
                self.after(0, lambda idx=i, total=len(paths), name=Path(path).name:
                           self._set_status(f"[{idx}/{total}] {name}", COLORS["accent"]))
                try:
                    changed = patch_existing_appimage(
                        Path(path),
                        logger=lambda m: self.after(0, lambda msg=m: self.log(msg)),
                        stop_check=lambda: self.stop_requested,
                        create_backup=not self.no_patch_backups.get(),
                    )
                    if changed:
                        patched += 1
                    else:
                        skipped += 1
                except Exception as e:
                    failed += 1
                    self.after(0, lambda m=str(e), n=Path(path).name: self.log(f"  ✗ {n}: {m}", "error"))
            self.after(0, lambda: self._build_done(
                f"Patch complete — ✓ {patched} patched, ↷ {skipped} skipped, ✗ {failed} failed",
                success=failed == 0,
            ))

        threading.Thread(target=run, daemon=True).start()

    def _build_done(self, msg: str, success: bool):
        self._build_in_progress = False
        color = COLORS["success"] if success else COLORS["danger"]
        self._set_status(msg[:40] + "…" if len(msg) > 40 else msg, color)
        self.log(f"\n{'═'*60}")
        self.log(msg, "success" if success else "error")
        if success:
            messagebox.showinfo("Done", msg)
        else:
            messagebox.showerror("Build Failed", msg)


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        import subprocess, sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "--break-system-packages", "-q"])
        from PIL import Image, ImageDraw

    app = Rom2App()
    app.mainloop()
