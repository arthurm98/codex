# Manga Downloader (GUI)

Aplicação de download de mangás PT-BR com interface moderna em **PySide6**.

## Estrutura

```text
.
├── main.py
├── build_exe.bat
├── requirements.txt
└── downloader/
    ├── core/
    ├── extractors/
    ├── gui/
    │   ├── main_window.py
    │   ├── theme.py
    │   └── widgets.py
    └── utils/
```

## Fontes suportadas

- MangaDex (`mangadex.org`)
- MangáTarō (`mangataro`)
- KuroMangas (`kuromangas`)
- Mugiwaras Oficial (`mugiwarasoficial.com`)
- Sites WordPress de leitura

## Executar

```bash
pip install -r requirements.txt
python main.py
```

## Build para Windows 11

```bash
pyinstaller --noconfirm --onefile --windowed --name MangaDownloader main.py
```

Ou execute:

```bat
build_exe.bat
```

Saída esperada: `dist/MangaDownloader.exe`.
