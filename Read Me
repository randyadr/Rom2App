# 🎮 Rom2App

**Rom2App** is a powerful Linux desktop application that transforms your game ROMs into standalone AppImages, allowing your retro and modern console games to behave like native applications on your system.

Instead of opening an emulator and browsing for a game every time you want to play, Rom2App creates a dedicated launcher for each game. The resulting AppImage contains everything needed to launch that title with your chosen emulator, complete with artwork, desktop integration, and custom icons.

Whether you're building a polished retro-gaming collection, integrating games into Steam, or simply want one-click access to your favorite titles, Rom2App automates the entire process.

---

## ✨ What Rom2App Does

Rom2App takes a ROM, disc image, or supported game folder and:

- Detects the platform automatically
- Extracts game information where possible
- Identifies game serial numbers and title IDs
- Downloads high-quality box art and cover images
- Creates custom launcher icons
- Builds a portable Linux AppImage
- Integrates with KDE, GNOME, XFCE, and other desktop environments
- Allows games to launch directly from menus, desktop shortcuts, file managers, or Steam

The result is a clean and organized gaming library that feels like a collection of native Linux applications.

---

## 🚀 Features

### 🎮 Multi-Platform Support

Rom2App currently supports:

| Platform | Supported Formats |
|-----------|------------------|
| PlayStation 1 | CUE, BIN, CHD, PBP |
| PlayStation 2 | ISO, BIN, CHD, CSO |
| PlayStation Portable | ISO, CSO, CHD, PBP |
| Nintendo GameCube | ISO, RVZ, GCM, GCZ |
| Original Xbox | ISO, XISO |
| PlayStation 3 | ISO, PKG, Extracted Games |
| Xbox 360 | ISO, XEX, ZAR |
| Nintendo Wii U | WUD, WUX, RPX, WUA |
| Nintendo Switch | NSP, XCI, NCA, NRO |

---

### 🖼️ Automatic Artwork Downloading

Rom2App automatically searches multiple online databases to find artwork for your games.

Artwork sources include:

- SteamGridDB
- Xlenore Cover Collections
- Libretro Thumbnail Repository
- Platform-specific title databases

If artwork cannot be found, Rom2App can generate platform-themed placeholder icons automatically.

---

### 🔍 Intelligent Game Identification

The application contains advanced game detection systems capable of:

- Reading disc serial numbers
- Detecting PlayStation title IDs
- Identifying Xbox Title IDs
- Reading GameCube internal game titles
- Parsing Wii U metadata
- Reading PS3 PARAM.SFO information
- Detecting Nintendo Switch Title IDs

This allows artwork and metadata retrieval even when ROM filenames are incorrect.

---

### 📦 Standalone AppImage Creation

Every generated launcher becomes a self-contained AppImage.

Benefits include:

- Portable deployment
- No installation required
- Native Linux application behavior
- Easy backup and sharing
- Distribution-independent compatibility

Generated AppImages can be moved anywhere and launched on virtually any modern Linux distribution.

---

### 🖥️ Desktop Integration

Rom2App automatically installs:

- Application menu entries
- Desktop launchers
- High-resolution icons
- KDE launcher integration
- GNOME launcher integration
- XFCE launcher integration

Games appear alongside normal applications and can be searched directly from your desktop environment.

---

### 🎨 Modern User Interface

The application includes a fully themed interface with numerous built-in color schemes:

- Midnight
- Dracula
- Nord
- Tokyo Night
- Gruvbox Dark
- Catppuccin Mocha
- Solarized Dark
- OneDark Pro
- Material Darker
- Synthwave
- Forest Green
- Ocean Blue
- High Contrast
- Pastel Dreams
- Cherry
- Light Mode

Switch themes instantly without restarting the application.

---

### ⚡ Advanced ROM Handling

Rom2App supports complex game structures including:

#### Multi-Disc Games

Automatically handles:

```text
Game.cue
Game (Track 1).bin
Game (Track 2).bin
Game (Track 3).bin
```

#### PS3 Extracted Games

Supports folder structures:

```text
Game Folder/
└── PS3_GAME/
    ├── USRDIR/
    ├── TROPDIR/
    └── PARAM.SFO
```

#### Wii U Game Folders

Supports:

```text
Game Folder/
├── code/
├── content/
└── meta/
```

#### Nintendo Switch Games

Supports:

```text
NSP
XCI
NCA
NRO
```

without extraction requirements.

---

## 🖥️ Supported Emulators

Rom2App is designed to work with popular Linux emulators.

| Platform | Emulator |
|-----------|-----------|
| PS1 | DuckStation |
| PS2 | PCSX2 |
| PSP | PPSSPP |
| GameCube | Dolphin |
| Xbox | xemu |
| PS3 | RPCS3 |
| Xbox 360 | Xenia |
| Wii U | Cemu |
| Switch | Ryujinx |

---

## 📋 Requirements

### Python

- Python 3.10 or newer
- Tkinter
- Pillow

Install dependencies:

```bash
pip install pillow
```

### Linux Utilities

Required:

```bash
appimagetool
gtk-update-icon-cache
```

Optional but recommended:

```bash
kbuildsycoca5
kbuildsycoca6
```

---

## 📥 Installation

Clone the repository:

```bash
git clone https://github.com/yourusername/rom2app.git
cd rom2app
```

Install dependencies:

```bash
pip install pillow
```

Run:

```bash
python3 Rom2App.py
```

---

## 📖 Usage

### Building Your First Game Launcher

1. Launch Rom2App.
2. Select the game platform.
3. Browse to your ROM or game folder.
4. Verify the detected title.
5. Download or choose artwork.
6. Configure emulator options.
7. Click **Build AppImage**.
8. Wait for the build process to finish.

Your game will now launch like a normal desktop application.

---

## 📂 Configuration Locations

### Application Settings

```bash
~/.config/rom2app/
```

### Cover Art Cache

```bash
~/.config/rom2app/cache/
```

### Logs

```bash
~/.local/share/rom2app/
```

---

## 🛠️ AppImage Artwork Patching

Rom2App includes a built-in AppImage icon patcher.

This allows you to:

- Replace existing AppImage icons
- Update artwork after creation
- Refresh launcher graphics
- Create backups automatically
- Rebuild AppImages safely

This is especially useful for users who maintain large game collections and frequently update artwork.

---

## 📸 Screenshots

### Main Window

```markdown
![Main Window](screenshots/main-window.png)
```

### Artwork Preview

```markdown
![Artwork Preview](screenshots/artwork-preview.png)
```

### Generated AppImage

```markdown
![Generated AppImage](screenshots/generated-appimage.png)
```

---

## 🤝 Contributing

Contributions are welcome.

Examples include:

- New platform support
- Additional emulator support
- UI improvements
- Metadata database additions
- Cover-art source integrations
- Bug fixes
- Performance improvements

Pull requests and issue reports are greatly appreciated.

---

## ⚠️ Legal Notice

Rom2App does **not** contain:

- ROM files
- BIOS files
- Game assets
- Emulator binaries

Users are responsible for ensuring they legally own and are permitted to use any game backups processed by this software.

---

## 🙏 Acknowledgements

Special thanks to:

### Artwork Providers

- SteamGridDB
- Xlenore Cover Collections
- Libretro Thumbnails

### Emulator Developers

- DuckStation
- PCSX2
- PPSSPP
- Dolphin
- xemu
- RPCS3
- Xenia
- Cemu
- Ryujinx

Without their work, projects like Rom2App would not be possible.

---

## 📜 License

MIT License

See the LICENSE file for details.

---

# 🎮 Turn Your ROM Collection Into Native Linux Applications

Create beautiful launchers, automate artwork management, and launch your games with a single click.
