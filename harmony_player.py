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
                            QColorDialog, QShortcut, QStyleFactory)

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
        # Initialize VLC with advanced parameters
        vlc_args = [
            '--no-xlib', 
            '--quiet',
            '--audio-resampler', 'soxr',
            '--avcodec-hw=any',
            '--network-caching=3000'
        ]
        self.instance = vlc.Instance(vlc_args)
        self.player = self.instance.media_player_new()
        self.equalizer = vlc.AudioEqualizer()
        self.current_media = None
        self.media_list = self.instance.media_list_new()
        self.list_player = self.instance.media_list_player_new()
        self.list_player.set_media_player(self.player)
        self.list_player.set_media_list(self.media_list)
        self.events = self.player.event_manager()
        
        # Audio effects
        self.compressor = None
        self.spatializer = None
        self.init_audio_effects()
        
        # Default equalizer preset
        self.set_eq_preset('flat')
        
        # Crossfade timer
        self.crossfade_timer = QTimer()
        self.crossfade_timer.timeout.connect(self.handle_crossfade)
        self.crossfade_duration = 3  # seconds
        self.fade_out_player = None
        
    def init_audio_effects(self):
        """Initialize audio effects if available"""
        try:
            # Try to enable advanced audio effects
            self.player.audio_set_effect('compressor')
            self.player.audio_set_effect('spatializer')
            logger.info("Audio effects initialized")
        except Exception as e:
            logger.warning(f"Could not initialize audio effects: {e}")
    
    def load_file(self, file_path: str) -> bool:
        """Load a local file with metadata parsing"""
        try:
            media = self.instance.media_new(file_path)
            
            # Parse metadata
            media.parse_with_options(vlc.MediaParseFlag.network, 5000)
            
            self.player.set_media(media)
            self.current_media = media
            return True
        except Exception as e:
            logger.error(f"Error loading file: {e}")
            return False
    
    def play(self) -> bool:
        """Start playback with optional crossfade"""
        if self.crossfade_duration > 0 and self.fade_out_player:
            self.start_crossfade()
            return True
        return self.player.play() == 0
    
    def start_crossfade(self):
        """Begin crossfade between current and next track"""
        self.crossfade_timer.start(100)  # Update every 100ms
        self.fade_out_player.audio_set_volume(100)
        self.player.audio_set_volume(0)
        self.player.play()
    
    def handle_crossfade(self):
        """Handle crossfade progress"""
        # Implement crossfade logic here
        pass
    
    # ... (rest of AudioEngine methods)

class ThemeEditor(QWidget):
    """Widget for customizing color themes"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Theme selection
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Custom"] + list(THEMES.keys()))
        self.theme_combo.currentTextChanged.connect(self.theme_changed)
        
        # Color pickers
        color_group = QGroupBox("Theme Colors")
        color_layout = QGridLayout()
        
        self.color_pickers = {}
        row = 0
        for color_name in ['base', 'text', 'highlight', 'button', 'panel']:
            lbl = QLabel(color_name.capitalize())
            btn = QPushButton()
            btn.setFixedSize(60, 30)
            btn.clicked.connect(lambda _, c=color_name: self.pick_color(c))
            self.color_pickers[color_name] = btn
            
            color_layout.addWidget(lbl, row, 0)
            color_layout.addWidget(btn, row, 1)
            row += 1
        
        color_group.setLayout(color_layout)
        
        # Preview area
        preview_group = QGroupBox("Preview")
        self.preview = QLabel()
        self.preview.setFixedHeight(100)
        preview_group.setLayout(QHBoxLayout())
        preview_group.layout().addWidget(self.preview)
        
        # Buttons
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
        self.update_preview()
    
    def pick_color(self, color_name):
        """Open color picker for a theme color"""
        color = QColorDialog.getColor()
        if color.isValid():
            self.color_pickers[color_name].setStyleSheet(
                f"background-color: {color.name()}; border: none;"
            )
            self.update_preview()
    
    def update_preview(self):
        """Update the theme preview"""
        pixmap = QPixmap(400, 100)
        painter = QPainter(pixmap)
        
        # Get current colors
        colors = {}
        for name, btn in self.color_pickers.items():
            style = btn.styleSheet()
            if 'background-color' in style:
                colors[name] = style.split(':')[1].split(';')[0].strip()
            else:
                colors[name] = '#000000'
        
        # Draw preview
        painter.fillRect(0, 0, 400, 100, QColor(colors['base']))
        
        # Draw "buttons"
        painter.setBrush(QColor(colors['button']))
        painter.drawRect(20, 20, 100, 30)
        
        # Draw "text"
        painter.setPen(QColor(colors['text']))
        painter.drawText(130, 40, "Sample Text")
        
        # Draw "highlight"
        painter.setBrush(QColor(colors['highlight']))
        painter.drawRect(250, 20, 30, 30)
        
        # Draw "panel"
        painter.setBrush(QColor(colors['panel']))
        painter.drawRect(300, 20, 80, 60)
        
        painter.end()
        self.preview.setPixmap(pixmap)
    
    def theme_changed(self, theme_name):
        """Handle theme selection change"""
        if theme_name == "Custom":
            return
            
        theme = THEMES.get(theme_name, THEMES['dark'])
        for name, color in theme.items():
            btn = self.color_pickers.get(name)
            if btn:
                btn.setStyleSheet(f"background-color: {color}; border: none;")
        
        self.update_preview()
    
    def save_theme(self):
        """Save the current custom theme"""
        theme = {}
        for name, btn in self.color_pickers.items():
            style = btn.styleSheet()
            if 'background-color' in style:
                theme[name] = style.split(':')[1].split(';')[0].strip()
        
        self.parent.save_custom_theme(theme)
    
    def reset_theme(self):
        """Reset to default theme"""
        self.theme_combo.setCurrentText('dark')

class MusicPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {VERSION}")
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize components
        self.audio_engine = AudioEngine()
        self.config = self.load_config()
        self.current_track = None
        self.current_lyrics = None
        self.current_playlist = []
        self.current_playlist_index = 0
        self.system_tray = None
        self.custom_theme = self.load_custom_theme()
        
        # Setup UI
        self.init_ui()
        self.init_system_tray()
        self.apply_theme(self.config['appearance']['theme'])
        self.apply_font_size(int(self.config['appearance']['font_size']))
        self.apply_accent_color(self.config['appearance']['accent_color'])
        self.setWindowOpacity(int(self.config['appearance']['window_opacity']) / 100)
        
        # Load initial state
        self.set_volume(int(self.config['audio']['volume']))
        
        # Initialize hotkeys
        self.init_hotkeys()
        
        logger.info("Application initialized")

    def load_custom_theme(self) -> Dict[str, str]:
        """Load custom theme from config"""
        try:
            return json.loads(self.config['appearance']['custom_theme'])
        except:
            return {}

    def save_custom_theme(self, theme: Dict[str, str]):
        """Save custom theme to config"""
        self.custom_theme = theme
        self.config['appearance']['custom_theme'] = json.dumps(theme)
        self.save_config()
        self.apply_theme('custom')

    def apply_theme(self, theme_name: str) -> None:
        """Apply theme to the application"""
        if theme_name == 'custom':
            theme = self.custom_theme
        else:
            theme = THEMES.get(theme_name, THEMES['dark'])
        
        palette = QPalette()
        
        # Base colors
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
        palette.setColor(QPalette.Highlight, QColor(self.config['appearance']['accent_color']))
        palette.setColor(QPalette.HighlightedText, QColor(theme['text']))
        
        QApplication.setPalette(palette)
        
        # Additional styling
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {theme['base']};
            }}
            QGroupBox {{
                border: 1px solid {theme['button']};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                color: {theme['text']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
            }}
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
                border-bottom: 3px solid {self.config['appearance']['accent_color']};
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
                background: {self.config['appearance']['accent_color']};
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
        """)
        
        # Update config
        if theme_name != 'custom':
            self.config['appearance']['theme'] = theme_name
            self.save_config()

    def apply_accent_color(self, color_hex: str):
        """Apply accent color to the UI"""
        self.config['appearance']['accent_color'] = color_hex
        self.save_config()
        
        # Update any accent-colored elements
        self.update_ui_colors()

    def update_ui_colors(self):
        """Update UI elements that use the accent color"""
        accent = self.config['appearance']['accent_color']
        
        # Update slider handles
        self.setStyleSheet(f"""
            QSlider::handle:horizontal {{
                background: {accent};
            }}
            QTabBar::tab:selected {{
                border-bottom-color: {accent};
            }}
        """)

    def init_hotkeys(self):
        """Initialize global hotkeys"""
        # Play/Pause
        QShortcut(QKeySequence("Space"), self, self.play_pause)
        QShortcut(QKeySequence("Media Play"), self, self.play_pause)
        
        # Next/Previous
        QShortcut(QKeySequence("Ctrl+Right"), self, self.next_track)
        QShortcut(QKeySequence("Media Next"), self, self.next_track)
        QShortcut(QKeySequence("Ctrl+Left"), self, self.prev_track)
        QShortcut(QKeySequence("Media Previous"), self, self.prev_track)
        
        # Volume control
        QShortcut(QKeySequence("Ctrl+Up"), self, lambda: self.set_volume(min(100, self.audio_engine.get_volume() + 5)))
        QShortcut(QKeySequence("Ctrl+Down"), self, lambda: self.set_volume(max(0, self.audio_engine.get_volume() - 5)))
        
        # Mute
        QShortcut(QKeySequence("Ctrl+M"), self, self.toggle_mute)

    def toggle_mute(self):
        """Toggle mute state"""
        current = self.audio_engine.get_volume()
        if current > 0:
            self.last_volume = current
            self.set_volume(0)
        else:
            self.set_volume(self.last_volume if hasattr(self, 'last_volume') else 70)

    # ... (rest of the MusicPlayer implementation)

    def create_settings_dialog(self):
        """Create the settings dialog with theme customization"""
        dialog = QWidget(self)
        dialog.setWindowTitle("Settings")
        dialog.setFixedSize(800, 600)
        
        layout = QVBoxLayout()
        tabs = QTabWidget()
        
        # Appearance tab
        appearance_tab = QWidget()
        appearance_layout = QVBoxLayout()
        
        # Theme selection
        theme_group = QGroupBox("Theme")
        theme_layout = QVBoxLayout()
        
        theme_combo = QComboBox()
        theme_combo.addItems(["dark", "light", "amethyst", "midnight", "sunset", "custom"])
        theme_combo.setCurrentText(self.config['appearance']['theme'])
        theme_combo.currentTextChanged.connect(lambda t: self.apply_theme(t))
        
        # Accent color
        accent_color_btn = QPushButton("Accent Color")
        accent_color_btn.clicked.connect(self.change_accent_color)
        
        # Window opacity
        opacity_slider = QSlider(Qt.Horizontal)
        opacity_slider.setRange(30, 100)
        opacity_slider.setValue(int(self.config['appearance']['window_opacity']))
        opacity_slider.valueChanged.connect(lambda v: self.setWindowOpacity(v/100))
        
        theme_layout.addWidget(QLabel("Theme:"))
        theme_layout.addWidget(theme_combo)
        theme_layout.addWidget(accent_color_btn)
        theme_layout.addWidget(QLabel("Window Opacity:"))
        theme_layout.addWidget(opacity_slider)
        theme_group.setLayout(theme_layout)
        
        # Theme editor
        self.theme_editor = ThemeEditor(self)
        
        appearance_layout.addWidget(theme_group)
        appearance_layout.addWidget(self.theme_editor)
        appearance_tab.setLayout(appearance_layout)
        
        tabs.addTab(appearance_tab, "Appearance")
        
        # Add other settings tabs (Audio, Playback, Lyrics, etc.)
        # ...
        
        layout.addWidget(tabs)
        dialog.setLayout(layout)
        
        return dialog

    def change_accent_color(self):
        """Change the accent color"""
        color = QColorDialog.getColor(QColor(self.config['appearance']['accent_color']))
        if color.isValid():
            self.apply_accent_color(color.name())

    # ... (remaining methods)

def main():
    # Set application attributes
    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setApplicationVersion(VERSION)
    QCoreApplication.setOrganizationName("Harmony")
    
    # Enable high DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle(QStyleFactory.create('Fusion'))
    
    # Create and show main window
    player = MusicPlayer()
    player.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
