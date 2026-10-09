from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Gemini
    google_api_key: str

    # LangSmith
   
    langsmith_tracing: str = "false"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_api_key: str = ""
    langsmith_project: str = "neurograph-ai"

    # Tavily
    tavily_api_key: str

    # App
    app_env: str = "development"        # prod: set to "production" on Render dashboard
    frontend_url: str = "http://localhost:5173"  # prod: set to deployed Vercel URL on Render dashboard

    # DB
    database_url: str = ""              # local: empty → SQLite; prod: Supabase Postgres URL on Render dashboard
    sqlite_db_path: str = "./data/neurograph.db"
    checkpoint_db_path: str = "./data/checkpoints.db"

    # RAG — vector store
    chroma_path: str = "./data/chroma"
    pinecone_api_key: str = ""          # prod: set on Render dashboard
    pinecone_index_name: str = "neurograph-rag"

    # Auth — JWT
    jwt_secret_key: str                 # generate with: openssl rand -hex 32
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7   # 7 days 

    model_config = SettingsConfigDict(
        env_file=".env", #read configs from .env file 
        env_file_encoding="utf-8", 
        case_sensitive=False, # make configurations key case insensitive 
        extra="ignore", #ignore any extra conifg 
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
