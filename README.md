# Sagre in Liguria

App per consultare le sagre e feste gastronomiche della Liguria.

## Architettura

```
claude-px03-sagre/
├── .github/workflows/scrape.yml   # cron notturno alle 02:00 UTC
├── scraper/
│   ├── scrape.py                  # orchestratore (auto-discovery plugin)
│   ├── merge.py                   # filtro food + deduplicazione
│   └── sources/
│       ├── mangiareinliguria.py   # scraping HTML da mangiareinliguria.it
│       ├── sagreautentiche.py     # scraping HTML da sagreautentiche.it
│       └── llm_liguria.py         # discovery via Claude API (LLM)
├── data/sagre.json                # dati aggiornati ogni notte
├── web/
│   ├── index.html
│   └── app.js
└── requirements.txt
```

## Filtro eventi gastronomici (`merge.py`)

Ogni evento raccolto dalle sorgenti passa attraverso `_is_food_event()` prima di essere incluso nel dataset. La logica è a tre livelli:

```
nome + descrizione dell'evento
        │
        ▼
┌──────────────────────────────────────┐
│  Contiene parola chiave FOOD?        │ ──► SÌ  → INCLUDI
│  (sagra, vino, pesce, focaccia …)   │
└──────────────────────────────────────┘
        │ NO
        ▼
┌──────────────────────────────────────┐
│  Contiene parola chiave NON-FOOD?    │ ──► SÌ  → ESCLUDI
│  (concerto, maratona, gran fondo …) │
└──────────────────────────────────────┘
        │ NO
        ▼
        INCLUDI (beneficio del dubbio — le sorgenti sono tematiche)
```

### Parole chiave food (selezione)

| Categoria     | Esempi                                                    |
|---------------|-----------------------------------------------------------|
| Evento        | `sagra`, `gastronomico`, `degustazione`, `street food`    |
| Pesce         | `pesce`, `acciughe`, `baccalà`, `polpo`, `gamberi`        |
| Prodotti      | `focaccia`, `farinata`, `pesto`, `olio`, `tartufo`        |
| Bevande       | `vino`, `birra`, `grappa`, `sciacchetrà`, `vermentino`    |
| Carni         | `cinghiale`, `agnello`, `salumi`, `formaggio`             |
| Dolci/altro   | `castagne`, `miele`, `frutta`, `gelato`                   |

### Parole chiave non-food (selezione)

| Categoria   | Esempi                                                        |
|-------------|---------------------------------------------------------------|
| Musica      | `concerto`, `jazz`, `orchestra`, `band`                       |
| Sport       | `maratona`, `gran fondo`, `granfondo`, `ciclistica`, `regata` |
| Arte        | `mostra`, `esposizione`, `pittura`, `cinema`                  |
| Altro       | `processione`, `antiquariato`, `mercatino di natale`          |

### Aggiungere o correggere keyword

Apri `scraper/merge.py` e modifica `_FOOD_KEYWORDS` o `_NONFOOD_KEYWORDS`.  
Usa il prefisso `\b` per evitare corrispondenze parziali.

Se un evento sfugge al filtro (falso positivo), aggiungi il termine più
specifico possibile alla lista `_NONFOOD_KEYWORDS`. Esempio: `gran.?fondo`
anziché il generico `fondo`.

## Sorgenti dati

### Scraper HTML
`mangiareinliguria.py` e `sagreautentiche.py` raccolgono eventi da siti
dedicati agli eventi liguri. Questi siti pubblicano **tutti** gli eventi
(non solo food), quindi il filtro `merge.py` è essenziale.

### Sorgente LLM (`llm_liguria.py`)
Interroga Claude (Haiku) per i mesi corrente + 2 successivi con il prompt:

> *Ricerca eventi culinari, sagre e feste gastronomiche in Liguria
> per il mese/i di {mesi} {anno}. Per ogni evento includi: nome, località
> e provincia, date precise, breve descrizione del piatto o prodotto tipico
> celebrato. Indica se si tratta di un Evento Autentico riconosciuto dalla
> Regione. Ordina i risultati cronologicamente.*

Il system prompt vincola Claude a rispondere **solo con JSON** e a includere
esclusivamente eventi gastronomici. La risposta viene validata e normalizzata
prima dell'inserimento.

Richiede la variabile d'ambiente `ANTHROPIC_API_KEY`. Se assente, la sorgente
viene saltata senza errori (le altre sorgenti continuano a funzionare).

**Indicatore UI**: quando almeno un evento proviene da `llm_liguria`, il tema
grafico dell'app passa da verde a blu.

## Come aggiungere una sorgente

1. Crea `scraper/sources/nuovosito.py`
2. Esponi una funzione `def scrape() -> list[dict]`
3. Ogni dict deve avere: `nome, comune, provincia, regione, data_inizio, data_fine, descrizione, url, immagine, stato, fonte`

Per disabilitare una sorgente senza cancellarla: rinomina il file con underscore iniziale (`_nuovosito.py`).

## Esecuzione manuale

```bash
pip install -r requirements.txt
python scraper/scrape.py

# Con sorgente LLM:
ANTHROPIC_API_KEY=sk-ant-... python scraper/scrape.py
```

## Configurazione GitHub Actions

Il workflow `.github/workflows/scrape.yml` esegue lo scraper ogni notte
alle 02:00 UTC e fa commit di `data/sagre.json`.

Segreti da configurare nel repository (Settings → Secrets → Actions):

| Segreto             | Descrizione                          |
|---------------------|--------------------------------------|
| `ANTHROPIC_API_KEY` | Chiave API Anthropic per llm_liguria |

## Deploy

- **Scraper**: GitHub Actions aggiorna `data/sagre.json` ogni notte
- **Frontend**: Vercel serve la cartella `web/` (configurato in `vercel.json`)
