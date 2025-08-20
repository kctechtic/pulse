from fastapi import APIRouter, Depends, HTTPException, status
from models import UserCreate, UserLogin, UserResponse, Token
from database import get_supabase, get_password_hash
from auth import create_access_token, authenticate_user, get_current_user
from datetime import timedelta
from config import settings

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate):
    supabase = get_supabase()
    
    # Check if user already exists
    try:
        existing_user = supabase.table("users").select("*").eq("email", user.email).execute()
        if existing_user.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error"
        )
    
    # Hash password and create user
    hashed_password = get_password_hash(user.password)
    
    try:
        new_user = {
            "email": user.email,
            "password": hashed_password,
            "first_name": user.first_name,
            "last_name": user.last_name
        }
        
        response = supabase.table("users").insert(new_user).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
        
        created_user = response.data[0]
        return UserResponse(
            id=created_user["id"],
            email=created_user["email"],
            first_name=created_user["first_name"],
            last_name=created_user["last_name"],
            created_at=created_user["created_at"],
            updated_at=created_user["updated_at"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )

@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin):
    user = authenticate_user(user_credentials.email, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.jwt_expire_minutes)
    access_token = create_access_token(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        first_name=current_user["first_name"],
        last_name=current_user["last_name"],
        created_at=current_user["created_at"],
        updated_at=current_user["updated_at"]
    )

@router.get("/verify")
async def verify_token_validity(current_user: dict = Depends(get_current_user)):
    return {"valid": True, "user_id": current_user["id"]}