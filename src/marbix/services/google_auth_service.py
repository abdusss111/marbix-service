import os
from dotenv import load_dotenv
load_dotenv()

import httpx
import jwt
from sqlalchemy.orm import Session
from fastapi import HTTPException
from marbix.models.user import User

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
JWT_SECRET = os.getenv("AUTH_SECRET", "secret-key")


async def exchange_code_for_token(code: str) -> str:
    """
    Обменивает authorization code на access token
    Используется для стандартного OAuth flow на фронте
    """
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code"
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        print(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI)

    if token_resp.status_code != 200:
        print(GOOGLE_REDIRECT_URI)
        raise HTTPException(
            status_code=400, 
            detail=f"Token exchange failed: {token_resp.text}"
        )

    token_data = token_resp.json()
    return token_data["access_token"]


async def validate_google_access_token(access_token: str) -> dict:
    """
    Валидирует Google access token и возвращает информацию о токене
    Проверяет audience для защиты от token substitution атак
    """
    async with httpx.AsyncClient() as client:
        token_info_resp = await client.get(
            f"https://www.googleapis.com/oauth2/v1/tokeninfo?access_token={access_token}"
        )
    
    if token_info_resp.status_code != 200:
        raise HTTPException(
            status_code=401, 
            detail=f"Token validation failed: {token_info_resp.text}"
        )
    
    token_info = token_info_resp.json()
    
        # Критически важно: проверяем что токен выдан для нашего приложения
    is_extension = access_token.startswith("ya29.")  # признак «расширенного» токена

    # выбираем, с каким CLIENT_ID сравнивать
    expected_audience = (
        GOOGLE_CLIENT_ID_EXTENSION if is_extension
        else GOOGLE_CLIENT_ID
    )

    if token_info.get("audience") != expected_audience:
        raise HTTPException(
            status_code=401,
            detail="Token audience mismatch - token not issued for this application"
        )
    # дальше – проверка срока жизни и т.п.


    # Проверяем что токен не истек
    if token_info.get("expires_in", 0) <= 0:
        raise HTTPException(
            status_code=401, 
            detail="Token has expired"
        )
    
    return token_info


async def get_google_user_info(access_token: str) -> dict:
    """
    Получает информацию о пользователе из Google API
    Сначала валидирует токен для безопасности
    """    
    # Теперь безопасно получаем user info
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )

    if user_resp.status_code != 200:
        raise HTTPException(
            status_code=400, 
            detail=f"User info fetch failed: {user_resp.text}"
        )

    return user_resp.json()


async def validate_and_get_user_info(access_token: str) -> dict:
    """
    Комбинированная функция: валидация токена + получение user info
    Для Chrome Identity API использования
    """
    # Валидируем токен

    token_info = await validate_google_access_token(access_token)
    
    # Получаем user info
    user_info = await get_google_user_info(access_token)
    
    # Возвращаем объединенную информацию
    return {
        **user_info,
        "token_info": {
            "audience": token_info.get("audience"),
            "scope": token_info.get("scope"),
            "expires_in": token_info.get("expires_in")
        }
    }


def find_or_create_user(user_info: dict, db: Session) -> User:
    """
    Находит существующего пользователя или создает нового
    """
    user = db.query(User).filter(User.id == user_info["id"]).first()
    if not user:
        user = User(
            id=user_info["id"],
            email=user_info["email"],
            name=user_info.get("name", "")
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def generate_jwt(user_info: dict) -> str:
    """
    Генерирует кастомный JWT для использования в API
    """
    payload = {
        "sub": user_info["id"],
        "email": user_info["email"],
        "name": user_info.get("name", ""),
    }
    
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


async def authenticate_with_google_token(code: str, db: Session) -> tuple[User, str]:
    """
    Полный flow аутентификации для Chrome Identity:
    1. Валидирует Google токен
    2. Получает user info  
    3. Создает/находит пользователя в БД
    4. Генерирует кастомный JWT
    
    Returns: (User object, JWT token)
    """
    try:
        # Получаем и валидируем user info
        access_token = await exchange_code_for_token(code)
        user_info = await get_google_user_info(access_token)
        
        # Создаем/находим пользователя
        user = find_or_create_user(user_info, db)
        
        # Генерируем наш JWT
        jwt_token = generate_jwt(user_info)
        
        return user, jwt_token
        
    except HTTPException:
        # Пробрасываем HTTP ошибки как есть
        raise
    except Exception as e:
        # Ловим любые другие ошибки
        raise HTTPException(
            status_code=500, 
            detail=f"Authentication failed: {str(e)}"
        )