# Sri Lanka Leptospirosis Dataset

A weekly, district-level time series of leptospirosis case counts in Sri Lanka (2007–present), built by scraping and parsing the **Weekly Epidemiological Report (WER)** PDFs published by the [Epidemiology Unit, Ministry of Health, Sri Lanka](https://www.epid.gov.lk/weekly-epidemiological-report).

This dataset was built as part of my final year research project. It is not an official government dataset — it is a machine-extracted reconstruction of the WER tables, and should be validated against source PDFs before being used in any downstream analysis. See [Known issues & caveats](#known-issues--caveats) below.

## What's in this repo

```
lepto_scraper/
├── 01_get_links.py                        # Step 1: crawl the WER archive page, collect PDF links + metadata
├── 02_download_pdfs.py                    # Step 2: download every PDF into ./pdfs/
├── 03_parse_leptospirosis.py              # Step 3: extract leptospirosis case counts per district from each PDF
├── debug_inspect.py                       # Utility: dump raw extracted text from a PDF for troubleshooting
├── wer_pdf_links.json                     # Output of Step 1 (also updated by Step 2 with local file paths)
├── download_failures.json                 # PDFs that failed to download in Step 2
├── leptospirosis_weekly_by_district.csv   # Final output: parsed case counts (main dataset)
└── failed_parses.csv                      # PDFs that Step 3 could not parse, with reasons
```

`pdfs/` (the downloaded WER reports) is **not committed to this repo** due to size — run Steps 1–2 to (re)generate it locally.

## Data source

Sri Lanka's Epidemiology Unit publishes a WER PDF every week, containing a "Notifiable Diseases Reported by Medical Officers of Health" table with weekly and cumulative case counts for ~25 diseases across all districts. Leptospirosis is the 6th disease listed in that table.

- Source page: https://www.epid.gov.lk/weekly-epidemiological-report
- Coverage in this dataset: **2007 (Week 1) to mid-2026**, spanning 1,014 discovered PDF reports

## Pipeline

The pipeline runs in three stages, each producing an intermediate file consumed by the next:

**1. `01_get_links.py` — Discover reports**
Crawls the WER archive page (plus any extra archive URLs added to `EXTRA_SEED_URLS`), extracts every PDF link along with its labelled year, week number, and date range, and follows pagination. Writes `wer_pdf_links.json`.

**2. `02_download_pdfs.py` — Download PDFs**
Downloads every PDF referenced in `wer_pdf_links.json` into `pdfs/`, naming each file `{year}_w{week}_{original_filename}`. Resumable — re-running skips files that already exist. Failures (e.g. dropped connections) are logged to `download_failures.json` rather than stopping the run.

**3. `03_parse_leptospirosis.py` — Extract case counts**
Uses PyMuPDF to locate the notifiable-diseases table in each PDF, identify each district's row by matching district names, and pull out the leptospirosis weekly (`A`) and cumulative (`B`) counts — the 11th and 12th numbers in each district's row. Writes `leptospirosis_weekly_by_district.csv`. PDFs where a valid table (≥15 recognizable district rows) can't be found are logged to `failed_parses.csv`.

**`debug_inspect.py`** is a standalone helper for dumping the raw text PyMuPDF extracts from a specific PDF — useful when a report fails to parse and you need to see why.

## Dataset: `leptospirosis_weekly_by_district.csv`

| Column | Description |
|---|---|
| `year` | Year label taken from the WER archive listing |
| `week` | Epidemiological week number, as labelled in the archive |
| `start_date` / `end_date` | Date range as labelled by the archive (see caveat below) |
| `district` | One of Sri Lanka's 25 districts |
| `leptospirosis_cases_week` | Leptospirosis cases reported for that week (column "A" in the WER table) |
| `leptospirosis_cases_cumulative` | Cumulative cases reported for the year to date (column "B") |
| `parse_method` | Parser version used, and notes on any districts with incomplete data on that page |
| `source_pdf` | Local path to the source PDF, for traceability |

Current size: **~25,300 rows** across **25 districts** and **20 years** (2007–2026).

## Known issues & caveats

These matter for anyone using this data downstream — please read before analysis:

- **One-week reporting lag.** The archive labels each report with a "Week N" tag, but the table *inside* each PDF actually covers the **previous** week. `03_parse_leptospirosis.py` records the archive's own label as-is (for traceability back to the source file) and does **not** correct for this. If you need the true epidemiological week the data covers, subtract 7 days from `start_date`/`end_date` (or 1 from `week`) during your own analysis — this correction has not yet been applied anywhere in this pipeline.
- **Kalmunai / Ampara merge.** Some reports split Ampara district's reporting into two separate RDHS (Regional Director of Health Services) divisions — "Ampara" and "Kalmunai" — even though Kalmunai is administratively part of Ampara. The parser detects both and sums Kalmunai's counts into Ampara's to produce one district-level figure. If Ampara wasn't separately captured on a given page, Kalmunai's numbers are used directly as Ampara's total.
- **Failed downloads (3 PDFs, see `download_failures.json`):** dropped connections for weeks 2012-W07, 2013-W42, and 2017-W19. Re-run `02_download_pdfs.py` to retry — it will skip already-downloaded files.
- **Failed parses (2 PDFs, see `failed_parses.csv`):** e.g. 2010-W50, where the parser couldn't locate a page with enough recognizable district rows (report may use a non-standard layout, or the leptospirosis-region table may be a scanned image rather than machine-readable text).
- **Older years (pre-2007).** Reports before 2007 were not found via the current archive page/pagination logic. If you locate an archive URL or "load more" endpoint that surfaces them, add it to `EXTRA_SEED_URLS` in `01_get_links.py`.
- **Not officially verified.** These figures are extracted by pattern-matching PDF text, not sourced from an official machine-readable dataset. Spot-check parsed rows against source PDFs (via `debug_inspect.py`) before using this data in publications.

## Setup & usage

**Requirements:** Python 3, `requests`, `beautifulsoup4`, `pymupdf`

```bash
pip install requests beautifulsoup4 pymupdf
```

**Run the full pipeline:**

```bash
cd lepto_scraper
python 01_get_links.py           # -> wer_pdf_links.json
python 02_download_pdfs.py       # -> pdfs/, download_failures.json
python 03_parse_leptospirosis.py # -> leptospirosis_weekly_by_district.csv, failed_parses.csv
```

Re-running any step is safe: link discovery de-duplicates by PDF URL, downloads skip existing files, and parsing simply regenerates the output CSVs.

**Debugging a specific PDF:**

Edit `TARGET_FILES` in `debug_inspect.py` to point at the PDF in question, then run it to see the raw text PyMuPDF extracts from each page.

## Attribution

The underlying case data is sourced from the publicly available Weekly Epidemiological Reports of the Epidemiology Unit, Ministry of Health, Sri Lanka (https://www.epid.gov.lk). Please credit the Epidemiology Unit as the original data source in any published work, alongside this repository for the extraction pipeline.

Data used here for non-commercial academic research purposes. This repository does not claim ownership of the underlying case data, only of the extraction and parsing pipeline used to compile it.

## Citation

If you use this dataset, please cite the repository:

> Sandamini, H. (2026). *SriLanka_Leptospirosis_Dataset* [Dataset]. GitHub. https://github.com/hsandamini/SriLanka_Leptospirosis_Dataset

## License

- **Code** (all scripts in `lepto_scraper/`): [MIT License](https://opensource.org/licenses/MIT) — free to reuse, modify, and redistribute with attribution.
- **Dataset** (`leptospirosis_weekly_by_district.csv` and other derived outputs): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — free to share and adapt with attribution to this repository.
- **Underlying source data**: remains the property of the Epidemiology Unit, Ministry of Health, Sri Lanka, and must be attributed to them regardless of how the code or dataset above is licensed.

See the [`LICENSE`](./LICENSE) file for the full MIT text.
