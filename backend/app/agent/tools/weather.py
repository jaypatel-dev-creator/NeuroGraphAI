import httpx
from langchain_core.tools import tool

from app.core.logging import get_logger

logger = get_logger(__name__)


@tool
async def weather(city: str) -> str:
    """
    Get current weather for a city.
    Input must be a city name string.
    Example: 'Mumbai', 'London', 'New York'
    """
    try:
        url = f"https://wttr.in/{city}?format=3"#format =3 returns weather in single line string formt 
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            return response.text.strip()
    except Exception as e:
        logger.error(f"weather failed for '{city}': {str(e)}", exc_info=True)
        return "Weather lookup failed. The city name may be invalid or the weather service may be unavailable."