from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):#base class from which all tables will be inheriting 
    pass



#creating sessions based on environment 
if settings.database_url: # production mode==> postgres(supabase) 
    engine = create_async_engine(
        settings.database_url,
        echo=False, # to avoig sqlite from printing sql queries it executes in terminal 
        pool_pre_ping=True,#Before using a connection from the pool, ping the DB to check if it's still alive. Prevents stale connection errors after inactivity.
    )
else:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{settings.sqlite_db_path}", #location of sqlite 
        echo=False,# to avoig sqlite from printing sql queries it executes in terminal 
        connect_args={"check_same_thread": False}, # by def , sqlite allows only cpu thread that created the connection to use it, since faltapi uses multiple threads, so check_same_thread=False, sqllite now allows any thread 
    )

#creating session maker
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)