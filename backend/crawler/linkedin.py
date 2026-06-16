"""
LinkedIn public job crawler.

Usage:
    python linkedin.py --keywords "Python Engineer" --location "Armenia"
    python linkedin.py --keywords "Data Engineer" --location "Yerevan" --date-posted week
    python linkedin.py --keywords "AI Engineer" --location "Remote" --date-posted day --max-pages 5

Date filter options: any | day | week | month
"""

import argparse
import json
import re
import sqlite3
import sys
import time
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


def _log(msg):
    """Write progress messages to stderr so stdout stays clean JSON."""
    print(msg, file=sys.stderr, flush=True)

# ─── Constants ────────────────────────────────────────────────────────────────

LINKEDIN_BASE = "https://www.linkedin.com"
SEARCH_URL    = f"{LINKEDIN_BASE}/jobs/search/"
VIEW_URL      = f"{LINKEDIN_BASE}/jobs/view/{{job_id}}/"
PAGE_SIZE     = 25  # LinkedIn returns 25 results per page

# f_TPR values for LinkedIn date-posted filter
DATE_POSTED_MAP = {
    "any":   "",
    "day":   "r86400",
    "week":  "r604800",
    "month": "r2592000",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ─── Utilities ────────────────────────────────────────────────────────────────

def _clean_text(element):
    """Return stripped plain text from a BeautifulSoup element, or empty string."""
    if not element:
        return ""
    return " ".join(element.get_text(separator=" ").split())


def _job_id_from_urn(urn: str) -> str | None:
    """Extract numeric job ID from a LinkedIn URN like 'urn:li:jobPosting:12345'."""
    m = re.search(r":jobPosting:(\d+)$", urn or "")
    return m.group(1) if m else None


# ─── Listing page ─────────────────────────────────────────────────────────────

def _fetch_search_page(session, keywords, location, date_posted, start):
    """Fetch one paginated search results page and return (html, status_code)."""
    
    GEO_ID_MAP = {
        "armenia":  "103030111",  # Armenia's geo ID
        "yerevan":  "102475833",  # Yerevan's geo ID
    }
    
    params = {
        "keywords": keywords,
        "start":    start,
    }
    
    geo_id = GEO_ID_MAP.get(location.lower())
    if geo_id:
        params["geoId"] = geo_id
    else:
        params["location"] = location  # fallback to plain text

    date_filter = DATE_POSTED_MAP.get(date_posted, "")
    if date_filter:
        params["f_TPR"] = date_filter

    resp = session.get(SEARCH_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.text


def _parse_search_page(html):
    """
    Parse job listing cards from a LinkedIn search results page.

    Returns a list of dicts with:
        source_job_id, title, company, location, posted_date, url
    """
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.base-card[data-entity-urn]")

    jobs = []
    for card in cards:
        urn = card.get("data-entity-urn", "")
        job_id = _job_id_from_urn(urn)
        if not job_id:
            continue

        title_el   = card.select_one("h3.base-search-card__title")
        company_el = card.select_one("h4.base-search-card__subtitle")
        location_el = card.select_one(".job-search-card__location")
        date_el    = card.select_one("time")
        link_el    = card.select_one("a.base-card__full-link") or card.select_one("a[href*='/jobs/view/']")

        url = ""
        if link_el and link_el.get("href"):
            # Strip tracking query params, keep clean canonical URL
            raw = link_el["href"]
            parsed = urlparse(raw)
            url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        jobs.append({
            "source_job_id": int(job_id),
            "title":         unescape(_clean_text(title_el)),
            "company":       unescape(_clean_text(company_el)),
            "location":      unescape(_clean_text(location_el)),
            "posted_date":   date_el.get("datetime", "") if date_el else "",
            "url":           url or VIEW_URL.format(job_id=job_id),
        })

    return jobs


def fetch_all_job_listings(keywords, location, date_posted="any", max_pages=None, delay=1.0):
    """
    Paginate through LinkedIn job search and collect all listing cards.

    Args:
        keywords:    Job title / search query.
        location:    Location string (city, country, or 'Remote').
        date_posted: One of 'any', 'day', 'week', 'month'.
        max_pages:   Optional cap on number of pages to crawl.
        delay:       Seconds to wait between page requests (rate limiting).

    Returns:
        list of dicts from _parse_search_page, deduplicated by source_job_id.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    all_jobs  = []
    seen_ids  = set()
    page      = 0

    while True:
        if max_pages and page >= max_pages:
            break

        start = page * PAGE_SIZE
        try:
            html = _fetch_search_page(session, keywords, location, date_posted, start)
        except Exception as e:
            _log(f"Warning: failed to fetch page {page + 1}: {e}")
            break

        page_jobs = _parse_search_page(html)

        # Stop when page returns no new jobs
        new_jobs = [j for j in page_jobs if j["source_job_id"] not in seen_ids]
        if not new_jobs:
            break

        for job in new_jobs:
            seen_ids.add(job["source_job_id"])
            all_jobs.append(job)

        _log(f"  Page {page + 1}: {len(new_jobs)} new jobs (total so far: {len(all_jobs)})")
        page += 1

        if page_jobs and len(page_jobs) < PAGE_SIZE:
            # Last partial page — no more results
            break

        time.sleep(delay)

    return all_jobs


# ─── Detail page ──────────────────────────────────────────────────────────────

def _parse_criteria(soup):
    """Extract seniority, employment type, job function, and industry from detail page."""
    criteria = {}
    for item in soup.select(".description__job-criteria-item"):
        header = _clean_text(item.select_one("h3")).lower()
        value  = _clean_text(item.select_one("span"))
        if "seniority" in header:
            criteria["seniority"] = value
        elif "employment" in header:
            criteria["employment_type"] = value
        elif "function" in header:
            criteria["job_function"] = value
        elif "industr" in header:
            criteria["industry"] = value
    return criteria


def fetch_job_details(source_job_id, job_url, session=None):
    """
    Fetch and parse a single LinkedIn job detail page.

    Returns:
        dict with description, responsibilities, required_qualifications,
              required_skills, employment_type, additional_info, posted_date.
    """
    _session = session or requests.Session()
    _session.headers.update(HEADERS)

    empty = {
        "employment_type":        "",
        "description":            "",
        "responsibilities":       "",
        "required_qualifications": "",
        "required_skills":        "",
        "additional_info":        "",
        "posted_date":            "",
    }

    try:
        resp = _session.get(job_url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Full description block
        desc_el = (
            soup.select_one(".show-more-less-html__markup")
            or soup.select_one(".description__text--rich")
            or soup.select_one(".description__text")
        )
        description = _clean_text(desc_el) if desc_el else ""

        # Criteria sidebar
        criteria = _parse_criteria(soup)

        # Posted date
        date_el = soup.select_one("time")
        posted_date = date_el.get("datetime", "") if date_el else ""

        return {
            "employment_type":        criteria.get("employment_type", ""),
            "description":            description,
            "responsibilities":       "",   # LinkedIn embeds this in description
            "required_qualifications": "",  # LinkedIn embeds this in description
            "required_skills":        criteria.get("job_function", ""),
            "additional_info":        criteria.get("industry", ""),
            "posted_date":            posted_date,
        }

    except Exception as e:
        _log(f"Warning: could not enrich job {source_job_id} from {job_url}: {e}")
        return empty


# ─── Database ─────────────────────────────────────────────────────────────────

def init_db(db_path="data/jobs.db"):
    """Create the shared SQLite database and linkedin table if they do not exist."""
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_file) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS linkedin (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                source_job_id         INTEGER NOT NULL UNIQUE,
                url                   TEXT NOT NULL,
                title                 TEXT,
                company               TEXT,
                location              TEXT,
                category              TEXT,
                employment_type       TEXT,
                description           TEXT,
                responsibilities      TEXT,
                required_qualifications TEXT,
                required_skills       TEXT,
                additional_info       TEXT,
                posted_date           TEXT,
                keywords              TEXT,
                updated_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def load_existing_jobs_by_source_id(db_path="data/jobs.db"):
    """Load persisted job details keyed by source_job_id for crawl short-circuiting."""
    db_file = Path(db_path)
    if not db_file.exists():
        return {}

    with sqlite3.connect(db_file) as conn:
        rows = conn.execute(
            """
            SELECT source_job_id, employment_type, description, responsibilities,
                   required_qualifications, required_skills, additional_info, posted_date
            FROM linkedin
            """
        ).fetchall()

    return {
        row[0]: {
            "employment_type":        row[1] or "",
            "description":            row[2] or "",
            "responsibilities":       row[3] or "",
            "required_qualifications": row[4] or "",
            "required_skills":        row[5] or "",
            "additional_info":        row[6] or "",
            "posted_date":            row[7] or "",
        }
        for row in rows
    }


def save_jobs_to_db(jobs, keywords="", db_path="data/jobs.db"):
    """Upsert scraped jobs into the linkedin table, keyed by source_job_id."""
    with sqlite3.connect(db_path) as conn:
        for job in jobs:
            conn.execute(
                """
                INSERT INTO linkedin (
                    source_job_id, url, title, company, location, category,
                    employment_type, description, responsibilities,
                    required_qualifications, required_skills, additional_info,
                    posted_date, keywords
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_job_id) DO UPDATE SET
                    url=excluded.url,
                    title=excluded.title,
                    company=excluded.company,
                    location=excluded.location,
                    category=excluded.category,
                    employment_type=excluded.employment_type,
                    description=excluded.description,
                    responsibilities=excluded.responsibilities,
                    required_qualifications=excluded.required_qualifications,
                    required_skills=excluded.required_skills,
                    additional_info=excluded.additional_info,
                    posted_date=excluded.posted_date,
                    keywords=excluded.keywords,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    job.get("source_job_id"),
                    job.get("url", ""),
                    job.get("title", ""),
                    job.get("company", ""),
                    job.get("location", ""),
                    job.get("category", ""),
                    job.get("employment_type", ""),
                    job.get("description", ""),
                    job.get("responsibilities", ""),
                    job.get("required_qualifications", ""),
                    job.get("required_skills", ""),
                    job.get("additional_info", ""),
                    job.get("posted_date", ""),
                    keywords,
                ),
            )


# ─── Orchestration ────────────────────────────────────────────────────────────

def crawl(keywords, location, date_posted="any", max_pages=None, delay=1.0,
          db_path="data/jobs.db"):
    """
    Full crawl pipeline:
      1. Paginate listings → collect job stubs.
      2. Skip detail fetch for jobs already in DB.
      3. Enrich new jobs from detail pages.
      4. Upsert all to SQLite.

    Returns:
        list of complete job dicts matching the target JSON schema.
    """
    _log(f"[LinkedIn] Crawling: keywords={keywords!r}, location={location!r}, "
          f"date_posted={date_posted!r}")

    init_db(db_path)
    existing = load_existing_jobs_by_source_id(db_path)
    _log(f"[LinkedIn] {len(existing)} jobs already in DB (will skip detail fetch).")

    listings = fetch_all_job_listings(
        keywords=keywords,
        location=location,
        date_posted=date_posted,
        max_pages=max_pages,
        delay=delay,
    )
    _log(f"[LinkedIn] {len(listings)} total listings collected.")

    session = requests.Session()
    session.headers.update(HEADERS)

    enriched_jobs = []
    for listing in listings:
        job_id = listing["source_job_id"]

        # Short-circuit: reuse stored detail if job already in DB.
        if job_id in existing:
            details = existing[job_id]
        else:
            _log(f"  Fetching details for job {job_id} …")
            details = fetch_job_details(job_id, listing["url"], session=session)
            time.sleep(delay)

        enriched_jobs.append({
            "source_job_id":          job_id,
            "title":                  listing["title"],
            "url":                    listing["url"],
            "company":                listing["company"],
            "location":               listing["location"],
            "category":               details.get("additional_info", ""),
            "employment_type":        details.get("employment_type", ""),
            "description":            details.get("description", ""),
            "responsibilities":       details.get("responsibilities", ""),
            "required_qualifications": details.get("required_qualifications", ""),
            "required_skills":        details.get("required_skills", ""),
            "additional_info":        "",
            "posted_date":            listing.get("posted_date") or details.get("posted_date", ""),
            "deadline":               "",
        })

    save_jobs_to_db(enriched_jobs, keywords=keywords, db_path=db_path)
    _log(f"[LinkedIn] Saved {len(enriched_jobs)} jobs to {db_path}.")
    return enriched_jobs


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawl LinkedIn public job postings.")
    parser.add_argument("--keywords",    required=True, help='Job title, e.g. "Python Engineer"')
    parser.add_argument("--location",    required=True, help='Location, e.g. "Armenia" or "Remote"')
    parser.add_argument("--date-posted", default="any",
                        choices=["any", "day", "week", "month"],
                        help="Filter by posting date (default: any)")
    parser.add_argument("--max-pages",   type=int, default=None,
                        help="Max listing pages to fetch (default: unlimited)")
    parser.add_argument("--delay",       type=float, default=1.0,
                        help="Delay in seconds between requests (default: 1.0)")
    parser.add_argument("--db",          default="data/jobs.db",
                        help="SQLite DB path (default: data/jobs.db)")
    args = parser.parse_args()

    jobs = crawl(
        keywords=args.keywords,
        location=args.location,
        date_posted=args.date_posted,
        max_pages=args.max_pages,
        delay=args.delay,
        db_path=args.db,
    )
    print(json.dumps(jobs, ensure_ascii=False, indent=2))
