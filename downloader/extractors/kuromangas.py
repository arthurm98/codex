from __future__ import annotations

from urllib.parse import urlparse

from downloader.extractors.generic_reader import GenericReaderExtractor


class KuromangasExtractor(GenericReaderExtractor):
    @classmethod
    def detect(cls, url: str) -> bool:
        return "kuromangas" in urlparse(url).netloc.lower()
