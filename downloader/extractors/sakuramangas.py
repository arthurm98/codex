from __future__ import annotations

from urllib.parse import urlparse

from downloader.extractors.wp_manga import WPMangaExtractor


class SakuraMangasExtractor(WPMangaExtractor):
    @classmethod
    def detect(cls, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return "sakuramangas.org" in host
