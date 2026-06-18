# Project Documentation

## Quick Start

* **Prereqs**: Python 3.8+ and git.
* **Virtualenv**: Create and activate the environment:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```
* **Install deps**:
    ```bash
    pip install -r requirements.txt
    ```
* **Dependencies used by the crawlers**: `requests`, `beautifulsoup4`, `lxml`, `fake-useragent` (installed via `requirements.txt`).

---

## Database

* **Path**: `data/jobs.db` — created and updated automatically by the crawlers. No manual setup required.
* **Tables**:
    * `linkedin` — populated by `backend/crawler/linkedin.py`
    * `staff_am` — populated by `backend/crawler/staff_am.py`

**Inspect the database:**
```bash
sqlite3 data/jobs.db "SELECT count(*) FROM linkedin;"
sqlite3 data/jobs.db "SELECT count(*) FROM staff_am;"
```

---

## Running Crawlers Manually

### LinkedIn Crawler

* **File**: `backend/crawler/linkedin.py`

**Basic usage:**
```bash
python backend/crawler/linkedin.py \
  --keywords "Data Engineer" \
  --location "Armenia" \
  --date-posted week \
  --max-pages 2 \
  --delay 0.5
```

**Single page, verbose example:**
```bash
python backend/crawler/linkedin.py \
  --keywords "Backend Engineer" \
  --location "Yerevan, Armenia" \
  --date-posted day \
  --max-pages 1 \
  --delay 1.0 \
  --verbose
```

**Flags:**

| Flag | Description |
|------|-------------|
| `--keywords` | Search query (required) |
| `--location` | Text location (e.g., `"Armenia"` or `"Yerevan, Armenia"`); the script may map known locations to a LinkedIn `geoId` |
| `--date-posted` | `day` \| `week` \| `month` \| `any` |
| `--max-pages` | Number of result pages to fetch |
| `--delay` | Seconds to wait between requests (reduces rate-limiting) |
| `--verbose` | Enable additional logging (if implemented) |

**Note on location accuracy:** LinkedIn may return listings outside the exact text passed to `--location`. For better targeting, `linkedin.py` uses known `geoId` mappings (see `GEO_ID_MAP` in the file) and may also post-filter parsed results by location — which can reduce the number of saved results when LinkedIn returns loosely-labeled cards.

Results are saved to `jobs.db` (table `linkedin`).

### staff.am Crawler

* **File**: `backend/crawler/staff_am.py`

**Basic usage:**
```bash
python backend/crawler/staff_am.py \
  --max-pages 5 \
  --delay 0.5
```

Results are saved to `jobs.db` (table `staff_am`).

---

## Automated Hourly Runner

`scripts/run_crawlers.sh` runs both crawlers on a schedule and writes logs to `data/logs/`. It uses a lock file to prevent overlapping runs and expects a virtualenv at `.venv` (edit the `PY` variable in the script if you use a different Python).

**Make it executable:**
```bash
chmod +x scripts/run_crawlers.sh
```

**Run immediately** (for testing, with console output):
```bash
./scripts/run_crawlers.sh
```

**Schedule hourly with cron** (runs at minute 0 every hour):
```bash
crontab -e
```
Add the line:
```
0 * * * * /full/path/to/band-of-agents-hackathon/scripts/run_crawlers.sh
```

**View logs live:**
```bash
tail -F data/logs/linkedin-*.log data/logs/staff_am-*.log
```

**Notes:**
* The crawlers update `jobs.db` automatically on every run — no manual DB steps required. Use manual runs (above) only for testing or debugging.
* The lock file prevents concurrent runs. Removing this logic to allow overlapping runs is not recommended.
* Logs are timestamped per run (UTC).

---

## Troubleshooting

* **Few or no results for a `--location`**: Try a broader location string, or check `GEO_ID_MAP` in `linkedin.py` for a known-good mapping.
* **Request failures**: Confirm network access is stable and that all dependencies (`requests`, `beautifulsoup4`, `lxml`, `fake-useragent`) are installed in your active virtual environment.
