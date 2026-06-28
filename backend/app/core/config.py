from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

#pydantic settings based configuration management 
class Settings(BaseSettings):
    # Gemini
    google_api_key: str

    # LangSmith
    langchain_tracing_v2: str = "true"
    langchain_endpoint: str = "https://api.smith.langchain.com"
    langchain_api_key: str
    langchain_project: str = "neurograph-ai"

    # Tavily
    tavily_api_key: str

    # App
    app_env: str = "development"# in prod, on render dashboard => production
    frontend_url: str = "http://localhost:5173" # in prod, on render dashboard, set to deployed vercel url 

    # DB — empty 
    database_url: str = "" # for local ==> empty (sqlite) , for prod =>  on render dashboard ==> postgre (supabase) url 
    sqlite_db_path: str = "./data/neurograph.db"   # for local ==> path for neurograph.db  ==> stores  threads and user profile table 
    checkpoint_db_path: str = "./data/checkpoints.db" # for local  path or checkpoints.db ==> stores STM checkpoints 

    # RAG — vector store
    # local ==> empty (chromadb), for prod ==> set PINECONE_API_KEY on render dashboard
    chroma_path: str = "./data/chroma"          # local ChromaDB persistence directory
    pinecone_api_key: str = ""                  # prod: set on render dashboard; empty = use ChromaDB
    pinecone_index_name: str = "neurograph-rag" # prod: pre-created index name in Pinecone console

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


#factory functions to return cached instance  of Settings 
@lru_cache()
def get_settings() -> Settings:
    return Settings()