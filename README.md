# Downloader de Mangás (CLI assíncrona)

Script Python (arquivo único) para baixar capítulos de mangá com suporte aos sites:

- `https://mangataro.org`
- `https://weebdex.org`
- `https://beta.kuromangas.com`
- `https://mangadex.org`

O downloader foi feito para uso responsável, com `User-Agent` customizável, delay entre requests por host e tentativas com backoff.

---

## Requisitos

- Python **3.10+**
- Dependências Python:
  - `aiohttp`
  - `aiofiles`
  - `beautifulsoup4`
  - `tqdm`

### Instalação

```bash
pip install aiohttp aiofiles beautifulsoup4 tqdm
```

Você também pode verificar o comando de instalação com:

```bash
python downloader.py --deps
```

---

## Instalação / Execução rápida

No diretório do projeto:

```bash
python downloader.py --help
```

Para baixar um título/capítulo:

```bash
python downloader.py --url "https://mangadex.org/title/<id>" --outdir ./Manga --concurrency 10 \
  --lang pt-br
```

Para baixar várias URLs de um arquivo:

```bash
python downloader.py --input urls.txt --cbz --concurrency 6 --delay 0.5 \
  --lang pt-br
```

---

## Como funciona

1. Detecta automaticamente o site com base no host da URL.
2. Resolve metadados do capítulo:
   - nome canônico do mangá
   - número/identificador do capítulo
3. Extrai a lista de páginas na ordem.
4. Faz download concorrente das imagens.
5. Salva com zero-padding (`001.jpg`, `002.jpg`, ...).
6. Opcionalmente cria arquivo `.cbz` por capítulo (`--cbz`).
7. Gera resumo em JSON com os metadados e estatísticas.

---

## Estrutura de saída

Por padrão, os arquivos são gravados em `./Manga`.

Estrutura por capítulo:

```text
Manga/
  <manga_name>/
    ch_<cap_num>/
      001.jpg
      002.jpg
      ...
```

Resumo JSON:

```text
Manga/download_summary.json
```

---

## Parâmetros da CLI

| Parâmetro | Descrição |
|---|---|
| `--url URL` | URL única para processar (capítulo ou título, dependendo do site). |
| `--input FILE` | Arquivo com múltiplas URLs (uma por linha). |
| `--outdir DIR` | Diretório de saída. Padrão: `./Manga`. |
| `--concurrency N` | Quantidade de downloads concorrentes por capítulo. |
| `--delay SECS` | Delay mínimo entre requests por host (rate-limit simples). |
| `--cbz` | Gera `.cbz` para cada capítulo ao concluir o download. |
| `--threads` | Compatibilidade de interface; implementação interna permanece assíncrona. |
| `--async` | Sinaliza uso do modo assíncrono. |
| `--user-agent STRING` | Define um `User-Agent` customizado. |
| `--deps` | Imprime dependências e encerra. |
| `--lang LANG` | Idioma para capítulos no MangaDex. Padrão: `pt-br`. |

> Observação: use `--url` **ou** `--input` (pode combinar, mas normalmente usa-se um dos dois).

---

## MangaDex: comportamento específico

- Para URL de capítulo (`/chapter/<id>`), usa API pública:
  - `GET /chapter/{id}`
  - `GET /at-home/server/{id}`
- Para URL de título (`/title/<id>`), expande capítulos consultando `GET /chapter?manga=<id>` em paginação, filtrando por idioma (`--lang`, padrão `pt-br`).

Isso melhora confiabilidade da extração das páginas em comparação com scraping puro.

---

## Retomada de download (resume)

Se o arquivo da página já existir e tiver tamanho maior que zero, o script pula o download dessa página.

Isso permite retomar execução interrompida sem baixar tudo novamente.

---

## Logs e monitoramento

- Logs em níveis `INFO`, `WARNING` e `ERROR`.
- Barra de progresso por capítulo.
- Barra de progresso global (todas as páginas).
- Throughput global ao final (páginas/segundo).

---

## Erros e tentativas automáticas

Erros de rede e HTTP comuns são tratados com retry e backoff exponencial, incluindo:

- `403`
- `404`
- `429`
- `500`, `502`, `503`, `504`

Após exceder tentativas, a página falha é registrada em log e o processo segue para as demais.

---

## Boas práticas de uso

- Respeite os termos de uso dos sites.
- Evite concorrência agressiva (comece com `--concurrency 4` a `8`).
- Use `--delay` para reduzir impacto no host (`0.3` a `1.0` costuma ser razoável).
- Defina um `--user-agent` identificável quando necessário.

Exemplo conservador:

```bash
python downloader.py --input urls.txt --concurrency 4 --delay 0.8 --user-agent "MeuDownloader/1.0"
```

---

## Exemplos práticos

### 1) Título no MangaDex, saída customizada

```bash
python downloader.py \
  --url "https://mangadex.org/title/<id>" \
  --outdir /dados/manga \
  --concurrency 10 \
  --lang pt-br
```

### 2) Lote de URLs + geração de CBZ

```bash
python downloader.py \
  --input urls.txt \
  --cbz \
  --concurrency 6 \
  --delay 0.5 \
  --lang pt-br
```

### 3) URL única com User-Agent customizado

```bash
python downloader.py \
  --url "https://mangataro.org/algum-capitulo" \
  --user-agent "MeuBot/1.0" \
  --async
```

---

## Solução de problemas

- **`ModuleNotFoundError`**: instale as dependências com `pip install aiohttp aiofiles beautifulsoup4 tqdm`.
- **Sem páginas encontradas**: a estrutura HTML do site pode ter mudado; tente novamente depois ou valide a URL.
- **Erros 429 frequentes**: reduza `--concurrency` e aumente `--delay`.
- **Muitos erros 403**: ajuste `--user-agent` e verifique bloqueios do host.

---

## Aviso legal

Use esta ferramenta apenas para conteúdo que você tenha direito de acessar/baixar e sempre em conformidade com leis locais e termos dos sites.
