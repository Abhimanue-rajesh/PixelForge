"""Look and feel: one stylesheet, light and dark palettes (follows the Windows setting)."""

import tempfile
from pathlib import Path
from string import Template

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPalette, QPen, QPixmap

LIGHT = dict(
    bg="#F3F3F3",
    card="#FFFFFF",
    border="#E3E3E3",
    text="#1B1B1B",
    muted="#616161",
    accent="#005FB8",
    accent_hover="#0055A5",
    accent_soft="#E7EEF5",
    accent_text="#FFFFFF",
    alt_row="#FAFAFA",
    header_bg="#F7F7F7",
    success_bg="#E8F7EE",
    success="#177A3E",
    disabled_bg="#EEF1F5",
    disabled_text="#A4ABB8",
    scroll="#C8CED8",
)
DARK = dict(
    bg="#202020",
    card="#2B2B2B",
    border="#3A3A3A",
    text="#F2F2F2",
    muted="#B9B9B9",
    accent="#60CDFF",
    accent_hover="#7AD5FF",
    accent_soft="#333E46",
    accent_text="#14212A",
    alt_row="#292929",
    header_bg="#303030",
    success_bg="#173222",
    success="#58D68D",
    disabled_bg="#232830",
    disabled_text="#5D6674",
    scroll="#3B424E",
)

STYLE = Template("""
* { font-family: "Poppins", "Segoe UI", sans-serif; font-size: 10pt; }
QMainWindow, QDialog, QMessageBox, QWidget#root { background: $bg; }
QLabel { color: $text; background: transparent; }
QLabel[role="muted"] { color: $muted; }
QLabel#title { font-size: 22pt; font-weight: 600; }
QLabel#brand { font-size: 16pt; font-weight: 600; }
QLabel[role="toolTitle"] { font-size: 11pt; font-weight: 500; }
QLabel[role="chevron"] { color: $muted; font-size: 18pt; }
QFrame#sidebar { background: $bg; border: none; border-right: 1px solid $border; }
QLabel#subtitle { color: $muted; font-size: 10pt; }
QLabel#summary { color: $muted; }
QLabel#flash { background: $success_bg; color: $success; border-radius: 8px; padding: 10px 14px; font-weight: 600; }
QLabel[role="statValue"] { font-size: 18pt; font-weight: 500; }
QLabel#emptyTitle { font-size: 15pt; font-weight: 600; }
QLabel#emptyText { color: $muted; }

QFrame[card="true"] { background: $card; border: 1px solid $border; border-radius: 6px; }
QFrame[card="true"] QLabel { background: transparent; }

QLabel[step="current"] { color: $accent; background: transparent; padding: 6px 4px; border-bottom: 2px solid $accent; font-weight: 500; }
QLabel[step="done"]    { color: $muted; background: transparent; padding: 6px 4px; }
QLabel[step="todo"]    { color: $muted; background: transparent; padding: 6px 4px; }
QLabel[role="sep"] { color: $border; }

QPushButton { background: $card; color: $text; border: 1px solid $border; border-radius: 5px; padding: 7px 14px; min-width: 70px; }
QPushButton:hover { background: $header_bg; }
QPushButton:pressed { background: $border; }
QPushButton:focus { border: 1px solid $accent; }
QPushButton:disabled { background: $disabled_bg; color: $disabled_text; border-color: $border; }
QPushButton[variant="primary"] { background: $accent; color: $accent_text; border: 1px solid $accent; font-weight: 600; }
QPushButton[variant="primary"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[variant="primary"]:disabled { background: $disabled_bg; color: $disabled_text; border-color: $border; }
QPushButton[navigation="true"] { background: transparent; text-align: left; border: 1px solid transparent; border-left: 3px solid transparent; padding: 10px 12px; font-weight: 400; }
QPushButton[navigation="true"]:hover { background: $border; }
QPushButton[navigation="true"]:checked { background: $accent_soft; border-left: 3px solid $accent; font-weight: 500; }
QPushButton[navigation="true"]:focus { border-top-color: $accent; border-bottom-color: $accent; border-right-color: $accent; }
QPushButton[toolRow="true"] { text-align: left; border-radius: 6px; padding: 0; }
QPushButton[toolRow="true"] QLabel { background: transparent; }

QScrollArea { background: transparent; border: none; }
QComboBox { background: $card; color: $text; border: 1px solid $border; border-radius: 5px; padding: 7px 12px; }
QComboBox:focus { border-color: $accent; }
QComboBox:disabled { background: $disabled_bg; color: $disabled_text; }
QComboBox QAbstractItemView { background: $card; color: $text; selection-background-color: $accent_soft; selection-color: $text; border: 1px solid $border; }

QDoubleSpinBox { background: $card; color: $text; border: 1px solid $border; border-radius: 5px; padding: 7px 12px; min-width: 100px; }
QDoubleSpinBox:focus { border-color: $accent; }
QDoubleSpinBox:disabled { background: $disabled_bg; color: $disabled_text; }
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 0px; border: none; }

QCheckBox { color: $text; spacing: 8px; background: transparent; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1.5px solid $muted; border-radius: 5px; background: $card; }
QCheckBox::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent; image: url($check); }
QCheckBox::indicator:disabled { border-color: $disabled_text; background: $disabled_bg; }

QTreeWidget { background: $card; alternate-background-color: $alt_row; color: $text;
              border: 1px solid $border; border-radius: 6px; outline: 0; }
QTreeWidget::item { padding: 6px 4px; border: none; }
QTreeWidget::item:selected { background: $accent_soft; color: $text; }
QTreeWidget::item:hover { background: $header_bg; }
QHeaderView::section { background: $header_bg; color: $muted; border: none;
                       border-bottom: 1px solid $border; padding: 9px 8px; font-weight: 600; }

QProgressBar { background: $border; border: none; border-radius: 3px; min-height: 6px; max-height: 6px; }
QProgressBar::chunk { background: $accent; border-radius: 3px; }

QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: $scroll; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $muted; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px; }
QScrollBar::handle:horizontal { background: $scroll; border-radius: 4px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: $muted; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QToolTip { background: $card; color: $text; border: 1px solid $border; padding: 6px; }
""")


def _check_icon(color: str) -> str:
    """Draw the tick used inside checked boxes once and cache it as a PNG."""
    path = Path(tempfile.gettempdir()) / "pixelforge" / f"check_{color.lstrip('#')}.png"
    if not path.exists():
        path.parent.mkdir(exist_ok=True)
        pm = QPixmap(36, 36)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(color), 4.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline([QPointF(9, 19), QPointF(15, 25), QPointF(27, 11)])
        painter.end()
        pm.save(str(path))
    return path.as_posix()


def is_dark(app) -> bool:
    try:
        return app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:  # Qt older than 6.5: no scheme detection
        return False


def load_fonts(app) -> None:
    fonts = Path(__file__).resolve().parents[1] / "assets" / "fonts"
    for path in sorted(fonts.glob("*.ttf")):
        if QFontDatabase.addApplicationFont(str(path)) == -1:
            raise RuntimeError(f"Could not load bundled font: {path.name}")
    app.setFont(QFont("Poppins", 10))


def apply_theme(app, dark: bool | None = None) -> None:
    c = DARK if (is_dark(app) if dark is None else dark) else LIGHT
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: c["bg"],
        QPalette.ColorRole.WindowText: c["text"],
        QPalette.ColorRole.Base: c["card"],
        QPalette.ColorRole.AlternateBase: c["alt_row"],
        QPalette.ColorRole.Text: c["text"],
        QPalette.ColorRole.Button: c["card"],
        QPalette.ColorRole.ButtonText: c["text"],
        QPalette.ColorRole.Highlight: c["accent"],
        QPalette.ColorRole.HighlightedText: c["accent_text"],
        QPalette.ColorRole.ToolTipBase: c["card"],
        QPalette.ColorRole.ToolTipText: c["text"],
        QPalette.ColorRole.PlaceholderText: c["muted"],
    }
    for role, color in roles.items():
        pal.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.WindowText,
    ):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(c["disabled_text"]))
    app.setPalette(pal)
    app.setStyleSheet(STYLE.substitute(c, check=_check_icon(c["accent_text"])))
