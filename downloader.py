#!/usr/bin/env python3
"""
Dependências (Python 3.10+):
  - aiohttp
  - aiofiles
  - beautifulsoup4
  - tqdm

Instalação rápida:
  pip install aiohttp aiofiles beautifulsoup4 tqdm
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import aiofiles
import aiohttp
from bs4 import BeautifulSoup
from tqdm import tqdm

INSTALL_HINT = "pip install aiohttp aiofiles beautifulsoup4 tqdm"
DEFAULT_UA = (
    "MangaDownloader/1.0 (+https://example.local; educational use; "
    "respect robots and site ToS)"
)

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")
SCRIPT_URL_PATTERN = re.compile(r"https?://[^\"'\s>]+(?:jpg|jpeg|png|webp|gif|avif)", re.I)


@dataclass
class ChapterTask:
    source_url: str
    manga_title: str
    chapter_num: str
    page_urls: list[str]
    site: str


class HostRateLimiter:
    """Rate-limit simples por host com delay mínimo entre requests."""

    def __init__(self, delay: float):
        self.delay = max(0.0, delay)
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_request: dict[str, float] = {}

    async def wait(self, host: str) -> None:
        if self.delay <= 0:
            return
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            last = self._last_request.get(host, 0.0)
            sleep_for = self.delay - (now - last)
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            self._last_request[host] = time.monotonic()


class Fetcher:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        limiter: HostRateLimiter,
        retries: int = 4,
        timeout: int = 30,
    ):
        self.session = session
        self.limiter = limiter
        self.retries = retries
        self.timeout = timeout

    async def fetch_text(self, url: str) -> str:
        return await self._fetch(url, as_text=True)

    async def fetch_bytes(self, url: str) -> bytes:
        return await self._fetch(url, as_text=False)

    async def fetch_json(self, url: str) -> dict:
        raw = await self._fetch(url, as_text=True)
        return json.loads(raw)

    async def _fetch(self, url: str, as_text: bool):
        host = urlparse(url).netloc
        last_error: Exception | None = None

        for attempt in range(1, self.retries + 1):
            await self.limiter.wait(host)
            try:
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                async with self.session.get(url, timeout=timeout) as resp:
                    if resp.status in {403, 404, 429, 500, 502, 503, 504}:
                        raise aiohttp.ClientResponseError(
                            request_info=resp.request_info,
                            history=resp.history,
                            status=resp.status,
                            message=f"HTTP {resp.status}",
                            headers=resp.headers,
                        )
                    resp.raise_for_status()
                    return await (resp.text() if as_text else resp.read())
            except Exception as exc:
                last_error = exc
                backoff = min(8.0, 0.6 * (2 ** (attempt - 1)))
                jitter = 0.1 * attempt
                logging.warning(
                    "Falha ao buscar %s (tentativa %d/%d): %s",
                    url,
                    attempt,
                    self.retries,
                    exc,
                )
                if attempt < self.retries:
                    await asyncio.sleep(backoff + jitter)

        assert last_error is not None
        raise last_error


def sanitize_name(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|]+", "_", value).strip()
    return value or "untitled"


def parse_chapter_label(text: str) -> str:
    if not text:
        return "unknown"
    m = re.search(r"(?:cap(?:i?tulo)?|chapter|ch)\s*([\d.]+)", text, flags=re.I)
    if m:
        return m.group(1)
    m2 = re.search(r"([\d]+(?:\.[\d]+)?)", text)
    return m2.group(1) if m2 else sanitize_name(text)[:40]


def unique_ordered(urls: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for u in urls:
        if not u:
            continue
        if u not in seen:
            seen.add(u)
            result.append(u)
    return result


def _extract_image_candidates_from_html(url: str, html: str) -> tuple[str, str, list[str]]:
    soup = BeautifulSoup(html, "html.parser")

    title_meta = soup.find("meta", attrs={"property": "og:title"})
    page_title = title_meta.get("content") if title_meta else (soup.title.string if soup.title else "")
    page_title = (page_title or "").strip()

    manga_title = "Unknown_Manga"
    chapter_num = "unknown"

    h1 = soup.find(["h1", "h2"])
    if h1 and h1.get_text(strip=True):
        htxt = h1.get_text(" ", strip=True)
        chapter_num = parse_chapter_label(htxt)
        base = re.split(r"(?:chapter|cap[ií]tulo|ch)\b", htxt, flags=re.I)[0].strip(" -:")
        manga_title = base or manga_title

    if manga_title == "Unknown_Manga" and page_title:
        chapter_num = parse_chapter_label(page_title)
        parts = re.split(r"\s[-|:]\s", page_title)
        if parts:
            manga_title = parts[0].strip() or manga_title

    image_urls: list[str] = []

    for img in soup.find_all("img"):
        for attr in ("data-src", "data-lazy-src", "data-original", "src", "data-url"):
            src = img.get(attr)
            if not src:
                continue
            src = urljoin(url, src)
            if any(ext in src.lower() for ext in IMAGE_EXTENSIONS):
                image_urls.append(src)

    for script in soup.find_all("script"):
        content = script.string or script.get_text(" ", strip=True)
        if not content:
            continue
        for match in SCRIPT_URL_PATTERN.findall(content):
            image_urls.append(urljoin(url, match))

    image_urls = unique_ordered(image_urls)
    return sanitize_name(manga_title), sanitize_name(chapter_num), image_urls


async def extract_mangataro(url: str, fetcher: Fetcher) -> tuple[str, str, list[str]]:
    html = await fetcher.fetch_text(url)
    return _extract_image_candidates_from_html(url, html)


async def extract_weebdex(url: str, fetcher: Fetcher) -> tuple[str, str, list[str]]:
    html = await fetcher.fetch_text(url)
    return _extract_image_candidates_from_html(url, html)


async def extract_kuromangas(url: str, fetcher: Fetcher) -> tuple[str, str, list[str]]:
    html = await fetcher.fetch_text(url)
    return _extract_image_candidates_from_html(url, html)


async def extract_mangadex(url: str, fetcher: Fetcher) -> tuple[str, str, list[str]]:
    """Extrai páginas de um capítulo do MangaDex via API pública."""
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    chapter_id = None

    if "chapter" in parts:
        idx = parts.index("chapter")
        if idx + 1 < len(parts):
            chapter_id = parts[idx + 1]

    if not chapter_id:
        raise ValueError(f"URL do Mangadex não parece capítulo: {url}")

    chapter_api = (
        f"https://api.mangadex.org/chapter/{chapter_id}?includes[]=manga&includes[]=scanlation_group"
    )
    chapter_payload = await fetcher.fetch_json(chapter_api)
    data = chapter_payload.get("data", {})
    attrs = data.get("attributes", {})

    chapter_num = attrs.get("chapter") or attrs.get("title") or chapter_id
    chapter_num = sanitize_name(str(chapter_num))

    manga_title = "Unknown_Manga"
    for rel in data.get("relationships", []):
        if rel.get("type") == "manga":
            tdata = rel.get("attributes", {}).get("title", {})
            if isinstance(tdata, dict) and tdata:
                manga_title = next(iter(tdata.values()))
                break
    manga_title = sanitize_name(manga_title)

    at_home_url = f"https://api.mangadex.org/at-home/server/{chapter_id}"
    server_payload = await fetcher.fetch_json(at_home_url)
    base = server_payload["baseUrl"]
    c_hash = server_payload["chapter"]["hash"]
    data_pages = server_payload["chapter"].get("data") or []

    page_urls = [f"{base}/data/{c_hash}/{fname}" for fname in data_pages]
    return manga_title, chapter_num, page_urls


async def mangadex_title_to_chapter_urls(url: str, fetcher: Fetcher, lang: str) -> list[str]:
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    if "title" not in parts:
        return [url]
    idx = parts.index("title")
    if idx + 1 >= len(parts):
        return [url]

    manga_id = parts[idx + 1]
    offset = 0
    limit = 100
    chapter_urls: list[str] = []

    while True:
        api = (
            "https://api.mangadex.org/chapter"
            f"?manga={manga_id}&translatedLanguage[]={lang}&order[chapter]=asc"
            f"&limit={limit}&offset={offset}"
        )
        payload = await fetcher.fetch_json(api)
        items = payload.get("data", [])
        total = payload.get("total", len(items))
        for item in items:
            cid = item.get("id")
            if cid:
                chapter_urls.append(f"https://mangadex.org/chapter/{cid}")
        offset += len(items)
        if offset >= total or not items:
            break

    return unique_ordered(chapter_urls) or [url]


def detect_site(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "mangadex.org" in host:
        return "mangadex"
    if "mangataro.org" in host:
        return "mangataro"
    if "weebdex.org" in host:
        return "weebdex"
    if "kuromangas.com" in host:
        return "kuromangas"
    return "unknown"


async def extract_chapter(site: str, url: str, fetcher: Fetcher) -> ChapterTask:
    if site == "mangadex":
        manga_title, chapter_num, page_urls = await extract_mangadex(url, fetcher)
    elif site == "mangataro":
        manga_title, chapter_num, page_urls = await extract_mangataro(url, fetcher)
    elif site == "weebdex":
        manga_title, chapter_num, page_urls = await extract_weebdex(url, fetcher)
    elif site == "kuromangas":
        manga_title, chapter_num, page_urls = await extract_kuromangas(url, fetcher)
    else:
        raise ValueError(f"Site não suportado: {url}")

    if not page_urls:
        raise ValueError(f"Nenhuma imagem encontrada em: {url}")

    return ChapterTask(
        source_url=url,
        manga_title=manga_title,
        chapter_num=chapter_num,
        page_urls=page_urls,
        site=site,
    )


async def save_image(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "wb") as f:
        await f.write(content)


def infer_ext_from_url(url: str) -> str:
    lower = url.lower()
    for ext in IMAGE_EXTENSIONS:
        if ext in lower:
            return ".jpg" if ext == ".jpeg" else ext
    return ".jpg"


async def download_chapter(
    chapter: ChapterTask,
    outdir: Path,
    fetcher: Fetcher,
    concurrency: int,
    global_progress: tqdm,
) -> dict:
    ch_dir = outdir / sanitize_name(chapter.manga_title) / f"ch_{sanitize_name(chapter.chapter_num)}"
    ch_dir.mkdir(parents=True, exist_ok=True)

    total = len(chapter.page_urls)
    digits = max(3, len(str(total)))
    sem = asyncio.Semaphore(concurrency)

    stats = {
        "manga_title": chapter.manga_title,
        "chapter": chapter.chapter_num,
        "site": chapter.site,
        "source_url": chapter.source_url,
        "pages_total": total,
        "pages_downloaded": 0,
        "pages_skipped_existing": 0,
        "pages_failed": 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(ch_dir),
    }

    pbar = tqdm(total=total, desc=f"{chapter.manga_title} ch {chapter.chapter_num}", leave=False)

    async def worker(i: int, page_url: str):
        ext = infer_ext_from_url(page_url)
        filename = f"{i:0{digits}d}{ext}"
        fpath = ch_dir / filename

        if fpath.exists() and fpath.stat().st_size > 0:
            stats["pages_skipped_existing"] += 1
            pbar.update(1)
            global_progress.update(1)
            return

        async with sem:
            try:
                content = await fetcher.fetch_bytes(page_url)
                await save_image(fpath, content)
                stats["pages_downloaded"] += 1
            except Exception as exc:
                stats["pages_failed"] += 1
                logging.error("Falha definitiva imagem %s: %s", page_url, exc)
            finally:
                pbar.update(1)
                global_progress.update(1)

    await asyncio.gather(*(worker(i, u) for i, u in enumerate(chapter.page_urls, start=1)))
    pbar.close()
    return stats


def build_cbz(chapter_dir: Path) -> Path:
    cbz_path = chapter_dir.with_suffix(".cbz")
    files = sorted([p for p in chapter_dir.iterdir() if p.is_file()])
    with zipfile.ZipFile(cbz_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, arcname=f.name)
    return cbz_path


async def resolve_urls(args: argparse.Namespace, fetcher: Fetcher) -> list[str]:
    urls: list[str] = []
    if args.url:
        urls.append(args.url.strip())
    if args.input:
        path = Path(args.input)
        content = path.read_text(encoding="utf-8")
        urls.extend([line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")])

    expanded: list[str] = []
    for u in urls:
        site = detect_site(u)
        if site == "mangadex" and "/title/" in u:
            logging.info("Expandindo título do Mangadex: %s (idioma=%s)", u, args.lang)
            chapter_urls = await mangadex_title_to_chapter_urls(u, fetcher, args.lang)
            expanded.extend(chapter_urls)
        else:
            expanded.append(u)

    return unique_ordered(expanded)


def configure_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Downloader robusto de mangás (CLI)")
    parser.add_argument("--input", help="Arquivo com URLs (uma por linha)")
    parser.add_argument("--url", help="URL única de mangá/capítulo")
    parser.add_argument("--outdir", default="./Manga", help="Diretório de saída (default: ./Manga)")
    parser.add_argument("--concurrency", type=int, default=8, help="Número de downloads concorrentes")
    parser.add_argument("--delay", type=float, default=0.25, help="Delay (segundos) entre requests por host")
    parser.add_argument("--cbz", action="store_true", help="Gerar arquivo .cbz por capítulo")
    parser.add_argument("--user-agent", default=DEFAULT_UA, help="User-Agent customizado")
    parser.add_argument("--deps", action="store_true", help="Mostra dependências e sai")
    parser.add_argument("--lang", default="pt-br", help="Idioma para capítulos do MangaDex (default: pt-br)")

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--threads", action="store_true", help="Modo threads (compatibilidade; usa async internamente)")
    mode_group.add_argument("--async", dest="force_async", action="store_true", help="Força modo asyncio")

    return parser.parse_args()


async def run(args: argparse.Namespace) -> int:
    args.lang = (args.lang or "pt-br").strip().lower()

    if args.threads:
        logging.warning("Flag --threads selecionada; este script usa implementação asyncio/aiohttp.")

    if not args.url and not args.input:
        logging.error("Informe --url ou --input.")
        return 2

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    headers = {
        "User-Agent": args.user_agent,
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        "Referer": "https://google.com/",
    }

    timeout = aiohttp.ClientTimeout(total=40)
    limiter = HostRateLimiter(delay=args.delay)
    connector = aiohttp.TCPConnector(limit=max(8, args.concurrency * 2))

    summary: list[dict] = []

    async with aiohttp.ClientSession(headers=headers, timeout=timeout, connector=connector) as session:
        fetcher = Fetcher(session=session, limiter=limiter)
        urls = await resolve_urls(args, fetcher)
        if not urls:
            logging.error("Nenhuma URL processável encontrada.")
            return 3

        logging.info("Total de URLs para processar: %d", len(urls))

        chapter_tasks: list[ChapterTask] = []
        for u in urls:
            site = detect_site(u)
            if site == "unknown":
                logging.error("Site não suportado: %s", u)
                continue
            try:
                ch = await extract_chapter(site, u, fetcher)
                chapter_tasks.append(ch)
            except Exception as exc:
                logging.error("Falha na extração de %s: %s", u, exc)

        if not chapter_tasks:
            logging.error("Nenhum capítulo válido extraído.")
            return 4

        total_pages = sum(len(c.page_urls) for c in chapter_tasks)
        global_progress = tqdm(total=total_pages, desc="Total páginas", position=0)

        start = time.perf_counter()
        for ch in chapter_tasks:
            stats = await download_chapter(
                chapter=ch,
                outdir=outdir,
                fetcher=fetcher,
                concurrency=args.concurrency,
                global_progress=global_progress,
            )
            if args.cbz:
                cbz_path = build_cbz(Path(stats["output_dir"]))
                stats["cbz_path"] = str(cbz_path)
            summary.append(stats)

        elapsed = max(0.001, time.perf_counter() - start)
        throughput = total_pages / elapsed
        global_progress.close()
        logging.info("Throughput global: %.2f páginas/s", throughput)

    summary_path = outdir / "download_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("Resumo salvo em %s", summary_path)

    return 0


def main() -> int:
    args = configure_args()

    if args.deps:
        print(INSTALL_HINT)
        return 0

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())


# USAGE
# 1) python downloader.py --url "https://mangadex.org/title/<id>" --outdir /dados/manga --concurrency 10
# 2) python downloader.py --input urls.txt --cbz --concurrency 6 --delay 0.5
# 3) python downloader.py --url "https://mangataro.org/algum-capitulo" --user-agent "MeuBot/1.0" --async
