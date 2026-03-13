# Universal PT-BR Manga Downloader (CLI)

Downloader assíncrono modular, focado **apenas em capítulos PT-BR**.

## Estrutura

```text
.
├── manga_downloader.py
├── requirements.txt
└── downloader/
    ├── main.py
    ├── cli/
    │   └── args.py
    ├── core/
    │   ├── downloader.py
    │   ├── fetcher.py
    │   ├── models.py
    │   ├── rate_limiter.py
    │   └── utils.py
    ├── extractors/
    │   ├── base.py
    │   ├── generic_reader.py
    │   ├── kuromangas.py
    │   ├── mangadex.py
    │   ├── mangataro.py
    │   └── wp_manga.py
    └── output/
        └── cbz.py
```

## Instalação

```bash
pip install -r requirements.txt
```

## Uso

```bash
python manga_downloader.py \
  --url https://mangadex.org/title/<id> \
  --lang pt-br \
  --cbz \
  --concurrency 10
```

```bash
python manga_downloader.py --input urls.txt --resume --delay 0.3
```

## Regras de idioma

Aceitos:
- `pt-br`
- `pt`
- `pt_BR`
- `brazilian-portuguese`

Sem idioma detectável: capítulo é ignorado.

## Saída

```text
Manga/
  MangaTitle/
    ch_001/
      001.jpg
      002.jpg
```

Resumo JSON em `Manga/download_summary.json`.
