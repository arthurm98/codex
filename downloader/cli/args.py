from __future__ import annotations

import argparse


PT_BR_ACCEPTED = ["pt-br", "pt", "pt_BR", "brazilian-portuguese"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Universal PT-BR manga downloader")
    parser.add_argument("--url", action="append", help="Manga URL (can be repeated)")
    parser.add_argument("--input", help="Text file with URLs")
    parser.add_argument("--lang", default="pt-br", help="Language filter (default: pt-br)")
    parser.add_argument("--outdir", default="Manga", help="Output directory")
    parser.add_argument("--concurrency", type=int, default=10, help="Parallel download count")
    parser.add_argument("--delay", type=float, default=0.2, help="Per-host delay in seconds")
    parser.add_argument("--cbz", action="store_true", help="Create CBZ after chapter download")
    parser.add_argument("--resume", action="store_true", help="Skip already downloaded pages")
    args = parser.parse_args()

    if args.lang not in PT_BR_ACCEPTED:
        raise SystemExit(f"Unsupported lang '{args.lang}'. Accepted: {', '.join(PT_BR_ACCEPTED)}")
    return args
