import asyncio
import logging
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from thenvoi import Agent
from thenvoi.adapters import LangGraphAdapter
from thenvoi.config import load_agent_config
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    load_dotenv()  # loads your LLM provider key, e.g. OPENAI_API_KEY
    
    api_key = os.getenv("FEATHERLESS_API_KEY")  # replace with your actual API key or ensure it's set in your .env file

    llm = ChatOpenAI(
        model="deepseek-ai/DeepSeek-V4-Pro",
        temperature=0.2,
        api_key=api_key,
        base_url="https://api.featherless.ai/v1"
    )
    
    adapter = LangGraphAdapter(
        llm=llm,
        checkpointer=InMemorySaver(),
        custom_section="You are a quick first-pass drafter. Take any brief, produce a tight first draft ready for critique.",
    )

    agent_id, api_key = load_agent_config("drafter")
    print(f"Loaded agent config: agent_id={agent_id[:4]}, api_key={api_key[:4]}...")
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)

    logger.info("Agent is running! Press Ctrl+C to stop.")
    await agent.run()  # opens a persistent WebSocket and listens forever

if __name__ == "__main__":
    asyncio.run(main())