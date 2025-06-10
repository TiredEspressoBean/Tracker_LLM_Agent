"""This module provides example tools for web scraping and search functionality.

It includes a basic Tavily search function (as an example)

These tools are intended as free examples to get started. For production use,
consider implementing more robust and specialized tools tailored to your needs.
"""

from typing import Any, Callable, List, Optional, cast, Annotated

from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_ollama import ChatOllama
from langchain_tavily import TavilySearch  # type: ignore[import-not-found]
from langchain_experimental.utilities import PythonREPL

from react_agent.configuration import Configuration

from langchain.tools import tool


async def search(query: str) -> Optional[dict[str, Any]]:
    """Search for general web results.

    This function performs a search using the Tavily search engine, which is designed
    to provide comprehensive, accurate, and trusted results. It's particularly useful
    for answering questions about current events.
    """
    configuration = Configuration.from_context()
    wrapped = TavilySearch(max_results=configuration.max_search_results)
    return cast(dict[str, Any], await wrapped.ainvoke({"query": query}))


@tool
def add_numbers(number_1: Annotated[int, "The first number"], number_2: Annotated[int, "The second number"]) -> int:
    """A tool that adds two numbers together."""
    return number_1 + number_2


@tool
def multiply_numbers(number_1: Annotated[int, "The first number"],
                     number_2: Annotated[int, "The second number"]) -> int:
    """A tool that multiplies two numbers together."""
    return number_1 * number_2


# 1. Init database
db = SQLDatabase.from_uri("postgresql+psycopg2://readonly_user:readonly_password@localhost:5432/tracker_AMBAC")

# 2. Init LLM
llm = ChatOllama(model="qwen3:latest")

# 3. Build SQL tools from toolkit
toolkit = SQLDatabaseToolkit(llm=llm, db=db)
sql_tools = toolkit.get_tools()

python_repl = PythonREPL()

def repl_tool(query:str) -> str:
    """ Sanitizes and executes a python query. If you want to receive information in return use print()"""
    sanitized_query = python_repl.sanitize_input(query)
    try:
        result = python_repl.run(sanitized_query)
    except BaseException as e:
        return f"Python Repl Failed, Error: {e}"
    return f"Python code: {sanitized_query}\n\n StdOut: {result}"


TOOLS: List[Callable[..., Any]] = [search, repl_tool] + sql_tools
