import asyncio
import logging
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from thenvoi import Agent
from thenvoi.adapters import LangGraphAdapter
from thenvoi.config import load_agent_config
import os
import sqlite3
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    load_dotenv()  # loads your LLM provider key, e.g. OPENAI_API_KEY
    
    active_jobs = await get_non_expired_staff_am_jobs_async()
    
    logger.info("Active staff.am jobs: %d", len(active_jobs))
    # inspect first job
    if active_jobs:
        logger.info("First job: %s", active_jobs[0].get("title"))
    
    




def get_non_expired_staff_am_jobs(db_path="data/jobs.db"):
    db_file = Path(db_path)
    if not db_file.exists():
        return []

    with sqlite3.connect(db_file) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT *
            FROM staff_am
            WHERE deadline IS NULL
               OR trim(deadline) = ''
               OR lower(trim(deadline)) = 'n/a'
               OR date(deadline) >= date('now')
            """
        ).fetchall()

    return [dict(r) for r in rows]

async def get_non_expired_staff_am_jobs_async(db_path="data/jobs.db"):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, get_non_expired_staff_am_jobs, db_path)


if __name__ == "__main__":
    asyncio.run(main())