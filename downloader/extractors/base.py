from __future__ import annotations

from abc import ABC, abstractmethod

from downloader.core.models import Chapter


class BaseExtractor(ABC):
    @classmethod
    @abstractmethod
    def detect(cls, url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def get_chapter_list(self, url: str, language: str) -> list[Chapter]:
        raise NotImplementedError

    @abstractmethod
    async def get_page_images(self, chapter: Chapter) -> list[str]:
        raise NotImplementedError
