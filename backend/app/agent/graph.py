"""LangChain agent construction and execution."""

import boto3
from botocore.config import Config
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_aws import ChatBedrockConverse
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory

from app.agent.memory import get_session_history
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import create_tools
from app.config import settings
from app.rag.retriever import FormattedRetriever


def create_agent(retriever: FormattedRetriever) -> RunnableWithMessageHistory:
    """
    Create the conversational agent with memory.

    Args:
        retriever: Initialized FormattedRetriever for RAG

    Returns:
        Agent executor wrapped with message history
    """
    # Configure Bedrock client with retry + timeout
    bedrock_config = Config(
        read_timeout=30,  # 30s timeout prevents hanging
        retries={
            "max_attempts": 3,  # Retry up to 3 times
            "mode": "adaptive",  # Exponential backoff with jitter
        },
    )

    llm = ChatBedrockConverse(
        model=settings.bedrock_model_id,
        region_name=settings.aws_region,
        temperature=0,
        client=boto3.client("bedrock-runtime", config=bedrock_config),
    )

    tools = create_tools(retriever)

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)

    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
    )

    agent_with_memory = RunnableWithMessageHistory(
        agent_executor,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

    return agent_with_memory
