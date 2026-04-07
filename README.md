# Sagre in Liguria

App per consultare le sagre e feste gastronomiche della Liguria.

## Architettura

```
claude-px03-sagre/
├── .github/workflows/scrape.yml   # cron notturno alle 02:00 UTC
├── scraper/
│   ├── scrape.py                  # orchestratore (auto-discovery plugin)
│   ├── merge.py                   # deduplicazione
│   └── sources/
│       ├── sagreautentiche.py
│       └── mangiareinliguria.py
├── data/sagre.json                # dati aggiornati ogni notte
├── web/
│   ├── index.html
│   └── app.js
└── requirements.txt
```

## Come aggiungere una sorgente

1. Crea `scraper/sources/nuovosito.py`
2. Esponi una funzione `def scrape() -> list[dict]`
3. Ogni dict deve avere: `nome, comune, provincia, regione, data_inizio, data_fine, descrizione, url, immagine, stato, fonte`

Per disabilitare una sorgente senza cancellarla: rinomina il file con underscore iniziale (`_nuovosito.py`).

## Esecuzione manuale

```bash
pip install -r requirements.txt
python scraper/scrape.py
```

## Deploy

- **Scraper**: GitHub Actions esegue `scrape.py` ogni notte, fa commit di `data/sagre.json`
- **Frontend**: GitHub Pages serve la cartella `web/` (configurare nelle impostazioni del repo)
