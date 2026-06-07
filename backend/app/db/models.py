from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)

#Thread model 
class Thread(Base):
    __tablename__ = "threads"#threads will be name of table mapped to Thread model  in actual database 

    id: Mapped[str] = mapped_column(String, primary_key=True) #uuid will be generated in routes and passed 
    title: Mapped[str] = mapped_column(String, default="New Chat")
    is_titled: Mapped[bool] = mapped_column(Boolean, default=False)#whether thread has title or not
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow #timestamp for when thread was created 
    )
    updated_at: Mapped[datetime] = mapped_column(#when the column was updated either by autogeneration (first chat) or user manual update
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

#UserProfile Model 
class UserProfile(Base):
    __tablename__ = "user_profile"#user_profile will be the name of table mapped to UserProfile model in actual database

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )