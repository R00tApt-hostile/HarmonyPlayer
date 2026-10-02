# Harmony Pro

A desktop music player built with Python, PyQt5, and libVLC.

## Overview

Harmony Pro is a local music player for Windows, macOS, and Linux. It uses libVLC for playback and PyQt5 for the interface, and supports common lossless and lossy audio formats.

## Features

- Playback of MP3, FLAC, WAV, OGG, M4A, and AAC files
- 10-band equalizer with 17 presets
- Five built-in color themes plus a custom theme editor
- Adjustable accent color, font size, and window opacity
- Playlist management with folder scanning
- System tray controls
- Configurable keyboard shortcuts
- Persistent settings via INI file

## Requirements

- Python 3.8 or later
- VLC media player (3.0 or later) installed on the system
- PyQt5
- python-vlc
- requests

## Installation

### 1. Install VLC

| Platform | Command |
|----------|---------|
| Windows | Download from https://www.videolan.org/vlc/ |
| macOS | `brew install --cask vlc` |
| Ubuntu/Debian | `sudo apt install vlc libvlc-dev` |
| Fedora | `sudo dnf install vlc` |
| Arch | `sudo pacman -S vlc` |

### 2. Clone the repository

```bash
git clone https://github.com/yourusername/harmony-pro.git
cd harmony-pro
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install PyQt5 python-vlc requests
```

### 4. Run

```bash
python harmony_player.py
```

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Play / Pause | Space |
| Next track | Ctrl + Right |
| Previous track | Ctrl + Left |
| Volume up | Ctrl + Up |
| Volume down | Ctrl + Down |
| Mute / Unmute | Ctrl + M |

Media keys (Play, Next, Previous) are also supported where the platform provides them.

## Configuration

Settings are stored at `~/.harmony_player.ini`.

```ini
[audio]
volume = 70
crossfade = 0
eq_preset = flat
replaygain = false
normalization = true

[appearance]
theme = dark
font_size = 12
accent_color = #1db954
window_opacity = 100
custom_theme = {}

[playback]
repeat = none
shuffle = false
crossfade_duration = 3
fade_on_pause = true

[lyrics]
auto_fetch = true
font_size = 16
alignment = center
```

Delete the file to restore defaults.

## Project Structure

```
harmony-pro/
├── harmony_player.py      Main application
├── requirements.txt       Python dependencies
├── harmony_player.log     Runtime log (generated)
├── README.md
└── docs/                  Screenshots and assets
```

## Known Limitations

- Crossfade is a linear fade, not a true overlapping dual-player transition.
- Lyrics fetching is not implemented.
- Hotkeys are scoped to the application window, not system-wide.
- Equalizer support depends on the local VLC build.

## Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/name`
3. Commit your changes.
4. Push the branch and open a pull request.

Follow PEP 8 and use 4-space indentation. Describe what the change does in the pull request.

## Acknowledgements

- VideoLAN, for libVLC
- Riverbank Computing, for PyQt5