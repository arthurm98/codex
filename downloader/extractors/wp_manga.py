from __future__ import annotations

from urllib.parse import urlparse

from downloader.extractors.generic_reader import GenericReaderExtractor


class WPMangaExtractor(GenericReaderExtractor):
    @classmethod
    def detect(cls, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return any(token in host for token in ("manga", "manhwa", "manhua"))
