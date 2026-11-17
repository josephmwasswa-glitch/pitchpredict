
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

users_db = {}

class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

@router.post("/register")
def register(user: UserRegister):
    if user.email in users_db:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    if len(user.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must have at least 8 characters"
        )

    users_db[user.email] = {
        "username": user.username,
        "email": user.email,
        "password": pwd_context.hash(user.password)
    }

    return {"message": "Registration successful"}

@router.post("/login")
def login(user: UserLogin):
    account = users_db.get(user.email)

    if not account or not pwd_context.verify(
        user.password,
        account["password"]
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    return {"message": "Login successful"}
