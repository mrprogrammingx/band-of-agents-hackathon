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

PRIMARY_DB = Path("data/jobs.db")
FALLBACK_DB = Path("data/jobs_sample.db")
crawler_lock = threading.Lock()
        
        
BAND_API_URL = "https://api.band.ai/v1/messages"  # placeholder
BAND_API_KEY = os.getenv("BAND_API_KEY", "demo-key")

demo_mode = st.sidebar.radio(
    "Select pipeline source",
    ["Auto (Smart Fallback)", "Force Live DB", "Force Sample DB", "Force Mock Data"]
)

def get_active_db(demo_mode):

    # if user overrides system
    if demo_mode == "Force Live DB":
        return PRIMARY_DB

    if demo_mode == "Force Sample DB":
        return FALLBACK_DB

    if demo_mode == "Force Mock Data":
        return None

    # default smart logic
    def db_has_data(db_path: Path) -> bool:
        if not db_path.exists():
            return False

        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()

            for table in ("linkedin", "staff_am"):
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {table}")
                    if cur.fetchone()[0] > 0:
                        conn.close()
                        return True
                except Exception:
                    continue

            conn.close()
        except Exception:
            pass

        return False

    if db_has_data(PRIMARY_DB):
        return PRIMARY_DB

    if db_has_data(FALLBACK_DB):
        return FALLBACK_DB

    return None


def get_pipeline_state(demo_mode):
    db = get_active_db(demo_mode)
    
    if db == PRIMARY_DB:
        return {
            "active_source": "Live Crawlers (jobs.db)",
            "status": "healthy",
            "color": "green"
        }

    elif db == FALLBACK_DB:
        return {
            "active_source": "Sample Dataset (jobs_sample.db)",
            "status": "fallback",
            "color": "orange"
        }

    else:
        return {
            "active_source": "In-Memory Mock Data",
            "status": "emergency",
            "color": "red"
        }
        
state = get_pipeline_state(demo_mode)
    
    
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

DB_PATH = get_active_db(demo_mode)
db_empty = (DB_PATH is None) or (not db_has_rows(DB_PATH))

st.sidebar.subheader("🧠 Data Pipeline Status")

st.subheader("📡 Pipeline Execution Flow")

st.progress(20, text="🧹 Crawlers fetching jobs")
st.progress(40, text=f"📦 Source: {state['active_source']}")
st.progress(60, text="⚙️ Processing Layer")
st.progress(80, text="🤖 Agent 1 → Agent 2")
st.progress(100, text="🏁 Agent 3 → Recommendations Ready")

st.sidebar.write(f"Status: {st.session_state['crawler_status']}")

if db_empty:
    st.sidebar.warning("DB empty — crawlers not yet run")
    if st.sidebar.button("▶ Initialize Data Pipeline"):
        st.session_state["crawler_status"] = "starting"
        threading.Thread(target=run_crawlers_bg, daemon=True).start()
        st.rerun()
else:
    st.sidebar.success("DB ready — jobs loaded")
        
# -----------------------------
# Helpers
# -----------------------------
def load_jobs(demo_mode, limit=20):
    db = get_active_db(demo_mode)

    if db == PRIMARY_DB:
        st.success("🟢 Using live crawler database")
    elif db == FALLBACK_DB:
        st.warning("🟡 Using sample fallback database")
    else:
        st.info("🔵 Using in-memory demo data")
    # 🟡 Final fallback (UI always works)
    if db is None:
        return [
                    {
            "title": "Data Engineer",
            "company": "Google",
            "location": "Remote",
            "category": "Data",
            "employment_type": "Full-time",
            "required_skills": "Python, SQL"
        },
                    {
            "title": "Backend Engineer",
            "company": "Amazon",
            "location": "Remote",
            "category": "Software",
            "employment_type": "Full-time",
            "required_skills": "Java, AWS"
        },
                    {
            "title": "ML Engineer",
            "company": "Meta",
            "location": "Remote",
            "category": "Data",
            "employment_type": "Full-time",
            "required_skills": "Python, TensorFlow"
        },
                ]

    try:
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(staff_am)")
        
        available_columns = [row[1] for row in cursor.fetchall()]

        wanted_columns = [
            "url",
            "title",
            "company",
            "location",
            "category",
            "employment_type",
            "description",
            "responsibilities",
            "required_qualifications",
            "required_skills",
            "additional_info",
            "deadline",
            "source_job_id"
        ]

        selected_columns = [
            col for col in wanted_columns
            if col in available_columns
        ]

        query = f"""
        SELECT {",".join(selected_columns)}
        FROM staff_am
        LIMIT ?
        """

        cursor.execute(query, (limit,))

        rows = cursor.fetchall()

        if not rows:
            return [{
                "title": "No jobs found",
                "company": "Empty DB",
                "location": "N/A",
                "category": "",
                "employment_type": ""
            }]

        columns = [desc[0] for desc in cursor.description]

        jobs = [dict(zip(columns, row)) for row in rows]

        return jobs

    except Exception as e:
        return [{
            "title": "Error reading DB",
            "company": "Check schema",
            "location": "N/A",
            "category": "",
            "employment_type": ""
        }]
    
  
def simulate_band_agents(jobs):
    """
    Simulate 3-agent collaboration through Band.
    """

    st.subheader("🤖 Multi-Agent Workflow (Band Simulation)")

    st.info("Agent 1 (Job Ingestor): Processing incoming jobs...")

    processed_jobs = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        processed_jobs.append({
            "title": job["title"],
            "company": job["company"],
            "location": job["location"],
            "skills": job.get("required_skills", "N/A"),
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

st.sidebar.subheader("🧠 Data Pipeline Control Tower")


st.sidebar.markdown(f"""
### Pipeline Status
**Source:** {state['active_source']}  
**Status:** `{state['status']}`
""")

if state["status"] == "healthy":
    st.sidebar.success("🟢 Live system active")
elif state["status"] == "fallback":
    st.sidebar.warning("🟡 Using fallback dataset")
else:
    st.sidebar.error("🔴 Using mock data")
    

st.sidebar.subheader("🔀 Switch Data Source (Demo Mode)")


# -----------------------------
# Section 1: Jobs
# -----------------------------
st.header("📊 Latest Jobs")

jobs = load_jobs(demo_mode)

st.subheader("📊 Latest Jobs")

for job in jobs:
    if not isinstance(job, dict):
        continue
    st.markdown(f"""
        <div style="
            padding:14px;
            border-radius:12px;
            border:1px solid #2d3748;
            margin-bottom:10px;
            background:linear-gradient(135deg,#0f172a,#1e293b);
            color:white;
        ">
            <h3 style="margin:0;">💼 {job['title']}</h3>
            <p style="margin:4px 0;">🏢 {job['company']} | 📍 {job.get('location','N/A')}</p>
            <p style="opacity:0.7; font-size:12px;">
                {job.get('category','')} • {job.get('employment_type','')}
            </p>
        </div>
        """, unsafe_allow_html=True)


st.header("📊 Job Analytics Dashboard")

# -------------------------
# 1. Category Distribution
# -------------------------
categories = {}
companies = {}

for job in jobs:
    cat = job.get("category", "Unknown")
    comp = job.get("company", "Unknown")

    categories[cat] = categories.get(cat, 0) + 1
    companies[comp] = companies.get(comp, 0) + 1

st.subheader("📂 Jobs by Category")

st.bar_chart(categories)

st.subheader("🏢 Top Hiring Companies")

st.bar_chart(companies)


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
    
    st.subheader("📈 Agent Score Distribution")

    scores = [job["score"] for job in scored_jobs]

    st.bar_chart(scores)

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

col1, col2, col3 = st.columns(3)

col1.metric("Pipeline Status", state["status"].upper())
col2.metric("Active Source", state["active_source"].split(" ")[0])
col3.metric("Mode", demo_mode)

st.write("---")
st.caption("Built for Band of Agents Hackathon | Multi-Agent Collaboration System")

st.metric("Jobs Processed", len(jobs))
st.metric("Top Match Score", "92%")
st.metric("Agents Active", "3")

st.info("📡 Note: In production, agents communicate through a shared Band Room using Band SDK/API. This demo simulates that communication layer for clarity.")