"""Look and feel: one stylesheet, light and dark palettes (follows the Windows setting)."""

import tempfile
from pathlib import Path
from string import Template

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPalette, QPen, QPixmap

LIGHT = dict(
    bg="#F4F6F9",
    card="#FFFFFF",
    border="#E2E6EC",
    text="#1B2230",
    muted="#667085",
    accent="#2563EB",
    accent_hover="#1D4ED8",
    accent_soft="#E6EEFD",
    accent_text="#FFFFFF",
    alt_row="#F9FAFC",
    header_bg="#F1F4F8",
    success_bg="#E8F7EE",
    success="#177A3E",
    disabled_bg="#EEF1F5",
    disabled_text="#A4ABB8",
    scroll="#C8CED8",
)
DARK = dict(
    bg="#14171C",
    card="#1D2128",
    border="#2B313B",
    text="#E8EBF0",
    muted="#98A1B0",
    accent="#5B93FF",
    accent_hover="#7AA6FF",
    accent_soft="#22304D",
    accent_text="#0A1020",
    alt_row="#1A1E24",
    header_bg="#222730",
    success_bg="#173222",
    success="#58D68D",
    disabled_bg="#232830",
    disabled_text="#5D6674",
    scroll="#3B424E",
)

STYLE = Template("""
* { font-family: "Segoe UI Variable", "Segoe UI", "Inter", "Helvetica Neue", sans-serif; font-size: 10pt; }
QMainWindow, QDialog, QMessageBox, QWidget#root { background: $bg; }
QLabel { color: $text; background: transparent; }
QLabel[role="muted"] { color: $muted; }
QLabel#title { font-size: 20pt; font-weight: 700; }
QLabel#subtitle { color: $muted; font-size: 10pt; }
QLabel#summary { color: $muted; }
QLabel#flash { background: $success_bg; color: $success; border-radius: 8px; padding: 10px 14px; font-weight: 600; }
QLabel[role="statValue"] { font-size: 22pt; font-weight: 700; }
QLabel#emptyTitle { font-size: 15pt; font-weight: 600; }
QLabel#emptyText { color: $muted; }

QFrame[card="true"] { background: $card; border: 1px solid $border; border-radius: 12px; }
QFrame[card="true"] QLabel { background: transparent; }

QLabel[step="current"] { color: $accent; background: $accent_soft; border-radius: 13px; padding: 5px 14px; font-weight: 600; }
QLabel[step="done"]    { color: $success; background: transparent; border-radius: 13px; padding: 5px 14px; }
QLabel[step="todo"]    { color: $muted;   background: transparent; border-radius: 13px; padding: 5px 14px; }
QLabel[role="sep"] { color: $border; }

QPushButton { background: $card; color: $text; border: 1px solid $border; border-radius: 8px; padding: 8px 16px; min-width: 70px; }
QPushButton:hover { background: $header_bg; }
QPushButton:pressed { background: $border; }
QPushButton:disabled { background: $disabled_bg; color: $disabled_text; border-color: $border; }
QPushButton[variant="primary"] { background: $accent; color: $accent_text; border: 1px solid $accent; font-weight: 600; }
QPushButton[variant="primary"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[variant="primary"]:disabled { background: $disabled_bg; color: $disabled_text; border-color: $border; }

QCheckBox { color: $text; spacing: 8px; background: transparent; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1.5px solid $muted; border-radius: 5px; background: $card; }
QCheckBox::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent; image: url($check); }
QCheckBox::indicator:disabled { border-color: $disabled_text; background: $disabled_bg; }

QTreeWidget { background: $card; alternate-background-color: $alt_row; color: $text;
              border: 1px solid $border; border-radius: 12px; outline: 0; }
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
