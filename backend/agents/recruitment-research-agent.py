import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import List, Optional

import fitz
import requests
from dotenv import load_dotenv
from duckduckgo_search import DDGS

from pydantic import BaseModel

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


# =====================================================
# RESUME MODELS
# =====================================================

class Experience(BaseModel):
    title: str
    company: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None


class Project(BaseModel):
    name: str
    description: Optional[str] = None
    technologies: List[str]


class Education(BaseModel):
    degree: str
    university: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ResumeProfile(BaseModel):
    personal_information: dict
    skills: List[str]
    roles: List[str]
    experience: List[Experience]
    projects: List[Project]
    education: List[Education]
    certifications: List[str]
    publications: List[str]


# =====================================================
# PROMPTS
# =====================================================

extract_prompt = ChatPromptTemplate.from_template(
    """
You are an expert resume parser.

Extract ALL information from the resume.

Return ONLY valid JSON.

Schema:

{schema}

Resume:

{resume}
"""
)

match_prompt = ChatPromptTemplate.from_template(
    """
You are a senior technical recruiter.

Candidate Profile:

{profile}

Job Description:

{job}

Calculate:

1. Match Score (0-100)
2. Missing Skills
3. Matching Skills
4. Experience Relevance
5. Final Recommendation

Return JSON only.
"""
)


# =====================================================
# SEARCH TOOL
# =====================================================

@tool
def web_search(query: str) -> str:
    """
    Search the web and return only concise results.
    Prevents context overflow.
    """

    try:

        results = []

        with DDGS() as ddgs:

            for r in ddgs.text(
                query,
                region="wt-wt",
                max_results=3
            ):

                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": (
                            r.get("body", "")[:300]
                        )
                    }
                )

        return json.dumps(
            results,
            ensure_ascii=False,
            indent=2
        )

    except Exception as e:

        return f"Search failed: {str(e)}"


# =====================================================
# SIMPLE WEBPAGE READER
# =====================================================

@tool
def read_webpage(url: str) -> str:
    """
    Read webpage content with strict limits.
    """

    try:

        response = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent":
                "Mozilla/5.0"
            }
        )

        text = response.text

        text = text[:5000]

        return text

    except Exception as e:

        return f"Failed to read webpage: {str(e)}"


# =====================================================
# DOWNLOAD FILE
# =====================================================

@tool
def download_file(url: str) -> str:
    """
    Download a file and return local path.
    """

    try:

        if "drive.google.com" in url:

            if "/file/d/" in url:

                file_id = (
                    url.split("/file/d/")[1]
                    .split("/")[0]
                )

                url = (
                    "https://drive.google.com/uc"
                    f"?export=download&id={file_id}"
                )

        response = requests.get(
            url,
            timeout=60,
            allow_redirects=True
        )

        response.raise_for_status()

        suffix = Path(url).suffix

        if not suffix:
            suffix = ".pdf"

        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        )

        temp_file.write(response.content)
        temp_file.close()

        return temp_file.name

    except Exception as e:

        return f"Download failed: {str(e)}"


# =====================================================
# PDF EXTRACTION
# =====================================================

@tool
def extract_pdf(url: str) -> str:
    """
    Extract text from PDF URL.
    """

    try:

        pdf_path = download_file.func(url)

        if pdf_path.startswith("Download failed"):
            return pdf_path

        doc = fitz.open(pdf_path)

        text = ""

        for page in doc:
            text += page.get_text()

        doc.close()

        # Prevent context overflow
        return text[:15000]

    except Exception as e:

        return f"PDF extraction failed: {str(e)}"


# =====================================================
# RESUME PARSER
# =====================================================

@tool
def parse_resume(resume_text: str) -> str:
    """
    Parse resume text.
    """

    try:

        resume_text = resume_text[:15000]

        chain = extract_prompt | llm

        result = chain.invoke(
            {
                "resume": resume_text,
                "schema":
                ResumeProfile.model_json_schema()
            }
        )

        content = result.content

        if "```json" in content:

            content = (
                content.split("```json")[1]
                .split("```")[0]
            )

        return content

    except Exception as e:

        return f"Resume parsing failed: {str(e)}"


# =====================================================
# JOB MATCHER
# =====================================================

@tool
def match_resume_to_job(
    resume_text: str,
    job_description: str
) -> str:
    """
    match_resume_to_job.
    """
    try:

        profile = parse_resume.func(
            resume_text[:15000]
        )

        chain = match_prompt | llm

        result = chain.invoke(
            {
                "profile": profile,
                "job": job_description[:5000]
            }
        )

        return result.content

    except Exception as e:

        return f"Job matching failed: {str(e)}"


# =====================================================
# MAIN
# =====================================================

async def main():

    global llm

    load_dotenv()

    agent_id, api_key = load_agent_config(
        "recruitment-research-agent"
    )
    agent_id = os.getenv("RECRUITMENT_RESEARCH_AGENT_ID")
    api_key = os.getenv("RECRUITMENT_RESEARCH_AGENT_API_KEY")
    
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
            # web_search,
            read_webpage,
            download_file,
            extract_pdf,
            parse_resume,
            match_resume_to_job
        ],
        custom_section="""
You are a Recruitment Research Agent.

Capabilities:
- Resume analysis
- Job matching
- Job search
- Company research
- PDF reading
- Web search

Important rules:

1. Never search more than once unless needed.
2. Never read more than one webpage.
3. Keep answers concise.
4. Use web_search for job searches.
5. Use extract_pdf only when a PDF URL is provided.
6. Avoid large outputs.
7. If enough information is available, answer without using tools.
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
        "Recruitment Research Agent Running..."
    )

    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())