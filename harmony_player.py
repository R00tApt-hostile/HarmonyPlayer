import os
import sys
import logging
import configparser
import json
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
import vlc
import requests
from PyQt5.QtCore import (Qt, QUrl, QTimer, QSize, QPoint, QSettings,
                          QStandardPaths, QCoreApplication, QByteArray)
from PyQt5.QtGui import (QIcon, QPixmap, QColor, QFont, QFontDatabase,
                         QPalette, QLinearGradient, QBrush, QPainter,
                         QRadialGradient, QImage, QKeySequence)
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QSlider,
                             QListWidget, QTabWidget, QFileDialog, QComboBox,
                             QStackedWidget, QSystemTrayIcon, QMenu,
                             QMessageBox, QScrollArea, QSpacerItem, QSizePolicy,
                             QGroupBox, QCheckBox, QDoubleSpinBox, QSpinBox,
                             QLineEdit, QProgressBar, QSplitter, QFrame,
                             QColorDialog, QShortcut, QStyleFactory,
                             QGridLayout, QStyle)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('harmony_player.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
APP_NAME = "Harmony Pro"
VERSION = "1.1.0"
SUPPORTED_FORMATS = ('.mp3', '.flac', '.wav', '.ogg', '.m4a', '.aac')
CONFIG_PATH = Path.home() / '.harmony_player.ini'

DEFAULT_CONFIG = {
    'audio': {
        'volume': '70',
        'crossfade': '0',
        'eq_preset': 'flat',
        'replaygain': 'false',
        'normalization': 'true'
    },
    'appearance': {
        'theme': 'dark',
        'font_size': '12',
        'accent_color': '#1db954',
        'custom_theme': '{}',
        'window_opacity': '100'
    },
    'playback': {
        'repeat': 'none',
        'shuffle': 'false',
        'crossfade_duration': '3',
        'fade_on_pause': 'true'
    },
    'lyrics': {
        'auto_fetch': 'true',
        'font_size': '16',
        'alignment': 'center'
    }
}

# Built-in color themes
THEMES = {
    'dark': {
        'base': '#121212',
        'text': '#ffffff',
        'highlight': '#1db954',
        'button': '#282828',
        'panel': '#181818'
    },
    'light': {
        'base': '#f5f5f5',
        'text': '#333333',
        'highlight': '#1db954',
        'button': '#e0e0e0',
        'panel': '#ffffff'
    },
    'amethyst': {
        'base': '#1a1a2e',
        'text': '#e94560',
        'highlight': '#9c27b0',
        'button': '#16213e',
        'panel': '#0f3460'
    },
    'midnight': {
        'base': '#0a192f',
        'text': '#ccd6f6',
        'highlight': '#64ffda',
        'button': '#172a45',
        'panel': '#112240'
    },
    'sunset': {
        'base': '#2d3436',
        'text': '#ffeaa7',
        'highlight': '#e17055',
        'button': '#3c4245',
        'panel': '#353b3c'
    }
}


class AudioEngine:
    """Advanced audio engine using VLC with additional features"""

    def __init__(self):
        vlc_args = [
            '--no-xlib',
            '--quiet',
            '--audio-resampler', 'soxr',
            '--network-caching=3000'
        ]
        try:
            self.instance = vlc.Instance(vlc_args)
        except Exception:
            # Fallback if some options are not supported
            self.instance = vlc.Instance(['--no-xlib', '--quiet'])

        self.player = self.instance.media_player_new()
        self.current_media = None
        self.media_list = self.instance.media_list_new()
        self.list_player = self.instance.media_list_player_new()
        self.list_player.set_media_player(self.player)
        self.list_player.set_media_list(self.media_list)
        self.events = self.player.event_manager()

        # Equalizer (may be unavailable on some builds)
        try:
            self.equalizer = vlc.AudioEqualizer()
        except Exception:
            self.equalizer = None

        self.set_eq_preset('flat')

        # Crossfade state
        self.crossfade_timer = QTimer()
        self.crossfade_timer.timeout.connect(self.handle_crossfade)
        self.crossfade_duration = 3
        self.fade_out_player = None

    # ------------------------------------------------------------------ #
    # Media loading / playback
    # ------------------------------------------------------------------ #
    def load_file(self, file_path: str) -> bool:
        try:
            media = self.instance.media_new(file_path)
            try:
                media.parse()  # best-effort metadata parse
            except Exception as parse_err:
                logger.debug(f"Metadata parse skipped: {parse_err}")
            self.player.set_media(media)
            self.current_media = media
            return True
        except Exception as e:
            logger.error(f"Error loading file: {e}")
            return False

    def play(self) -> bool:
        if self.crossfade_duration > 0 and self.fade_out_player is not None:
            self.start_crossfade()
            return True
        return self.player.play() == 0

    def pause(self):
        self.player.pause()

    def stop(self):
        self.player.stop()

    def is_playing(self) -> bool:
        return self.player.is_playing() == 1

    def start_crossfade(self):
        self.crossfade_timer.start(100)
        if self.fade_out_player is not None:
            self.fade_out_player.audio_set_volume(100)
        self.player.audio_set_volume(0)
        self.player.play()

    def handle_crossfade(self):
        # Placeholder — real crossfade would interpolate both players' volumes
        if self.fade_out_player is None:
            self.crossfade_timer.stop()
            return
        current = self.player.audio_get_volume()
        if current >= 100:
            self.crossfade_timer.stop()
        else:
            self.player.audio_set_volume(min(100, current + 5))

    # ------------------------------------------------------------------ #
    # Volume / position / EQ
    # ------------------------------------------------------------------ #
    def set_volume(self, vol: int):
        self.player.audio_set_volume(int(max(0, min(100, vol))))

    def get_volume(self) -> int:
        v = self.player.audio_get_volume()
        return v if v >= 0 else 0

    def get_time(self) -> int:
        t = self.player.get_time()
        return t if t > 0 else 0

    def set_time(self, ms: int):
        self.player.set_time(int(ms))

    def get_length(self) -> int:
        l = self.player.get_length()
        return l if l > 0 else 0

    def get_position(self) -> float:
        p = self.player.get_position()
        return p if p > 0 else 0.0

    def set_position(self, pos: float):
        self.player.set_position(max(0.0, min(1.0, pos)))

    def set_eq_preset(self, preset: str):
        """Apply a named equalizer preset if supported."""
        if self.equalizer is None:
            return
        presets = {
            'flat': 0, 'classical': 1, 'club': 2, 'dance': 3,
            'full_bass': 4, 'full_bass_treble': 5, 'headphones': 6,
            'large_hall': 7, 'live': 8, 'party': 9, 'pop': 10,
            'reggae': 11, 'rock': 12, 'ska': 13, 'soft': 14,
            'soft_rock': 15, 'techno': 16
        }
        try:
            if preset == 'flat':
                self.player.audio_set_equalizer(None)
                return
            idx = presets.get(preset, 0)
            # python-vlc exposes preset count via instance; guard carefully
            count = self.equalizer.get_preset_count() if hasattr(
                self.equalizer, 'get_preset_count') else 0
            if 0 <= idx < count:
                self.equalizer.set_preset(idx)
                self.player.audio_set_equalizer(self.equalizer)
        except Exception as e:
            logger.warning(f"Could not set EQ preset '{preset}': {e}")


class ThemeEditor(QWidget):
    """Widget for customizing color themes"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Custom"] + list(THEMES.keys()))
        self.theme_combo.currentTextChanged.connect(self.theme_changed)

        color_group = QGroupBox("Theme Colors")
        color_layout = QGridLayout()

        self.color_pickers = {}
        row = 0
        for color_name in ['base', 'text', 'highlight', 'button', 'panel']:
            lbl = QLabel(color_name.capitalize())
            btn = QPushButton()
            btn.setFixedSize(60, 30)
            btn.setStyleSheet("background-color: #000000; border: none;")
            btn.clicked.connect(lambda _, c=color_name: self.pick_color(c))
            self.color_pickers[color_name] = btn

            color_layout.addWidget(lbl, row, 0)
            color_layout.addWidget(btn, row, 1)
            row += 1

        color_group.setLayout(color_layout)

        preview_group = QGroupBox("Preview")
        self.preview = QLabel()
        self.preview.setFixedHeight(100)
        preview_layout = QHBoxLayout()
        preview_layout.addWidget(self.preview)
        preview_group.setLayout(preview_layout)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Theme")
        save_btn.clicked.connect(self.save_theme)
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self.reset_theme)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(reset_btn)

        layout.addWidget(QLabel("Select Theme:"))
        layout.addWidget(self.theme_combo)
        layout.addWidget(color_group)
        layout.addWidget(preview_group)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self.theme_combo.setCurrentText('dark')
        self.update_preview()

    def _current_colors(self) -> Dict[str, str]:
        colors = {}
        for name, btn in self.color_pickers.items():
            style = btn.styleSheet()
            if 'background-color' in style:
                colors[name] = style.split(':')[1].split(';')[0].strip()
            else:
                colors[name] = '#000000'
        return colors

    def pick_color(self, color_name):
        current = self._current_colors().get(color_name, '#000000')
        color = QColorDialog.getColor(QColor(current), self, "Pick color")
        if color.isValid():
            self.color_pickers[color_name].setStyleSheet(
                f"background-color: {color.name()}; border: none;"
            )
            self.update_preview()

    def update_preview(self):
        pixmap = QPixmap(400, 100)
        painter = QPainter(pixmap)
        colors = self._current_colors()

        painter.fillRect(0, 0, 400, 100, QColor(colors['base']))

        painter.setBrush(QColor(colors['button']))
        painter.setPen(Qt.NoPen)
        painter.drawRect(20, 20, 100, 30)

        painter.setPen(QColor(colors['text']))
        painter.drawText(130, 40, "Sample Text")

        painter.setBrush(QColor(colors['highlight']))
        painter.setPen(Qt.NoPen)
        painter.drawRect(250, 20, 30, 30)

        painter.setBrush(QColor(colors['panel']))
        painter.drawRect(300, 20, 80, 60)

        painter.end()
        self.preview.setPixmap(pixmap)

    def theme_changed(self, theme_name):
        if theme_name == "Custom" or theme_name not in THEMES:
            return
        theme = THEMES[theme_name]
        for name, color in theme.items():
            btn = self.color_pickers.get(name)
            if btn:
                btn.setStyleSheet(f"background-color: {color}; border: none;")
        self.update_preview()

    def save_theme(self):
        theme = self._current_colors()
        if self.parent is not None and hasattr(self.parent, 'save_custom_theme'):
            self.parent.save_custom_theme(theme)
            QMessageBox.information(self, "Theme Saved",
                                    "Custom theme has been saved.")

    def reset_theme(self):
        self.theme_combo.setCurrentText('dark')


class MusicPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {VERSION}")
        self.setGeometry(100, 100, 1200, 800)

        # Config must be loaded before we use it
        self.config = self.load_config()

        # Core components
        self.audio_engine = AudioEngine()
        self.current_track = None
        self.current_lyrics = None
        self.current_playlist: List[str] = []
        self.current_playlist_index = 0
        self.system_tray: Optional[QSystemTrayIcon] = None
        self.custom_theme = self.load_custom_theme()
        self.last_volume = int(self.config['audio']['volume'])

        # UI
        self.init_ui()
        self.init_system_tray()

        # Apply preferences
        self.apply_theme(self.config['appearance']['theme'])
        self.apply_font_size(int(self.config['appearance']['font_size']))
        self.apply_accent_color(self.config['appearance']['accent_color'], persist=False)
        try:
            self.setWindowOpacity(int(self.config['appearance']['window_opacity']) / 100)
        except Exception:
            pass

        self.set_volume(int(self.config['audio']['volume']))

        # Hotkeys
        self.init_hotkeys()
        # Timer to refresh the position slider
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_position)
        self.update_timer.start(500)

        logger.info("Application initialized")

    # ------------------------------------------------------------------ #
    # Config
    # ------------------------------------------------------------------ #
    def load_config(self) -> configparser.ConfigParser:
        cfg = configparser.ConfigParser()
        # Populate defaults
        for section, values in DEFAULT_CONFIG.items():
            cfg[section] = values
        try:
            if CONFIG_PATH.exists():
                cfg.read(str(CONFIG_PATH))
        except Exception as e:
            logger.warning(f"Could not read config: {e}")
        return cfg

    def save_config(self):
        try:
            with open(CONFIG_PATH, 'w') as f:
                self.config.write(f)
        except Exception as e:
            logger.error(f"Could not save config: {e}")

    def load_custom_theme(self) -> Dict[str, str]:
        try:
            return json.loads(self.config['appearance']['custom_theme'])
        except Exception:
            return {}

    def save_custom_theme(self, theme: Dict[str, str]):
        self.custom_theme = theme
        self.config['appearance']['custom_theme'] = json.dumps(theme)
        self.config['appearance']['theme'] = 'custom'
        self.save_config()
        self.apply_theme('custom')

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # Now-playing header
        header = QHBoxLayout()
        self.title_label = QLabel("No track loaded")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.title_label.setFont(font)
        header.addWidget(self.title_label)
        header.addStretch(1)
        root.addLayout(header)

        # Splitter: playlist (left) / lyrics+controls (right)
        splitter = QSplitter(Qt.Horizontal)

        # Playlist
        playlist_box = QGroupBox("Playlist")
        playlist_layout = QVBoxLayout(playlist_box)
        self.playlist_widget = QListWidget()
        self.playlist_widget.itemDoubleClicked.connect(self.play_selected_item)
        playlist_layout.addWidget(self.playlist_widget)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Files")
        add_btn.clicked.connect(self.add_files)
        add_folder_btn = QPushButton("Add Folder")
        add_folder_btn.clicked.connect(self.add_folder)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(add_folder_btn)
        playlist_layout.addLayout(btn_row)

        splitter.addWidget(playlist_box)

        # Right side: lyrics + controls
        right = QWidget()
        right_layout = QVBoxLayout(right)

        self.lyrics_view = QScrollArea()
        self.lyrics_label = QLabel("Lyrics will appear here.")
        self.lyrics_label.setAlignment(Qt.AlignCenter)
        self.lyrics_label.setWordWrap(True)
        self.lyrics_view.setWidget(self.lyrics_label)
        self.lyrics_view.setWidgetResizable(True)
        right_layout.addWidget(self.lyrics_view, 1)

        # Progress slider
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 1000)
        self.position_slider.sliderMoved.connect(self.seek)
        right_layout.addWidget(self.position_slider)

        # Transport controls
        controls = QHBoxLayout()
        self.prev_btn = QPushButton("⏮")
        self.play_btn = QPushButton("▶")
        self.next_btn = QPushButton("⏭")
        self.prev_btn.clicked.connect(self.prev_track)
        self.play_btn.clicked.connect(self.play_pause)
        self.next_btn.clicked.connect(self.next_track)
        controls.addWidget(self.prev_btn)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.next_btn)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(int(self.config['audio']['volume']))
        self.volume_slider.valueChanged.connect(self.on_volume_slider)
        controls.addWidget(QLabel("Vol"))
        controls.addWidget(self.volume_slider)

        settings_btn = QPushButton("⚙")
        settings_btn.clicked.connect(self.show_settings)
        controls.addWidget(settings_btn)

        right_layout.addLayout(controls)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        root.addWidget(splitter, 1)

    def init_system_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.system_tray = QSystemTrayIcon(self)
        icon = self.style().standardIcon(QStyle.SP_MediaPlay)
        self.system_tray.setIcon(icon)
        self.system_tray.setToolTip(f"{APP_NAME} {VERSION}")

        menu = QMenu()
        menu.addAction("Play/Pause", self.play_pause)
        menu.addAction("Next", self.next_track)
        menu.addAction("Previous", self.prev_track)
        menu.addSeparator()
        menu.addAction("Show", self.showNormal)
        menu.addAction("Quit", QApplication.quit)

        self.system_tray.setContextMenu(menu)
        self.system_tray.activated.connect(self._tray_activated)
        self.system_tray.show()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()
            self.activateWindow()

    # ------------------------------------------------------------------ #
    # Theme
    # ------------------------------------------------------------------ #
    def apply_theme(self, theme_name: str) -> None:
        if theme_name == 'custom':
            theme = self.custom_theme or THEMES['dark']
        else:
            theme = THEMES.get(theme_name, THEMES['dark'])

        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(theme['base']))
        palette.setColor(QPalette.WindowText, QColor(theme['text']))
        palette.setColor(QPalette.Base, QColor(theme['panel']))
        palette.setColor(QPalette.AlternateBase, QColor(theme['button']))
        palette.setColor(QPalette.ToolTipBase, QColor(theme['text']))
        palette.setColor(QPalette.ToolTipText, QColor(theme['base']))
        palette.setColor(QPalette.Text, QColor(theme['text']))
        palette.setColor(QPalette.Button, QColor(theme['button']))
        palette.setColor(QPalette.ButtonText, QColor(theme['text']))
        palette.setColor(QPalette.BrightText, QColor(theme['highlight']))
        palette.setColor(QPalette.Highlight,
                         QColor(self.config['appearance']['accent_color']))
        palette.setColor(QPalette.HighlightedText, QColor(theme['text']))
        QApplication.setPalette(palette)

        accent = self.config['appearance']['accent_color']
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {theme['base']}; }}
            QWidget {{ color: {theme['text']}; }}
            QGroupBox {{
                border: 1px solid {theme['button']};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                color: {theme['text']};
            }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; }}
            QTabBar::tab {{
                background: {theme['button']};
                color: {theme['text']};
                padding: 8px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }}
            QTabBar::tab:selected {{
                background: {theme['panel']};
                color: {theme['text']};
                border-bottom: 3px solid {accent};
            }}
            QListWidget {{
                background-color: {theme['panel']};
                color: {theme['text']};
                border: 1px solid {theme['button']};
                border-radius: 5px;
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: {theme['button']};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {accent};
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }}
            QScrollBar:vertical {{
                background: {theme['panel']};
                width: 10px;
            }}
            QScrollBar::handle:vertical {{
                background: {theme['button']};
                min-height: 20px;
            }}
            QPushButton {{
                background-color: {theme['button']};
                color: {theme['text']};
                border: 1px solid {theme['panel']};
                padding: 6px 12px;
                border-radius: 4px;
            }}
            QPushButton:hover {{ border: 1px solid {accent}; }}
        """)

        if theme_name != 'custom':
            self.config['appearance']['theme'] = theme_name
            self.save_config()

    def apply_accent_color(self, color_hex: str, persist: bool = True):
        if not QColor(color_hex).isValid():
            return
        self.config['appearance']['accent_color'] = color_hex
        if persist:
            self.save_config()
        # Re-apply the full theme so the accent appears everywhere
        self.apply_theme(self.config['appearance']['theme'])

    def apply_font_size(self, size: int):
        f = QFont()
        f.setPointSize(size)
        QApplication.setFont(f)

    def change_accent_color(self):
        color = QColorDialog.getColor(
            QColor(self.config['appearance']['accent_color']), self)
        if color.isValid():
            self.apply_accent_color(color.name())

    # ------------------------------------------------------------------ #
    # Hotkeys
    # ------------------------------------------------------------------ #
    def init_hotkeys(self):
        QShortcut(QKeySequence("Space"), self, self.play_pause)
        QShortcut(QKeySequence("Ctrl+Right"), self, self.next_track)
        QShortcut(QKeySequence("Ctrl+Left"), self, self.prev_track)
        QShortcut(QKeySequence("Ctrl+Up"), self,
                  lambda: self.set_volume(min(100, self.audio_engine.get_volume() + 5)))
        QShortcut(QKeySequence("Ctrl+Down"), self,
                  lambda: self.set_volume(max(0, self.audio_engine.get_volume() - 5)))
        QShortcut(QKeySequence("Ctrl+M"), self, self.toggle_mute)

    def toggle_mute(self):
        current = self.audio_engine.get_volume()
        if current > 0:
            self.last_volume = current
            self.set_volume(0)
        else:
            self.set_volume(self.last_volume or 70)

    # ------------------------------------------------------------------ #
    # Playback
    # ------------------------------------------------------------------ #
    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Add Audio Files", "",
            "Audio Files (*" + " *".join(SUPPORTED_FORMATS) + ")")
        for f in files:
            self.current_playlist.append(f)
            self.playlist_widget.addItem(os.path.basename(f))

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Add Folder")
        if not folder:
            return
        for p in sorted(Path(folder).rglob("*")):
            if p.suffix.lower() in SUPPORTED_FORMATS:
                self.current_playlist.append(str(p))
                self.playlist_widget.addItem(p.name)

    def play_selected_item(self, item):
        idx = self.playlist_widget.row(item)
        if 0 <= idx < len(self.current_playlist):
            self.current_playlist_index = idx
            self.play_track(self.current_playlist[idx])

    def play_track(self, path: str):
        if not path:
            return
        if self.audio_engine.load_file(path):
            self.current_track = path
            self.title_label.setText(Path(path).stem)
            self.audio_engine.play()
            self.play_btn.setText("⏸")
            self.current_lyrics = None
            self.lyrics_label.setText("Lyrics will appear here.")
            if self.system_tray:
                self.system_tray.setToolTip(f"{APP_NAME} — {Path(path).stem}")

    def play_pause(self):
        if self.audio_engine.is_playing():
            self.audio_engine.pause()
            self.play_btn.setText("▶")
        else:
            if self.current_track is None and self.current_playlist:
                self.play_track(self.current_playlist[0])
            else:
                self.audio_engine.play()
                self.play_btn.setText("⏸")

    def next_track(self):
        if not self.current_playlist:
            return
        self.current_playlist_index = (self.current_playlist_index + 1) % len(self.current_playlist)
        self.play_track(self.current_playlist[self.current_playlist_index])
        self.playlist_widget.setCurrentRow(self.current_playlist_index)

    def prev_track(self):
        if not self.current_playlist:
            return
        self.current_playlist_index = (self.current_playlist_index - 1) % len(self.current_playlist)
        self.play_track(self.current_playlist[self.current_playlist_index])
        self.playlist_widget.setCurrentRow(self.current_playlist_index)

    def set_volume(self, vol: int):
        vol = int(max(0, min(100, vol)))
        self.audio_engine.set_volume(vol)
        self.config['audio']['volume'] = str(vol)
        self.save_config()
        if hasattr(self, 'volume_slider') and self.volume_slider.value() != vol:
            self.volume_slider.blockSignals(True)
            self.volume_slider.setValue(vol)
            self.volume_slider.blockSignals(False)

    def on_volume_slider(self, value: int):
        self.set_volume(value)

    def seek(self, value: int):
        length = self.audio_engine.get_length()
        if length > 0:
            self.audio_engine.set_time(int(length * value / 1000))

    def update_position(self):
        length = self.audio_engine.get_length()
        if length > 0:
            pos = int(self.audio_engine.get_time() * 1000 / length)
            self.position_slider.blockSignals(True)
            self.position_slider.setValue(pos)
            self.position_slider.blockSignals(False)

    # ------------------------------------------------------------------ #
    # Settings
    # ------------------------------------------------------------------ #
    def show_settings(self):
        dlg = self.create_settings_dialog()
        dlg.setAttribute(Qt.WA_DeleteOnClose)
        dlg.show()

    def create_settings_dialog(self):
        dialog = QWidget(self)
        dialog.setWindowTitle("Settings")
        dialog.setFixedSize(800, 600)

        layout = QVBoxLayout()
        tabs = QTabWidget()

        # ---- Appearance tab ----
        appearance_tab = QWidget()
        appearance_layout = QVBoxLayout()

        theme_group = QGroupBox("Theme")
        theme_layout = QVBoxLayout()

        theme_combo = QComboBox()
        theme_combo.addItems(["dark", "light", "amethyst", "midnight", "sunset", "custom"])
        theme_combo.setCurrentText(self.config['appearance']['theme'])
        theme_combo.currentTextChanged.connect(lambda t: self.apply_theme(t))

        accent_color_btn = QPushButton("Accent Color")
        accent_color_btn.clicked.connect(self.change_accent_color)

        opacity_slider = QSlider(Qt.Horizontal)
        opacity_slider.setRange(30, 100)
        opacity_slider.setValue(int(self.config['appearance']['window_opacity']))
        opacity_slider.valueChanged.connect(self._set_opacity)

        theme_layout.addWidget(QLabel("Theme:"))
        theme_layout.addWidget(theme_combo)
        theme_layout.addWidget(accent_color_btn)
        theme_layout.addWidget(QLabel("Window Opacity:"))
        theme_layout.addWidget(opacity_slider)
        theme_group.setLayout(theme_layout)

        # Theme editor (the parent here is the MusicPlayer)
        editor = ThemeEditor(self)
        editor.theme_combo.setCurrentText(self.config['appearance']['theme'])

        appearance_layout.addWidget(theme_group)
        appearance_layout.addWidget(editor)
        appearance_tab.setLayout(appearance_layout)
        tabs.addTab(appearance_tab, "Appearance")

        # ---- Audio tab ----
        audio_tab = QWidget()
        audio_layout = QVBoxLayout()
        eq_label = QLabel("Equalizer Preset:")
        eq_combo = QComboBox()
        eq_combo.addItems(['flat', 'classical', 'club', 'dance', 'full_bass',
                           'full_bass_treble', 'headphones', 'large_hall',
                           'live', 'party', 'pop', 'reggae', 'rock', 'ska',
                           'soft', 'soft_rock', 'techno'])
        eq_combo.setCurrentText(self.config['audio']['eq_preset'])
        eq_combo.currentTextChanged.connect(self._set_eq_preset)
        audio_layout.addWidget(eq_label)
        audio_layout.addWidget(eq_combo)
        audio_layout.addStretch(1)
        audio_tab.setLayout(audio_layout)
        tabs.addTab(audio_tab, "Audio")

        layout.addWidget(tabs)
        dialog.setLayout(layout)
        return dialog

    def _set_opacity(self, value: int):
        try:
            self.setWindowOpacity(value / 100)
        except Exception:
            pass
        self.config['appearance']['window_opacity'] = str(value)
        self.save_config()

    def _set_eq_preset(self, preset: str):
        self.config['audio']['eq_preset'] = preset
        self.save_config()
        self.audio_engine.set_eq_preset(preset)

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def closeEvent(self, event):
        if self.system_tray and self.system_tray.isVisible():
            self.hide()
            self.system_tray.showMessage(
                APP_NAME, "Minimized to tray.",
                QSystemTrayIcon.Information, 1500)
            event.ignore()
        else:
            self.save_config()
            event.accept()


def main():
    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setApplicationVersion(VERSION)
    QCoreApplication.setOrganizationName("Harmony")

    # High-DPI attributes must be set before QApplication is constructed
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create('Fusion'))
    # Ensure quitting from the tray actually exits
    app.setQuitOnLastWindowClosed(False)

    player = MusicPlayer()
    player.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()