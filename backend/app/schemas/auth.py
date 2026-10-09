from pydantic import BaseModel, EmailStr, Field

#sign up /register  request schema 
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

#sign in /login request schema 
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

#response schema for both sign up  and log in 
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


