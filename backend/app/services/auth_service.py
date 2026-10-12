import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import User
from app.core.security import hash_password, verify_password, create_access_token
from app.core.exceptions import UnauthorizedException, UserAlreadyExistsException
from app.core.logging import get_logger

logger = get_logger(__name__)

#create account /sign up
async def register_user(db: AsyncSession, email: str, password: str) -> str:
    """Create a new user and return a JWT access token."""
    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise UserAlreadyExistsException(email)

    user = User(
        id=str(uuid.uuid4()),#generating id 
        email=email,
        hashed_password=hash_password(password),#hashing the password while storing using bcrypt 
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    logger.info(f"New user registered: {user.id}")
    return create_access_token(subject=user.id)

#log in /sign in 
async def login_user(db: AsyncSession, email: str, password: str) -> str:
    """Verify credentials and return a JWT access token."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        raise UnauthorizedException("Invalid email or password.")

    logger.info(f"User authenticated: {user.id}")
    return create_access_token(subject=user.id)