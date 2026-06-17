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

---

## Database
* **Path**: `data/jobs.db` — Automatically created/updated by the crawlers. Use `sqlite3` to inspect the contents.

---

## Run LinkedIn Crawler
* **File**: `backend/crawler/linkedin.py`
* **Example**:
    ```bash
    python backend/crawler/linkedin.py \
      --keywords "Data Engineer" \
      --location "Armenia" \
      --date-posted week \
      --max-pages 2 \
      --delay 0.5
    ```
* **Flags**:
    * `--keywords`: Search query.
    * `--location`: Text location or mapped geoId.
    * `--date-posted`: Filter by `day`, `week`, `month`, or `any`.
    * `--max-pages`: Limit the number of pages to crawl.
    * `--delay`: Seconds between requests to avoid rate limiting.

---

## Run staff.am Crawler
* **File**: `backend/crawler/staff_am.py`
* **Example**:
    ```bash
    python backend/crawler/staff_am.py \
      --max-pages 5 \
      --delay 0.5
    ```
* **Notes**: `staff_am.py` saves data to the same `jobs.db` file (table: `staff_am`).

---

## Run LinkedIn Crawler

* **File**: `backend/crawler/linkedin.py`

### Examples
**Basic usage:**
```bash
python backend/crawler/linkedin.py \
  --keywords "Data Engineer" \
  --location "Armenia" \
  --date-posted week \
  --max-pages 2 \
  --delay 0.5


Example (single page, verbose):

```bash

python backend/crawler/linkedin.py \

  --keywords "Backend Engineer" \

  --location "Yerevan, Armenia" \

  --date-posted day \

  --max-pages 1 \

  --delay 1.0 \

  --verbose

```



Flags

- `--keywords` : search query (required)

- `--location` : text location (e.g., "Armenia" or "Yerevan, Armenia"); script may map some locations to LinkedIn `geoId`

- `--date-posted` : `day` | `week` | `month` | `any`

- `--max-pages` : number of result pages to fetch

- `--delay` : seconds to wait between requests (use to reduce rate-limiting)

- `--verbose` : enable more logging (if implemented)



Notes

- LinkedIn may return listings outside the exact text `--location`. For better targeting, `linkedin.py` can use known `geoId` mappings (see the `GEO_ID_MAP` in the file) and the script may also perform post-parse location filtering—which can reduce saved results if LinkedIn returns loosely-labeled cards.

- Results are saved into jobs.db (table `linkedin`). Inspect with:

```bash

sqlite3 data/jobs.db "SELECT count(*) FROM linkedin;"

```

---

## Inspect DB
* **Count records**:
    ```bash
    sqlite3 data/jobs.db "SELECT count(*) FROM linkedin;"
    sqlite3 data/jobs.db "SELECT count(*) FROM staff_am;"
    ```

---

## Troubleshooting
* **Location Issues**: If crawlers return few or no rows for a strict `--location`, try a broader location string or use known `geoId` mappings found within `linkedin.py`.
* **Request Failures**: Ensure stable network access and verify that all dependencies are installed in your virtual environment: `requests`, `beautifulsoup4`, `lxml`, and `fake-useragent`.