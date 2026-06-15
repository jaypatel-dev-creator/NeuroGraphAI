from langchain_tavily import TavilySearch
from app.core.config import get_settings


def get_search_tool() -> TavilySearch:
    settings = get_settings()
    return TavilySearch(
        max_results=3,#return top 3 search results 
        tavily_api_key=settings.tavily_api_key,

        description=( 
            "Search the web for current information, news, recent events, "
            "or anything that requires up-to-date knowledge."
        ),        #Gemini reads description to decide when to use search — same as docstring in other tools. Explicitly mentions "current information" and "recent events" — so Gemini uses search when it knows its training data might be outdated.

    )