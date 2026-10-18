from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout


def repolish(widget) -> None:
    """Re-apply the stylesheet after a dynamic property changed."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class StatCard(QFrame):
    """A small summary tile: big number + caption."""

    def __init__(self, caption: str):
        super().__init__()
        self.setProperty("card", True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(0)
        self.value = QLabel("–")
        self.value.setProperty("role", "statValue")
        self.caption = QLabel(caption)
        self.caption.setProperty("role", "muted")
        lay.addWidget(self.value)
        lay.addWidget(self.caption)

    def set_value(self, value: str, caption: str | None = None) -> None:
        self.value.setText(value)
        if caption:
            self.caption.setText(caption)


class StepBar(QFrame):
    """Shows where the user is in the workflow: done / current / still to do."""

    STEPS = ["Choose folder", "Find duplicates", "Move sets", "Review"]

    def __init__(self):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.labels = []
        for i, name in enumerate(self.STEPS):
            lab = QLabel()
            lab.setProperty("step", "todo")
            self.labels.append(lab)
            lay.addWidget(lab)
            if i < len(self.STEPS) - 1:
                sep = QLabel("›")
                sep.setProperty("role", "sep")
                lay.addWidget(sep)
        lay.addStretch()
        self.set_current(0)

    def set_current(self, index: int) -> None:
        for i, (lab, name) in enumerate(zip(self.labels, self.STEPS)):
            state = "done" if i < index else "current" if i == index else "todo"
            lab.setText(f"✓  {name}" if state == "done" else f"{i + 1}  {name}")
            if lab.property("step") != state:
                lab.setProperty("step", state)
                repolish(lab)


class ElidedLabel(QLabel):
    """A label that shortens long text with … instead of widening the window."""

    def __init__(self, text: str = ""):
        super().__init__()
        self._full = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.set_full_text(text)

    def set_full_text(self, text: str) -> None:
        self._full = text
        self.setToolTip(text)
        self._elide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()

    def _elide(self):
        shown = self.fontMetrics().elidedText(
            self._full, Qt.TextElideMode.ElideMiddle, max(self.width() - 4, 20)
        )
        super().setText(shown)
