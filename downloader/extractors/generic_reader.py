from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from downloader.core.fetcher import Fetcher
from downloader.core.models import Chapter
from downloader.core.utils import IMAGE_EXTENSIONS, is_pt_br, sanitize_name
from downloader.extractors.base import BaseExtractor

SCRIPT_URL_PATTERN = re.compile(r"https?://[^\"'\s<>]+(?:jpg|jpeg|png|webp|avif)(?:\?[^\"'\s<>]*)?", re.I)
PLACEHOLDER_TOKENS = ("placeholder", "spacer", "blank.gif", "lazyload")


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
        images = self._extract_images_from_soup(soup, chapter.chapter_url)

        # fallback para lazy loading agressivo em conteúdo renderizado dentro de <noscript>
        for noscript in soup.select("noscript"):
            body = noscript.decode_contents()
            if not body:
                continue
            nested = BeautifulSoup(body, "html.parser")
            images.extend(self._extract_images_from_soup(nested, chapter.chapter_url))

        seen: set[str] = set()
        out: list[str] = []
        for image in images:
            normalized = image.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                out.append(normalized)
        return out

    def _extract_images_from_soup(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        images: list[str] = []

        for img in soup.select("img"):
            for attr in (
                "src",
                "data-src",
                "data-lazy",
                "data-lazy-src",
                "data-original",
                "data-pagespeed-lazy-src",
                "data-srcset",
                "srcset",
            ):
                raw = img.get(attr)
                if not raw:
                    continue
                for candidate in self._expand_image_candidates(raw):
                    if self._looks_like_image(candidate) and self._is_real_image(candidate):
                        images.append(urljoin(base_url, candidate))

        for script in soup.select("script"):
            body = script.string or script.get_text(" ", strip=True)
            if not body:
                continue
            images.extend(SCRIPT_URL_PATTERN.findall(body))
            images.extend(self._extract_json_images(body, base_url))

        return images

    def _expand_image_candidates(self, raw: str) -> list[str]:
        parts = [chunk.strip() for chunk in raw.split(",") if chunk.strip()]
        if len(parts) <= 1:
            return [raw.strip()]

        expanded: list[str] = []
        for part in parts:
            candidate = part.split()[0].strip()
            if candidate:
                expanded.append(candidate)
        return expanded

    def _looks_like_image(self, value: str) -> bool:
        value_lower = value.lower()
        return any(ext in value_lower for ext in IMAGE_EXTENSIONS)

    def _is_real_image(self, value: str) -> bool:
        value_lower = value.lower()
        if value_lower.startswith("data:image"):
            return False
        return not any(token in value_lower for token in PLACEHOLDER_TOKENS)

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
                    if isinstance(item, str) and self._looks_like_image(item) and self._is_real_image(item):
                        found.append(urljoin(base_url, item))
        return found
