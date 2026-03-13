from __future__ import annotations

from urllib.parse import urlparse

from downloader.core.fetcher import Fetcher
from downloader.core.models import Chapter
from downloader.core.utils import sanitize_name
from downloader.extractors.base import BaseExtractor


class MangaDexExtractor(BaseExtractor):
    def __init__(self, fetcher: Fetcher) -> None:
        self.fetcher = fetcher

    @classmethod
    def detect(cls, url: str) -> bool:
        return "mangadex.org" in urlparse(url).netloc

    async def get_chapter_list(self, url: str, language: str) -> list[Chapter]:
        path_parts = [part for part in urlparse(url).path.split("/") if part]
        if not path_parts:
            return []

        if path_parts[0] == "chapter" and len(path_parts) > 1:
            chapter_id = path_parts[1]
            chapter = await self._chapter_from_id(chapter_id)
            return [chapter] if chapter else []

        if path_parts[0] == "title" and len(path_parts) > 1:
            manga_id = path_parts[1]
            return await self._chapters_from_manga_id(manga_id)

        return []

    async def get_page_images(self, chapter: Chapter) -> list[str]:
        at_home = await self.fetcher.get_json(f"https://api.mangadex.org/at-home/server/{chapter.chapter_id}")
        base_url = at_home["baseUrl"]
        chapter_data = at_home["chapter"]
        hash_value = chapter_data["hash"]
        files = chapter_data.get("data") or chapter_data.get("dataSaver") or []
        return [f"{base_url}/data/{hash_value}/{fname}" for fname in files]

    async def _chapter_from_id(self, chapter_id: str) -> Chapter | None:
        payload = await self.fetcher.get_json(
            f"https://api.mangadex.org/chapter/{chapter_id}?includes[]=manga"
        )
        data = payload.get("data", {})
        attributes = data.get("attributes", {})
        lang = attributes.get("translatedLanguage")
        if lang != "pt-br":
            return None

        manga_title = "Unknown_Manga"
        for rel in data.get("relationships", []):
            if rel.get("type") == "manga":
                title = (rel.get("attributes", {}) or {}).get("title", {})
                manga_title = title.get("pt-br") or title.get("en") or manga_title
        chapter_num = attributes.get("chapter") or chapter_id
        return Chapter(sanitize_name(manga_title), chapter_id, f"ch_{chapter_num}", f"https://mangadex.org/chapter/{chapter_id}", lang)

    async def _chapters_from_manga_id(self, manga_id: str) -> list[Chapter]:
        chapters: list[Chapter] = []
        offset = 0
        limit = 100
        while True:
            endpoint = (
                f"https://api.mangadex.org/chapter?manga={manga_id}&limit={limit}&offset={offset}"
                "&order[chapter]=asc&translatedLanguage[]=pt-br&includes[]=manga"
            )
            payload = await self.fetcher.get_json(endpoint)
            data = payload.get("data", [])
            if not data:
                break

            for item in data:
                attrs = item.get("attributes", {})
                manga_title = "Unknown_Manga"
                for rel in item.get("relationships", []):
                    if rel.get("type") == "manga":
                        title = (rel.get("attributes", {}) or {}).get("title", {})
                        manga_title = title.get("pt-br") or title.get("en") or manga_title
                ch_num = attrs.get("chapter") or item.get("id")
                chapters.append(
                    Chapter(
                        manga_title=sanitize_name(manga_title),
                        chapter_id=item["id"],
                        chapter_title=f"ch_{ch_num}",
                        chapter_url=f"https://mangadex.org/chapter/{item['id']}",
                        language=attrs.get("translatedLanguage", ""),
                    )
                )
            total = payload.get("total", 0)
            offset += limit
            if offset >= total:
                break
        return chapters
