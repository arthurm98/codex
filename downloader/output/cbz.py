from __future__ import annotations

import zipfile
from pathlib import Path


def create_cbz(chapter_folder: Path) -> Path:
    cbz_path = chapter_folder.with_suffix(".cbz")
    with zipfile.ZipFile(cbz_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for image in sorted(chapter_folder.glob("*")):
            if image.is_file():
                zf.write(image, arcname=image.name)
    return cbz_path
