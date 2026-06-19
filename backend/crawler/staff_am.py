import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import json
import sqlite3
from html import unescape
from pathlib import Path


def _pick_localized_text(value):
    """Extract English, Armenian, or Russian text from multilingual field."""
    if isinstance(value, dict):
        return value.get('en') or value.get('am') or value.get('ru') or ''
    return value or ''


def _html_to_text(value):
    """Convert localized HTML content into normalized plain text."""
    html = _pick_localized_text(value)
    if not html:
        return ''

    text = BeautifulSoup(html, 'html.parser').get_text("\n")
    lines = [unescape(line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _extract_skills(skills):
    """Flatten staff.am skills objects into a comma-separated string."""
    if not skills:
        return ''

    titles = []
    for skill in skills:
        title = _pick_localized_text(skill.get('title', {}))
        if title:
            titles.append(unescape(title.strip()))

    return ', '.join(titles)


def _get_session_headers():
    """Generate headers with random user-agent for requests."""
    ua = UserAgent()
    return {'User-Agent': ua.random}


def _build_job_url(job, main_page_url):
    """Build the working staff.am job URL from category code and slug."""
    slug_data = job.get('slug', {})
    category_code = job.get('category', {}).get('code', '')

    if isinstance(slug_data, dict):
        slug = slug_data.get('en') or slug_data.get('am') or slug_data.get('ru') or ''
    else:
        slug = slug_data or ''

    slug = str(slug).strip('/ ')
    category_code = str(category_code).strip('/ ')

    # Normalize malformed slug values that may already include extra segments.
    if '/' in slug:
        slug = slug.split('/')[-1]

    if category_code and slug:
        return f"{main_page_url}/en/jobs/{category_code}/{slug}"

    if slug:
        return f"{main_page_url}/en/jobs/{slug}"

    return f"{main_page_url}/en/jobs"


def _parse_job_details(job_detail):
    """Map staff.am detail-page payload into the target enrichment fields."""
    employment_type_parts = []
    job_type = _pick_localized_text(job_detail.get('job_type', {}).get('title', {}))
    job_term = _pick_localized_text(job_detail.get('job_term', {}).get('title', {}))
    candidate_level = _pick_localized_text(job_detail.get('job_candidate_level', {}).get('title', {}))

    if job_type:
        employment_type_parts.append(job_type)
    if job_term:
        employment_type_parts.append(job_term)
    if candidate_level:
        employment_type_parts.append(candidate_level)

    additional_parts = []
    additional_information = _html_to_text(job_detail.get('additional_information', {}))
    application_procedures = _html_to_text(job_detail.get('application_procedures', {}))

    if additional_information:
        additional_parts.append(additional_information)
    if application_procedures:
        additional_parts.append(application_procedures)

    return {
        'employment_type': ' | '.join(employment_type_parts) if employment_type_parts else 'N/A',
        'description': _html_to_text(job_detail.get('description', {})),
        'responsibilities': _html_to_text(job_detail.get('responsibilities', {})),
        'required_qualifications': _html_to_text(job_detail.get('required_qualifications', {})),
        'required_skills': _extract_skills(job_detail.get('skills', [])),
        'additional_info': '\n\n'.join(additional_parts)
    }


def fetch_job_details(job_id, job_url, headers=None):
    """Fetch and parse a single job detail page from staff.am."""
    request_headers = headers or _get_session_headers()

    try:
        response = requests.get(job_url, headers=request_headers, timeout=100)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        next_data_tag = soup.select_one('script#__NEXT_DATA__')

        if not next_data_tag or not next_data_tag.string:
            raise ValueError(f"No detail payload found for job {job_id}")

        next_data = json.loads(next_data_tag.string)
        job_detail = next_data.get('props', {}).get('pageProps', {}).get('job', {})
        if not job_detail:
            raise ValueError(f"No job detail found for job {job_id}")

        return _parse_job_details(job_detail)
    except Exception as e:
        print(f"Warning: could not enrich job {job_id} from {job_url}: {e}")
        return {
            'employment_type': 'N/A',
            'description': '',
            'responsibilities': '',
            'required_qualifications': '',
            'required_skills': '',
            'additional_info': ''
        }


def fetch_jobs_list():
    """
    Fetch all paginated jobs listings from staff.am jobs page.
    
    Returns:
        dict: pageProps object containing merged jobs and configuration
        
    Raises:
        Exception: If unable to fetch or parse jobs
    """
    headers = _get_session_headers()
    base_url = "https://staff.am/en/jobs"
    
    try:
        merged_page_props = None
        merged_jobs = []
        page = 1

        while True:
            response = requests.get(
                base_url,
                headers=headers,
                params={'page': page},
                timeout=10,
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # staff.am renders jobs inside Next.js page data.
            next_data_tag = soup.select_one('script#__NEXT_DATA__')
            if not next_data_tag or not next_data_tag.string:
                raise ValueError(f"No job data found in __NEXT_DATA__ script tag for page {page}")

            next_data = json.loads(next_data_tag.string)
            page_props = next_data.get('props', {}).get('pageProps', {})
            page_jobs = page_props.get('jobs', [])
            page_postings = [job for job in page_jobs if job.get('itemType') == 1]

            # Stop when there are no actual job postings on the page.
            if not page_postings:
                break

            if merged_page_props is None:
                merged_page_props = page_props.copy()

            merged_jobs.extend(page_jobs)
            page += 1

        if merged_page_props is None:
            return {'jobs': []}

        merged_page_props['jobs'] = merged_jobs
        return merged_page_props

    except Exception as e:
        raise Exception(f"Error fetching jobs list: {e}")


def load_existing_jobs_by_source_id(db_path="data/jobs.db"):
    """Load persisted job details keyed by source_job_id for crawl short-circuiting."""
    db_file = Path(db_path)
    if not db_file.exists():
        return {}

    with sqlite3.connect(db_file) as conn:
        rows = conn.execute(
            """
            SELECT
                source_job_id,
                employment_type,
                description,
                responsibilities,
                required_qualifications,
                required_skills,
                additional_info
            FROM staff_am
            WHERE source_job_id IS NOT NULL
            """
        ).fetchall()

    return {
        row[0]: {
            'employment_type': row[1] or 'N/A',
            'description': row[2] or '',
            'responsibilities': row[3] or '',
            'required_qualifications': row[4] or '',
            'required_skills': row[5] or '',
            'additional_info': row[6] or '',
        }
        for row in rows
    }


def parse_jobs_data(page_props, existing_jobs_by_id=None):
    """
    Parse and structure job data from page props.
    
    Args:
        page_props: pageProps object from __NEXT_DATA__
        
    Returns:
        list of dict: Structured job objects matching target schema
    """
    jobs = page_props.get('jobs', [])
    main_page_url = page_props.get('NEXT_PUBLIC_MAIN_PAGE_URL', 'https://staff.am')
    headers = _get_session_headers()
    existing_jobs_by_id = existing_jobs_by_id or {}
    
    extracted_jobs = []
    seen_job_ids = set()
    for job in jobs:
        # itemType == 1 are job postings; itemType == 0 are banners/ads.
        if job.get('itemType') != 1:
            continue

        source_job_id = job.get('id')
        if source_job_id in seen_job_ids:
            continue
        seen_job_ids.add(source_job_id)

        title = unescape(_pick_localized_text(job.get('title', {}))) or 'Untitled job'
        company = _pick_localized_text(job.get('companiesStruct', {}).get('title', {})) or 'Unknown company'
        city = _pick_localized_text(job.get('job_city', {}).get('title', {}))
        location = 'Remote' if job.get('is_remote') else (city or 'N/A')
        category = _pick_localized_text(job.get('category', {}).get('title', {})) or 'N/A'

        url = _build_job_url(job, main_page_url)

        deadline = job.get('deadline', 'N/A')

        additional_flags = []
        if job.get('is_remote'):
            additional_flags.append('Remote')
        if job.get('is_hot'):
            additional_flags.append('Hot')
        if job.get('is_featured'):
            additional_flags.append('Featured')

        cached_detail_fields = existing_jobs_by_id.get(source_job_id)
        if cached_detail_fields:
            detail_fields = cached_detail_fields
            additional_info = detail_fields.get('additional_info', '')
        else:
            detail_fields = fetch_job_details(job.get('id'), url, headers=headers)
            additional_info = '\n\n'.join(
                part for part in [
                    ', '.join(additional_flags) if additional_flags else '',
                    detail_fields.get('additional_info', '')
                ] if part
            )

        extracted_jobs.append({
            'source_job_id': source_job_id,
            'title': title,
            'url': url,
            'company': company,
            'location': location,
            'category': category,
            'employment_type': detail_fields.get('employment_type', 'N/A'),
            'description': detail_fields.get('description', ''),
            'responsibilities': detail_fields.get('responsibilities', ''),
            'required_qualifications': detail_fields.get('required_qualifications', ''),
            'required_skills': detail_fields.get('required_skills', ''),
            'additional_info': additional_info,
            'deadline': deadline
        })

    return extracted_jobs


def init_db(db_path="data/jobs.db"):
    """Create the shared SQLite database and staff_am table if they do not exist."""
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_file) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS staff_am (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_job_id INTEGER,
                url TEXT NOT NULL UNIQUE,
                title TEXT,
                company TEXT,
                location TEXT,
                category TEXT,
                employment_type TEXT,
                description TEXT,
                responsibilities TEXT,
                required_qualifications TEXT,
                required_skills TEXT,
                additional_info TEXT,
                deadline TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Prevent duplicates by stable source job id.
        conn.execute("DROP INDEX IF EXISTS idx_staff_am_source_job_id")
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_staff_am_source_job_id
            ON staff_am(source_job_id)
            """
        )


def save_jobs_to_db(jobs, db_path="data/jobs.db"):
    """Upsert scraped jobs into the staff_am table using source_job_id / URL as the unique key."""
    with sqlite3.connect(db_path) as conn:
        for job in jobs:
            source_job_id = job.get('source_job_id')
            row = (
                job.get('url', ''),
                job.get('title', ''),
                job.get('company', ''),
                job.get('location', ''),
                job.get('category', ''),
                job.get('employment_type', ''),
                job.get('description', ''),
                job.get('responsibilities', ''),
                job.get('required_qualifications', ''),
                job.get('required_skills', ''),
                job.get('additional_info', ''),
                job.get('deadline', ''),
                source_job_id,
            )

            # 1) Prefer stable source_job_id if already present.
            updated = conn.execute(
                """
                UPDATE staff_am
                SET
                    url=?,
                    title=?,
                    company=?,
                    location=?,
                    category=?,
                    employment_type=?,
                    description=?,
                    responsibilities=?,
                    required_qualifications=?,
                    required_skills=?,
                    additional_info=?,
                    deadline=?,
                    source_job_id=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE source_job_id=?
                """,
                row + (source_job_id,),
            )

            if updated.rowcount:
                continue

            # 2) Fallback to URL upsert (also backfills source_job_id for old rows).
            conn.execute(
                """
                INSERT INTO staff_am (
                    url,
                    title,
                    company,
                    location,
                    category,
                    employment_type,
                    description,
                    responsibilities,
                    required_qualifications,
                    required_skills,
                    additional_info,
                    deadline,
                    source_job_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
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
                    deadline=excluded.deadline,
                    source_job_id=excluded.source_job_id,
                    updated_at=CURRENT_TIMESTAMP
                """,
                row,
            )


if __name__ == "__main__":
    try:
        init_db()
        page_props = fetch_jobs_list()
        existing_jobs_by_id = load_existing_jobs_by_source_id()
        jobs = parse_jobs_data(page_props, existing_jobs_by_id=existing_jobs_by_id)
        save_jobs_to_db(jobs)
        print(json.dumps(jobs, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Error: {e}", file=__import__('sys').stderr)
        exit(1)
