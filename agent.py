from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware, TodoListMiddleware

from tools.say import say
from tools.search import web_search, crawl_url
from tools.graphrag import store_memory, retrieve_memory
from tools.modify_system_prompt import modify_system_prompt, read_system_prompt
from tools.request_user_input import request_user_input
from tools.shell import execute_shell
from tools.filesystem import (
    create_directory, remove_directory, list_directory,
    create_file, view_file, remove_file, edit_file, append_to_file
)
from tools.wolfram import wolfram_query

from config import MODEL_NAME, OPENAI_API_KEY, OPENAI_BASE_URL, SYSTEM_PROMPT_PATH

def load_system_prompt() -> str:
    """Load the system prompt from file."""
    try:
        with open(SYSTEM_PROMPT_PATH, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return "You are Bob, an AI assistant."

def create_bob_agent():
    """Create the LangChain agent with all tools and middleware."""
    
    llm = ChatOpenAI(
        model=MODEL_NAME,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        use_responses_api=False,
        streaming=True,
    )
    
    summarization_llm = ChatOpenAI(
        model=MODEL_NAME,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        use_responses_api=False,
    )
    
    tools = [
        say,
        web_search,
        crawl_url,
        wolfram_query,
        store_memory,
        retrieve_memory,
        modify_system_prompt,
        read_system_prompt,
        request_user_input,
        execute_shell,
        create_directory,
        remove_directory,
        list_directory,
        create_file,
        view_file,
        remove_file,
        edit_file,
        append_to_file,
    ]
    
    agent = create_agent(
        model=llm,
        tools=tools,
        middleware=[
            SummarizationMiddleware(
                model=summarization_llm,
                trigger=("tokens", 4000),
                keep=("messages", 20),
            ),
            TodoListMiddleware(),
        ],
    )
    
    return agent
