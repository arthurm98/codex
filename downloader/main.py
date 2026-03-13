from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from downloader.cli.args import parse_args
from downloader.core.downloader import MangaDownloader


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def main() -> None:
    configure_logging()
    args = parse_args()
    urls = list(args.url or [])

    if args.input:
        lines = Path(args.input).read_text(encoding="utf-8").splitlines()
        urls.extend([line.strip() for line in lines if line.strip() and not line.startswith("#")])

    if not urls:
        raise SystemExit("No URL provided. Use --url or --input.")

    downloader = MangaDownloader(
        outdir=Path(args.outdir),
        concurrency=args.concurrency,
        delay=args.delay,
        create_cbz=args.cbz,
        resume=args.resume,
        language=args.lang,
    )
    asyncio.run(downloader.run(urls))


if __name__ == "__main__":
    main()
