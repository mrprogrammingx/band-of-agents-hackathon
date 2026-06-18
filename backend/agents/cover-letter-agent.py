import asyncio
import logging
import os

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


# =====================================================
# PROMPTS
# =====================================================

cover_letter_prompt = ChatPromptTemplate.from_template(
    """
You are a professional career coach and expert cover letter writer.

Write a tailored cover letter using the candidate information
and job description provided below.

Requirements:
- Professional tone
- Personalized and specific
- Highlight relevant achievements
- Highlight matching skills
- Explain motivation for applying
- Length: 300-500 words
- Avoid generic phrases
- Use modern hiring best practices

Candidate Information:

{candidate_info}

Job Description:

{job_description}

Return ONLY the cover letter.
"""
)

recruiter_message_prompt = ChatPromptTemplate.from_template(
    """
You are a career coach.

Create a short recruiter outreach message.

Requirements:
- 50-120 words
- Professional and concise
- Mention strongest qualifications
- Express interest in the role
- Include a call to action

Candidate Information:

{candidate_info}

Job Description:

{job_description}

Return ONLY the recruiter message.
"""
)

application_package_prompt = ChatPromptTemplate.from_template(
    """
You are a professional job application assistant.

Create:

1. Professional Cover Letter
2. Short Recruiter Message

Candidate Information:

{candidate_info}

Job Description:

{job_description}

Format:

# Cover Letter

...

# Recruiter Message

...
"""
)


# =====================================================
# COVER LETTER TOOL
# =====================================================

@tool
def generate_cover_letter(
    candidate_info: str,
    job_description: str
) -> str:
    """
    Generate a tailored cover letter using candidate information and job description.
    """

    chain = cover_letter_prompt | llm

    result = chain.invoke(
        {
            "candidate_info": candidate_info[:15000],
            "job_description": job_description[:8000]
        }
    )

    return result.content


# =====================================================
# RECRUITER MESSAGE TOOL
# =====================================================

@tool
def generate_recruiter_message(
    candidate_info: str,
    job_description: str
) -> str:
    """
    Generate a recruiter outreach message using candidate information and job description.
    """

    chain = recruiter_message_prompt | llm

    result = chain.invoke(
        {
            "candidate_info": candidate_info[:15000],
            "job_description": job_description[:8000]
        }
    )

    return result.content


# =====================================================
# FULL APPLICATION PACKAGE
# =====================================================

@tool
def generate_application_package(
    candidate_info: str,
    job_description: str
) -> str:
    """
    Generate both a cover letter and recruiter message.
    """

    chain = application_package_prompt | llm

    result = chain.invoke(
        {
            "candidate_info": candidate_info[:15000],
            "job_description": job_description[:8000]
        }
    )

    return result.content


# =====================================================
# MAIN
# =====================================================

async def main():

    global llm

    load_dotenv()

    agent_id, api_key = load_agent_config(
        "cover-letter-writer"
    )

    # llm = ChatOpenAI(
    #     model="deepseek-ai/DeepSeek-V4-Pro",
    #     temperature=0.4,
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
            generate_cover_letter,
            generate_recruiter_message,
            generate_application_package
        ],
        custom_section="""
You are a Cover Letter Writer Agent.

Capabilities:
1. Create tailored cover letters.
2. Create recruiter outreach messages.
3. Create complete application packages.
4. Customize content for specific jobs.
5. Highlight candidate strengths.

Instructions:

- If the user asks only for a cover letter:
  use generate_cover_letter.

- If the user asks only for a recruiter message:
  use generate_recruiter_message.

- If the user asks for both:
  use generate_application_package.

- Use the candidate information and job description
  provided by the user.

- Produce professional, ATS-friendly content.

- Keep outputs concise, impactful, and personalized.
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
        "Cover Letter Writer Agent Running..."
    )

    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())