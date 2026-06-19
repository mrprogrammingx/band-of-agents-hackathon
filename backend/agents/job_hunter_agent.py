import asyncio
import json
import logging
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

from langgraph.checkpoint.memory import InMemorySaver

from band import Agent
from band.adapters import LangGraphAdapter
from band.config import load_agent_config


# =====================================================
# LOGGING
# =====================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

llm = None

DB_PATH = "data/jobs.db"


# =====================================================
# DATABASE
# =====================================================

def get_non_expired_staff_am_jobs(
    db_path=DB_PATH
):
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


async def get_non_expired_staff_am_jobs_async(
    db_path=DB_PATH
):
    loop = asyncio.get_running_loop()

    return await loop.run_in_executor(
        None,
        get_non_expired_staff_am_jobs,
        db_path
    )


# =====================================================
# SEARCH JOBS BY SKILLS
# =====================================================

@tool
def search_jobs_by_skills(
    skills: str
) -> str:
    """
    Search jobs using a list of skills.
    Example:
    Python, Computer Vision, PyTorch
    """

    jobs = get_non_expired_staff_am_jobs()

    skill_list = [
        s.strip().lower()
        for s in skills.split(",")
    ]

    scored_jobs = []

    for job in jobs:

        searchable_text = json.dumps(
            job,
            ensure_ascii=False
        ).lower()

        score = sum(
            1
            for skill in skill_list
            if skill in searchable_text
        )

        if score > 0:

            scored_jobs.append(
                {
                    "score": score,
                    "title": job.get("title"),
                    "company": job.get("company"),
                    "deadline": job.get("deadline"),
                    "url": job.get("job_url"),
                    "description": (
                        str(
                            job.get(
                                "job_description",
                                ""
                            )
                        )[:500]
                    )
                }
            )

    scored_jobs.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return json.dumps(
        scored_jobs[:10],
        indent=2,
        ensure_ascii=False
    )


# =====================================================
# MATCH JOBS TO CV
# =====================================================

match_prompt = ChatPromptTemplate.from_template(
    """
You are a senior recruiter.

Candidate Profile:

{profile}

Jobs:

{jobs}

Select the TOP 10 jobs.

For each job provide:

- Job Title
- Company
- Match Score (0-100)
- Why It Matches

Return JSON.
"""
)


@tool
def match_jobs_to_cv(
    candidate_profile: str
) -> str:
    """
    Match jobs against an extracted CV profile.
    """

    jobs = get_non_expired_staff_am_jobs()

    reduced_jobs = []

    for job in jobs[:100]:

        reduced_jobs.append(
            {
                "title": job.get("title"),
                "company": job.get("company"),
                "description": str(
                    job.get(
                        "job_description",
                        ""
                    )
                )[:1000],
                "url": job.get("job_url")
            }
        )

    chain = match_prompt | llm

    result = chain.invoke(
        {
            "profile": candidate_profile[:10000],
            "jobs": json.dumps(
                reduced_jobs,
                ensure_ascii=False
            )
        }
    )

    return result.content


# =====================================================
# JOB RECOMMENDATIONS
# =====================================================

@tool
def get_latest_jobs(
    limit: int = 10
) -> str:
    """
    Return latest active jobs.
    """

    jobs = get_non_expired_staff_am_jobs()

    latest = []

    for job in jobs[:limit]:

        latest.append(
            {
                "title": job.get("title"),
                "company": job.get("company"),
                "deadline": job.get("deadline"),
                "url": job.get("job_url")
            }
        )

    return json.dumps(
        latest,
        indent=2,
        ensure_ascii=False
    )


# =====================================================
# MAIN
# =====================================================

async def main():

    global llm

    load_dotenv()

    agent_id, api_key = load_agent_config(
        "job-hunter"
    )
    
    agent_id = os.getenv("JOB_HUNTER_AGENT_ID")
    api_key = os.getenv("JOB_HUNTER_AGENT_API_KEY")

    # llm = ChatOpenAI(
    #     model="deepseek-ai/DeepSeek-V4-Pro",
    #     temperature=0.2,
    #     api_key=os.getenv(
    #         "FEATHERLESS_API_KEY"
    #     ),
    #     base_url="https://api.featherless.ai/v1"
    # )
    llm = ChatOpenAI(
        model="gpt-4o-mini-2024-07-18",
        temperature=0.2,
        api_key=os.getenv(
            "ML_API_KEY"
        ),
        base_url="https://api.aimlapi.com/v1/"
    )
    adapter = LangGraphAdapter(
        llm=llm,
        checkpointer=InMemorySaver(),
        additional_tools=[
            search_jobs_by_skills,
            match_jobs_to_cv,
            get_latest_jobs
        ],
        custom_section="""
You are Job Hunter.

Capabilities:

1. Search jobs by skills.
2. Match jobs to CV profiles.
3. Recommend opportunities.
4. Rank jobs by relevance.

Instructions:

- If user provides skills:
  use search_jobs_by_skills.

- If user provides a CV profile:
  use match_jobs_to_cv.

- If user asks for recent jobs:
  use get_latest_jobs.

Always return the most relevant jobs first.
Keep responses concise.
"""
    )

    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        ws_url=os.getenv("BAND_WS_URL"),
        rest_url=os.getenv("BAND_REST_URL")
    )

    logger.info(
        "Job Hunter Agent Running..."
    )

    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())