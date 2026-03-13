from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from downloader.core.downloader import MangaDownloader
from downloader.gui.widgets import AnimatedProgressBar


class DownloadWorker(QThread):
    log = Signal(str)
    chapter_progress = Signal(str, int, int)
    overall_progress = Signal(int, int)
    finished_ok = Signal()
    failed = Signal(str)

    def __init__(self, urls: list[str], outdir: str) -> None:
        super().__init__()
        self.urls = urls
        self.outdir = outdir

    def run(self) -> None:
        try:
            downloader = MangaDownloader(
                outdir=Path(self.outdir),
                concurrency=8,
                delay=0.2,
                create_cbz=False,
                resume=True,
                language="pt-br",
                on_log=lambda m: self.log.emit(m),
                on_overall_progress=lambda done, total: self.overall_progress.emit(done, total),
                on_chapter_progress=lambda name, done, total: self.chapter_progress.emit(name, done, total),
            )
            asyncio.run(downloader.run(self.urls))
            self.finished_ok.emit()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Manga Downloader")
        self.resize(900, 700)

        self.urls: list[str] = []
        self.output_dir = str(Path.cwd() / "downloads")
        self.worker: DownloadWorker | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        title = QLabel("Manga Downloader")
        title.setObjectName("title")
        subtitle = QLabel("Downloads PT-BR com interface moderna")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        url_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Cole a URL do mangá...")
        add_btn = QPushButton("Adicionar")
        add_btn.clicked.connect(self.add_url)
        url_row.addWidget(self.url_input)
        url_row.addWidget(add_btn)
        layout.addLayout(url_row)

        self.chapter_list = QListWidget()
        self.chapter_list.setMinimumHeight(170)
        layout.addWidget(self.chapter_list)

        self.chapter_progress = AnimatedProgressBar()
        self.chapter_progress.setFormat("Capítulo: %p%")
        self.overall_progress = AnimatedProgressBar()
        self.overall_progress.setFormat("Geral: %p%")
        layout.addWidget(self.chapter_progress)
        layout.addWidget(self.overall_progress)

        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(QLabel("Log de status"))
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(170)
        panel_layout.addWidget(self.log_box)
        layout.addWidget(panel)

        actions = QHBoxLayout()
        folder_btn = QPushButton("Escolher pasta")
        folder_btn.clicked.connect(self.pick_folder)
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.start_download)
        actions.addWidget(folder_btn)
        actions.addStretch(1)
        actions.addWidget(self.download_btn)
        layout.addLayout(actions)

    def add_url(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            return
        self.urls.append(url)
        self.chapter_list.addItem(QListWidgetItem(url))
        self.url_input.clear()

    def pick_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Escolher pasta", self.output_dir)
        if selected:
            self.output_dir = selected
            self.log_box.append(f"Pasta de saída: {selected}")

    def start_download(self) -> None:
        if not self.urls:
            QMessageBox.warning(self, "Atenção", "Adicione ao menos uma URL.")
            return

        self.download_btn.setEnabled(False)
        self.chapter_progress.setValue(0)
        self.overall_progress.setValue(0)

        self.worker = DownloadWorker(self.urls, self.output_dir)
        self.worker.log.connect(self.log_box.append)
        self.worker.chapter_progress.connect(self.on_chapter_progress)
        self.worker.overall_progress.connect(self.on_overall_progress)
        self.worker.finished_ok.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def on_chapter_progress(self, name: str, done: int, total: int) -> None:
        self.chapter_progress.setFormat(f"{name} ({done}/{total})")
        pct = int((done / total) * 100) if total else 0
        self.chapter_progress.animate_to(pct)

    def on_overall_progress(self, done: int, total: int) -> None:
        pct = int((done / total) * 100) if total else 0
        self.overall_progress.animate_to(pct)

    def on_finished(self) -> None:
        self.log_box.append("Download finalizado.")
        self.download_btn.setEnabled(True)

    def on_failed(self, error: str) -> None:
        self.log_box.append(f"Erro: {error}")
        self.download_btn.setEnabled(True)
