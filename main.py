from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from downloader.gui.main_window import MainWindow
from downloader.gui.theme import build_stylesheet


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(build_stylesheet())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
