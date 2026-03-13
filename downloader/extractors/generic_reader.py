from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from downloader.core.fetcher import Fetcher
from downloader.core.models import Chapter
from downloader.core.utils import IMAGE_EXTENSIONS, is_pt_br, sanitize_name
from downloader.extractors.base import BaseExtractor

SCRIPT_URL_PATTERN = re.compile(r"https?://[^\"'\s<>]+(?:jpg|jpeg|png|webp|avif)", re.I)


class GenericReaderExtractor(BaseExtractor):
    def __init__(self, fetcher: Fetcher) -> None:
        self.fetcher = fetcher

    @classmethod
    def detect(cls, url: str) -> bool:
        return True

    async def get_chapter_list(self, url: str, language: str) -> list[Chapter]:
        html = await self.fetcher.get_text(url)
        soup = BeautifulSoup(html, "html.parser")

        title = sanitize_name((soup.title.string if soup.title else "Unknown_Manga").strip())
        chapter_name = sanitize_name(self._extract_chapter_name(url, soup))
        page_lang = self._language_from_html(soup)
        if not is_pt_br(page_lang):
            return []

        chapter_id = chapter_name
        return [Chapter(title, chapter_id, chapter_name, url, page_lang)]

    async def get_page_images(self, chapter: Chapter) -> list[str]:
        html = await self.fetcher.get_text(chapter.chapter_url, referer=chapter.chapter_url)
        soup = BeautifulSoup(html, "html.parser")
        images: list[str] = []

        for img in soup.select("img"):
            for attr in ("src", "data-src", "data-lazy", "data-lazy-src", "data-original"):
                src = img.get(attr)
                if src and any(ext in src.lower() for ext in IMAGE_EXTENSIONS):
                    images.append(urljoin(chapter.chapter_url, src))

        for script in soup.select("script"):
            body = script.string or script.get_text(" ", strip=True)
            if not body:
                continue
            images.extend(SCRIPT_URL_PATTERN.findall(body))
            images.extend(self._extract_json_images(body, chapter.chapter_url))

        seen: set[str] = set()
        out: list[str] = []
        for image in images:
            if image not in seen:
                seen.add(image)
                out.append(image)
        return out

    def _extract_chapter_name(self, url: str, soup: BeautifulSoup) -> str:
        h1 = soup.find(["h1", "h2"])
        if h1:
            return h1.get_text(" ", strip=True)
        return urlparse(url).path.strip("/").split("/")[-1] or "chapter"

    def _language_from_html(self, soup: BeautifulSoup) -> str:
        html_tag = soup.find("html")
        lang = html_tag.get("lang") if html_tag else None
        if lang:
            return lang

        meta = soup.find("meta", attrs={"property": "og:locale"})
        if meta and meta.get("content"):
            return meta["content"]

        text = soup.get_text(" ", strip=True).lower()
        if "português" in text or "pt-br" in text:
            return "pt-br"
        return ""

    def _extract_json_images(self, script_body: str, base_url: str) -> list[str]:
        found: list[str] = []
        chunks = re.findall(r"\[(?:.|\n)*?\]", script_body)
        for chunk in chunks:
            try:
                data = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, str) and any(ext in item.lower() for ext in IMAGE_EXTENSIONS):
                        found.append(urljoin(base_url, item))
        return found
