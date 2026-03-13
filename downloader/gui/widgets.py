from __future__ import annotations

from PySide6.QtCore import QEasingCurve, Property, QPropertyAnimation
from PySide6.QtWidgets import QProgressBar


class AnimatedProgressBar(QProgressBar):
    def __init__(self) -> None:
        super().__init__()
        self._value = 0
        self._animation = QPropertyAnimation(self, b"animatedValue", self)
        self._animation.setDuration(220)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

    def get_animated_value(self) -> int:
        return self._value

    def set_animated_value(self, value: int) -> None:
        self._value = value
        self.setValue(value)

    animatedValue = Property(int, get_animated_value, set_animated_value)

    def animate_to(self, value: int) -> None:
        self._animation.stop()
        self._animation.setStartValue(self.value())
        self._animation.setEndValue(value)
        self._animation.start()
