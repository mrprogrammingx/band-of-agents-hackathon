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
from firecrawl import FirecrawlApp
from pydantic import BaseModel

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from langgraph.checkpoint.memory import InMemorySaver

from band import Agent
from band.adapters import LangGraphAdapter
from band.config import load_agent_config


# =====================================================
# Logging
# =====================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

llm = None
firecrawl = None


# =====================================================
# Resume Models
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
# Prompts
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
# Web Search Tool
# =====================================================

@tool
def web_search(query: str) -> str:
    """
    Search the web using Firecrawl.
    """

    try:
        results = firecrawl.search(
            query=query,
            limit=5
        )

        return json.dumps(
            results,
            indent=2,
            ensure_ascii=False
        )

    except Exception as e:
        return f"Search failed: {str(e)}"


# =====================================================
# Scrape URL Tool
# =====================================================

@tool
def scrape_url(url: str) -> str:
    """
    Scrape webpage content.
    """

    try:

        result = firecrawl.scrape_url(
            url=url,
            formats=["markdown"]
        )

        if isinstance(result, dict):

            markdown = (
                result.get("markdown")
                or result.get("content")
                or ""
            )

            return markdown[:20000]

        return str(result)

    except Exception as e:

        return f"Scrape failed: {str(e)}"


# =====================================================
# Download File Tool
# =====================================================

@tool
def download_file(url: str) -> str:
    """
    Download a file from URL.
    Returns local path.
    """

    try:

        if "drive.google.com" in url:

            if "/file/d/" in url:

                file_id = (
                    url.split("/file/d/")[1]
                    .split("/")[0]
                )

                url = (
                    f"https://drive.google.com/uc?"
                    f"export=download&id={file_id}"
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
# PDF Extraction Tool
# =====================================================

@tool
def extract_pdf(url: str) -> str:
    """
    Download PDF and extract text.
    """

    try:

        pdf_path = download_file.func(url)

        if pdf_path.startswith("Download failed"):
            return pdf_path

        pdf = fitz.open(pdf_path)

        text = ""

        for page in pdf:
            text += page.get_text()

        pdf.close()

        return text[:50000]

    except Exception as e:

        return f"PDF extraction failed: {str(e)}"


# =====================================================
# Resume Parser
# =====================================================

@tool
def parse_resume(resume_text: str) -> str:
    """
    Parse resume text into structured JSON.
    """

    try:

        chain = extract_prompt | llm

        result = chain.invoke(
            {
                "resume": resume_text,
                "schema": ResumeProfile.model_json_schema()
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
# Resume Matcher
# =====================================================

@tool
def match_resume_to_job(
    resume_text: str,
    job_description: str
) -> str:
    """
    Match resume against a job.
    """

    try:

        profile = parse_resume.func(
            resume_text
        )

        chain = match_prompt | llm

        result = chain.invoke(
            {
                "profile": profile,
                "job": job_description
            }
        )

        return result.content

    except Exception as e:

        return f"Job matching failed: {str(e)}"


# =====================================================
# Main
# =====================================================

async def main():

    global llm
    global firecrawl

    load_dotenv()

    firecrawl = FirecrawlApp(
        api_key=os.getenv(
            "FIRECRAWL_API_KEY"
        )
    )

    agent_id, api_key = load_agent_config(
        "recruitment-research-agent"
    ) 
    # recruitment-research-agent

    llm = ChatOpenAI(
        model="deepseek-ai/DeepSeek-V4-Pro",
        temperature=0.2,
        api_key=os.getenv(
            "FEATHERLESS_API_KEY"
        ),
        base_url="https://api.featherless.ai/v1"
    )

    adapter = LangGraphAdapter(
        llm=llm,
        checkpointer=InMemorySaver(),
        additional_tools=[
            web_search,
            scrape_url,
            download_file,
            extract_pdf,
            parse_resume,
            match_resume_to_job
        ],
        custom_section="""
You are a Recruitment Research Agent.

Capabilities:

1. Parse resumes pasted into chat.
2. Match resumes against jobs.
3. Search the web.
4. Scrape webpages.
5. Download documents.
6. Read PDFs.
7. Read public Google Drive PDFs.
8. Research companies and candidates.

Instructions:

- Use web_search for current information.
- Use scrape_url for webpage analysis.
- Use extract_pdf for PDF links.
- Use parse_resume for CV analysis.
- Use match_resume_to_job when both CV and job description exist.
- Always use tools before answering.
"""
    )

    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        ws_url=os.getenv("BAND_WS_URL"),
        rest_url=os.getenv("BAND_REST_URL"),
    )

    logger.info(
        "Recruitment Research Agent Running..."
    )

    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())