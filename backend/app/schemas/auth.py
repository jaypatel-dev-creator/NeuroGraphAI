from pydantic import BaseModel, EmailStr, Field

#sign up request schema 
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

#sign in request schema 
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

