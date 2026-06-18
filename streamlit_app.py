import streamlit as st
import sqlite3
import os
import random
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import time
import requests
import json
import threading
import subprocess
from pathlib import Path
import streamlit as st

crawler_lock = threading.Lock()
        
        
BAND_API_URL = "https://api.band.ai/v1/messages"  # placeholder
BAND_API_KEY = os.getenv("BAND_API_KEY", "demo-key")

DB_PATH = Path("data/jobs.db")

def seed_db_if_empty():
    if DB_PATH.exists() and db_has_rows(DB_PATH):
        return

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS linkedin (
            title TEXT,
            company TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS staff_am (
            title TEXT,
            company TEXT
        )
    """)

    sample_jobs = [
    ("Senior Data Engineer", "Google"),
    ("Data Engineer - Analytics Platform", "Amazon"),
    ("Analytics Engineer (dbt + Snowflake)", "Netflix"),
    ("Backend Data Engineer (Kafka/Python)", "Meta"),
    ("ML Data Engineer (Feature Pipelines)", "Spotify"),
    ("Streaming Data Engineer (Kafka, Flink)", "Uber"),
    ("AdTech Data Engineer (RTB / Bid Data)", "The Trade Desk"),
    ("Data Platform Engineer (Airflow + AWS)", "Airbnb"),
    ("Data Engineer - BigQuery Pipelines", "Stripe"),
    ("ETL Engineer (Batch + Real-time Systems)", "Databricks"),
    ("Data Engineer - Marketing Analytics", "LinkedIn"),
    ("Data Engineer (ClickHouse / OLAP)", "Pinterest"),
    ("Analytics Engineer - Revenue Systems", "Snap Inc."),
    ("Data Engineer - Cloud Data Lake", "Apple"),
    ("Data Engineer (Python, SQL, Spark)", "Microsoft"),
    ]

    cur.executemany("INSERT INTO linkedin VALUES (?,?)", sample_jobs)
    conn.commit()
    conn.close()
    
    
def run_crawlers_bg():
    with crawler_lock:
        logdir = Path("data/logs")
        logdir.mkdir(parents=True, exist_ok=True)

        ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        out = logdir / f"crawler-{ts}.log"

        st.session_state["crawler_status"] = "running"

        with open(out, "ab") as f:
            process = subprocess.Popen(
                ["/bin/bash", "scripts/run_crawlers.sh"],
                stdout=f,
                stderr=subprocess.STDOUT,
                cwd=os.getcwd()
            )

            process.wait()

        st.session_state["crawler_status"] = "done"
        
        
def db_has_rows(db_path: Path) -> bool:
    try:
        with sqlite3.connect(db_path) as conn:
            total = 0
            for t in ("linkedin", "staff_am"):
                try:
                    cur = conn.execute(f"SELECT count(*) FROM {t}")
                    total += cur.fetchone()[0] or 0
                except Exception:
                    pass
            return total > 0
    except Exception:
        return False

if "crawler_status" not in st.session_state:
    st.session_state["crawler_status"] = "idle"

db_empty = (not DB_PATH.exists()) or (not db_has_rows(DB_PATH))

st.sidebar.subheader("🧠 Data Pipeline Status")

st.sidebar.write(f"Status: {st.session_state['crawler_status']}")

if db_empty:
    st.sidebar.warning("DB empty — crawlers not yet run")
    if st.sidebar.button("▶ Initialize Data Pipeline"):
        seed_db_if_empty()
        st.session_state["crawler_status"] = "starting"
        threading.Thread(target=run_crawlers_bg, daemon=True).start()
        st.rerun()
else:
    st.sidebar.success("DB ready — jobs loaded")

# -----------------------------
# Helpers
# -----------------------------
def load_jobs(limit=20):
    """
    Load jobs from SQLite DB.
    Fallback to mock data if DB doesn't exist.
    """
    if not DB_PATH.exists():
        return [
            ("Data Engineer", "ABC Corp"),
            ("Backend Engineer", "XYZ Ltd"),
            ("Python Developer", "TechSoft"),
        ]

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT title, company
            FROM linkedin
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return [("No jobs found", "DB Empty")]

        return rows

    except Exception:
        return [("Error reading DB", "Check schema")]


def simulate_band_agents(jobs):
    """
    Simulate 3-agent collaboration through Band.
    """

    st.subheader("🤖 Multi-Agent Workflow (Band Simulation)")

    st.info("Agent 1 (Job Ingestor): Processing incoming jobs...")

    processed_jobs = []
    for title, company in jobs:
        processed_jobs.append({
            "title": title,
            "company": company,
            "score_input": random.randint(60, 100)
        })

    st.success(f"Agent 1 completed: {len(processed_jobs)} jobs processed")

    st.info("Agent 2 (Match Scorer): Scoring jobs against profile...")

    scored_jobs = []
    for job in processed_jobs:
        score = job["score_input"] + random.randint(-10, 10)
        score = max(0, min(100, score))

        job["score"] = score
        scored_jobs.append(job)

    scored_jobs.sort(key=lambda x: x["score"], reverse=True)

    st.success("Agent 2 completed: Jobs ranked")

    st.info("Agent 3 (Recommendation Generator): Creating insights...")

    top_jobs = scored_jobs[:5]

    recommendations = [
        f"{job['title']} at {job['company']} (Match: {job['score']}%)"
        for job in top_jobs
    ]

    st.success("Agent 3 completed: Recommendations generated")

    return scored_jobs, recommendations


# -----------------------------
# UI
# -----------------------------
st.set_page_config(page_title="Band Multi-Agent Job System", layout="wide")
interval=60000  # 1 minute for live demo video later should be 3600000 for 1 hour in production
st_autorefresh(interval=interval, key="hourly_refresh")

st.sidebar.info("🔁 Auto-refresh enabled (every 1 minute)")
st.sidebar.caption("Simulates cron job for job ingestion pipeline")

st.title("🚀 Band Multi-Agent Job Assistant")
st.caption("Hackathon Demo: Multi-agent system with job crawling + Band coordination")


# -----------------------------
# Section 1: Jobs
# -----------------------------
st.header("📊 Latest Jobs")

jobs = load_jobs()

st.subheader("📊 Latest Jobs")

for title, company in jobs:
    st.markdown(f"""
    <div style="
        padding:12px;
        border-radius:10px;
        border:1px solid #ddd;
        margin-bottom:8px;
        background-color:#0f172a;
        color:white;
    ">
        <h4 style="margin:0;">💼 {title}</h4>
        <p style="margin:0; opacity:0.8;">🏢 {company}</p>
    </div>
    """, unsafe_allow_html=True)



# -----------------------------
# Section 2: Run Demo
# -----------------------------
st.header("🧠 Multi-Agent Demo")

if st.button("▶ Run Demo"):

    st.write("---")
    st.write(f"🕒 Demo started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    st.info("Fetching jobs from system...")

    scored_jobs, recommendations = simulate_band_agents(jobs)

    st.write("---")

    st.subheader("🏆 Top Recommendations")

    for r in recommendations:
        st.success(r)

    st.write("---")

    st.subheader("📈 Full Scored Jobs")

    st.dataframe(scored_jobs)

    st.write("---")

    st.subheader("📡 Band Message Simulation")

    st.code(
        """
{
  "from": "agent_1",
  "to": "band_room",
  "type": "job_update",
  "payload": {
    "jobs_fetched": 10,
    "timestamp": "2026-06-19"
  }
}

{
  "from": "agent_2",
  "to": "agent_3",
  "type": "scoring_result",
  "payload": {
    "top_jobs": "Data Engineer, Backend Engineer"
  }
}
        """,
        language="json"
    )

    st.success("Demo completed successfully 🎯")


# -----------------------------
# Footer
# -----------------------------
st.write("---")
st.caption("Built for Band of Agents Hackathon | Multi-Agent Collaboration System")

st.metric("Jobs Processed", len(jobs))
st.metric("Top Match Score", "92%")
st.metric("Agents Active", "3")

st.info("📡 Note: In production, agents communicate through a shared Band Room using Band SDK/API. This demo simulates that communication layer for clarity.")