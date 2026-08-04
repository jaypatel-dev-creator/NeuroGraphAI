import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import User
from app.core.security import hash_password, verify_password, create_access_token
from app.core.exceptions import UnauthorizedException, UserAlreadyExistsException
from app.core.logging import get_logger
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse

logger = get_logger(__name__)

#sign in 
async def register_user(db: AsyncSession, payload: RegisterRequest) -> TokenResponse:
    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise UserAlreadyExistsException(payload.email)

    user = User(
        id=str(uuid.uuid4()),#generating id 
        email=payload.email,
        hashed_password=hash_password(payload.password),#hashing the password 
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    logger.info(f"New user registered: {user.id}")
    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token)

#log in 
async def login_user(db: AsyncSession, payload: LoginRequest) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise UnauthorizedException("Invalid email or password.")

    logger.info(f"User authenticated: {user.id}")
    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token)