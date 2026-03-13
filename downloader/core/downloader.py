from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import aiofiles
import aiohttp
from tqdm.asyncio import tqdm

from downloader.core.fetcher import Fetcher
from downloader.core.models import Chapter, DownloadResult
from downloader.core.rate_limiter import HostRateLimiter
from downloader.core.utils import dump_summary, infer_ext, is_pt_br, sanitize_name
from downloader.extractors.base import BaseExtractor
from downloader.extractors.generic_reader import GenericReaderExtractor
from downloader.extractors.kuromangas import KuromangasExtractor
from downloader.extractors.mangadex import MangaDexExtractor
from downloader.extractors.mangataro import MangataroExtractor
from downloader.extractors.mugiwaras import MugiwarasExtractor
from downloader.extractors.sakuramangas import SakuraMangasExtractor
from downloader.extractors.wp_manga import WPMangaExtractor
from downloader.output.cbz import create_cbz

logger = logging.getLogger(__name__)


class MangaDownloader:
    def __init__(
        self,
        outdir: Path,
        concurrency: int,
        delay: float,
        create_cbz: bool,
        resume: bool,
        language: str,
    ) -> None:
        self.outdir = outdir
        self.concurrency = max(1, concurrency)
        self.delay = delay
        self.create_cbz = create_cbz
        self.resume = resume
        self.language = language
        self.summary: list[dict] = []

    async def run(self, urls: list[str]) -> None:
        timeout = aiohttp.ClientTimeout(total=40)
        connector = aiohttp.TCPConnector(limit=200, ttl_dns_cache=300)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            fetcher = Fetcher(session=session, limiter=HostRateLimiter(self.delay))
            for url in urls:
                extractor = self._pick_extractor(url, fetcher)
                chapters = await extractor.get_chapter_list(url, self.language)
                chapters = [chapter for chapter in chapters if is_pt_br(chapter.language)]
                if not chapters:
                    logger.warning("Skipping URL with no PT-BR chapters: %s", url)
                    continue

                for chapter in chapters:
                    result = await self._download_chapter(fetcher, extractor, chapter)
                    self.summary.append(result.__dict__)

        self.outdir.mkdir(parents=True, exist_ok=True)
        dump_summary(self.outdir / "download_summary.json", self.summary)
        logger.info("Done. Summary written to %s", self.outdir / "download_summary.json")

    def _pick_extractor(self, url: str, fetcher: Fetcher) -> BaseExtractor:
        for cls in (
            MangaDexExtractor,
            MangataroExtractor,
            KuromangasExtractor,
            MugiwarasExtractor,
            SakuraMangasExtractor,
            WPMangaExtractor,
        ):
            if cls.detect(url):
                return cls(fetcher)
        return GenericReaderExtractor(fetcher)

    async def _download_chapter(self, fetcher: Fetcher, extractor: BaseExtractor, chapter: Chapter) -> DownloadResult:
        images = await extractor.get_page_images(chapter)
        if not images:
            logger.warning("Skipping chapter with zero images: %s", chapter.chapter_url)
            return DownloadResult(chapter.manga_title, chapter.chapter_title, 0, 0, self.outdir)

        chapter_folder = self.outdir / sanitize_name(chapter.manga_title) / sanitize_name(chapter.chapter_title)
        chapter_folder.mkdir(parents=True, exist_ok=True)

        semaphore = asyncio.Semaphore(self.concurrency)
        tasks = [
            self._download_page(fetcher, chapter, image_url, chapter_folder, idx + 1, semaphore)
            for idx, image_url in enumerate(images)
        ]
        results = []
        for coro in tqdm.as_completed(tasks, desc=f"{chapter.manga_title} {chapter.chapter_title}", total=len(tasks)):
            results.append(await coro)

        ok = sum(1 for item in results if item)
        failed = len(results) - ok

        if ok and self.create_cbz:
            create_cbz(chapter_folder)

        return DownloadResult(chapter.manga_title, chapter.chapter_title, ok, failed, chapter_folder)

    async def _download_page(
        self,
        fetcher: Fetcher,
        chapter: Chapter,
        image_url: str,
        chapter_folder: Path,
        page_num: int,
        semaphore: asyncio.Semaphore,
    ) -> bool:
        ext = infer_ext(image_url)
        out_file = chapter_folder / f"{page_num:03d}{ext}"

        if self.resume and out_file.exists() and out_file.stat().st_size > 0:
            return True

        async with semaphore:
            try:
                payload = await fetcher.get_bytes(image_url, referer=chapter.chapter_url)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed page %s (%s): %s", page_num, image_url, exc)
                return False

            async with aiofiles.open(out_file, "wb") as fp:
                await fp.write(payload)
            return True
