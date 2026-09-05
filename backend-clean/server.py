#!/usr/bin/env python3
"""
ShopVerse FBO E-Commerce Backend
Production-Ready Single-File FastAPI Application
Version: 3.1.0 - Hardened production checkout plus Gemini customer assistant
"""

# ============================================================================
# IMPORTS
# ============================================================================
import base64
import json
import os
import re
import io
import uuid
import time
import hashlib
import asyncio
import logging
import smtplib
import secrets
import random
from typing import Dict, List, Optional, Any, Union, Literal, Tuple
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps
from contextlib import asynccontextmanager
from pathlib import Path

import bcrypt
import jwt
import httpx
import magic
from PIL import Image
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    validator,
    ValidationError,
    conint,
    constr,
    AnyHttpUrl
)
from pydantic.fields import FieldInfo
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from bson import ObjectId
from fastapi import (
    FastAPI,
    Request,
    Response,
    Depends,
    HTTPException,
    status as http_status,
    UploadFile,
    File,
    Form,
    Cookie,
    Header,
    Body,
    Query,
    Path as PathParam
)
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader

try:
    from google import genai
except ImportError:
    genai = None

# ============================================================================
# ENVIRONMENT & CONFIGURATION
# ============================================================================

# Load environment variables
load_dotenv()

class Settings:
    """Application settings from environment variables."""

    # Application
    APP_NAME: str = os.getenv("APP_NAME", "ShopVerse FBO")
    APP_VERSION: str = "3.1.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # API
    API_PREFIX: str = os.getenv("API_PREFIX", "/api")
    API_VERSION: str = "v1"
    RENDER_URL: str = os.getenv("RENDER_URL", "https://shopverse-1-la3b.onrender.com")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "https://shopbyfbo.vercel.app")

    # Database
    MONGO_URL: str = os.getenv("MONGO_URL", "")
    DB_NAME: str = os.getenv("DB_NAME", "shopverse")
    MONGO_MAX_POOL_SIZE: int = int(os.getenv("MONGO_MAX_POOL_SIZE", "100"))
    MONGO_MIN_POOL_SIZE: int = int(os.getenv("MONGO_MIN_POOL_SIZE", "10"))

    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    JWT_ISSUER: str = os.getenv("JWT_ISSUER", "shopverse-fbo")
    JWT_AUDIENCE: str = os.getenv("JWT_AUDIENCE", "shopverse-frontend")

    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")

    # Admin
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")

    # Email
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASS: str = os.getenv("SMTP_PASS", "")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "ShopVerse FBO")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "")

    # Cloudinary
    CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET", "")

    # Checkout
    SHIPPING_THRESHOLD: float = float(os.getenv("SHIPPING_THRESHOLD", "499"))
    SHIPPING_FEE: float = float(os.getenv("SHIPPING_FEE", "49"))
    MAX_CART_QUANTITY: int = int(os.getenv("MAX_CART_QUANTITY", "20"))

    # Gemini chatbot
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    # Used only if the primary model fails with a transient/capacity error,
    # or if the primary model itself turns out to be unavailable/not found.
    GEMINI_FALLBACK_MODEL: str = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")
    # Per-attempt network timeout for a single Gemini call.
    GEMINI_TIMEOUT_SECONDS: float = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "10"))
    # Hard ceiling on the whole primary+fallback+retries sequence, so a single
    # chat request can never hang indefinitely regardless of retry count.
    GEMINI_TOTAL_TIMEOUT_SECONDS: float = float(os.getenv("GEMINI_TOTAL_TIMEOUT_SECONDS", "25"))
    CHAT_MAX_HISTORY: int = int(os.getenv("CHAT_MAX_HISTORY", "12"))
    CHAT_RATE_LIMIT: int = int(os.getenv("CHAT_RATE_LIMIT", "20"))
    CHAT_RATE_WINDOW_SECONDS: int = int(os.getenv("CHAT_RATE_WINDOW_SECONDS", "60"))
    WHATSAPP_NUMBER: str = os.getenv("WHATSAPP_NUMBER", "")

    # Payment
    MERCHANT_UPI_ID: str = os.getenv("MERCHANT_UPI_ID", "")
    MERCHANT_NAME: str = os.getenv("MERCHANT_NAME", "FBO Store")
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")

    # CORS
    CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "").split(",")
        if origin.strip()
    ] or [
        # Local development
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://localhost:5000",
        "http://localhost:8080",

        # Vercel deployments
        "https://shopbyfbo.vercel.app",
        "https://www.shopbyfbo.vercel.app",
        "https://shopbyfbo-repo.vercel.app",
        "https://www.shopbyfbo-repo.vercel.app",

        # Render backend
        "https://shopverse-1-la3b.onrender.com",
    ]

    # Rate Limiting
    RATE_LIMIT_LOGIN: int = int(os.getenv("RATE_LIMIT_LOGIN", "5"))
    RATE_LIMIT_REGISTER: int = int(os.getenv("RATE_LIMIT_REGISTER", "3"))
    RATE_LIMIT_CHECKOUT: int = int(os.getenv("RATE_LIMIT_CHECKOUT", "10"))
    RATE_LIMIT_UPLOAD: int = int(os.getenv("RATE_LIMIT_UPLOAD", "20"))

    # File Upload
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "5242880"))
    MAX_IMAGE_WIDTH: int = int(os.getenv("MAX_IMAGE_WIDTH", "4096"))
    MAX_IMAGE_HEIGHT: int = int(os.getenv("MAX_IMAGE_HEIGHT", "4096"))

    # Security
    SECURE_COOKIES: bool = os.getenv("SECURE_COOKIES", "True").lower() == "true"

    # Categories
    CATEGORIES: List[str] = [
        "Aloe Drinks",
        "Bee Products",
        "Personal Care",
        "Nutrition",
        "Weight Management",
        "Skincare",
    ]

    @classmethod
    def validate(cls):
        """Validate required settings."""
        required = [
            "MONGO_URL", "DB_NAME", "JWT_SECRET",
            "ADMIN_EMAIL", "ADMIN_PASSWORD"
        ]
        missing = [r for r in required if not getattr(cls, r)]
        if missing:
            raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

        if len(cls.JWT_SECRET) < 32:
            raise RuntimeError("JWT_SECRET must be at least 32 characters")

        if cls.DEBUG and cls.ENVIRONMENT == "production":
            raise RuntimeError("DEBUG must be False in production")

        # Google OAuth is optional, but if partially configured it's almost
        # certainly a misconfiguration that will surface as a 500 at runtime
        # (see verify_google_token). Fail fast at startup instead.
        if bool(cls.GOOGLE_CLIENT_ID) != bool(cls.GOOGLE_CLIENT_SECRET):
            raise RuntimeError(
                "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must both be set, or both left empty"
            )

        if not cls.GOOGLE_CLIENT_ID:
            logging.getLogger(__name__).warning(
                "GOOGLE_CLIENT_ID is not set - /auth/google-login will always fail with 500"
            )

        return True

# Validate settings
Settings.validate()

# Initialize Cloudinary if configured
if Settings.CLOUDINARY_CLOUD_NAME:
    cloudinary.config(
        cloud_name=Settings.CLOUDINARY_CLOUD_NAME,
        api_key=Settings.CLOUDINARY_API_KEY,
        api_secret=Settings.CLOUDINARY_API_SECRET,
        secure=True,
    )

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record):
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)

def setup_logging():
    """Configure logging."""
    log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper())

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.setLevel(log_level)

    if os.getenv("LOG_FORMAT", "json") == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))

    root_logger.addHandler(handler)

    # Reduce third-party logging
    for lib in ["motor", "pymongo", "httpx", "urllib3"]:
        logging.getLogger(lib).setLevel(logging.WARNING)

    return logging.getLogger(__name__)

logger = setup_logging()

# ============================================================================
# DATABASE CONNECTION
# ============================================================================

class Database:
    """Singleton database manager."""

    _instance = None
    _client: Optional[AsyncIOMotorClient] = None
    _db: Optional[AsyncIOMotorDatabase] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self):
        """Establish database connection."""
        if self._client is None:
            try:
                self._client = AsyncIOMotorClient(
                    Settings.MONGO_URL,
                    maxPoolSize=Settings.MONGO_MAX_POOL_SIZE,
                    minPoolSize=Settings.MONGO_MIN_POOL_SIZE,
                    serverSelectionTimeoutMS=5000,
                )
                self._db = self._client[Settings.DB_NAME]
                await self._client.admin.command('ping')
                await self._create_indexes()
                logger.info(f"Connected to database: {Settings.DB_NAME}")
            except Exception as e:
                logger.error(f"Database connection failed: {e}")
                raise

    async def _create_indexes(self):
        """Create database indexes."""
        try:
            # Users
            await self._db.users.create_index("email", unique=True)
            await self._db.users.create_index("user_id", unique=True)
            await self._db.users.create_index("created_at")

            # Products
            await self._db.products.create_index("product_id", unique=True)
            await self._db.products.create_index("category")
            await self._db.products.create_index("status")
            await self._db.products.create_index("featured")
            await self._db.products.create_index("created_at")
            await self._db.products.create_index("sku", sparse=True, unique=True)

            # Orders
            await self._db.orders.create_index("order_id", unique=True)
            await self._db.orders.create_index("user_id")
            await self._db.orders.create_index("status")
            await self._db.orders.create_index("created_at")
            await self._db.orders.create_index("payment_ref", sparse=True)
            await self._db.orders.create_index([("user_id", 1), ("created_at", -1)])

            # Carts
            await self._db.carts.create_index("user_id", unique=True)

            # Token blacklist
            await self._db.token_blacklist.create_index("jti", unique=True)
            await self._db.token_blacklist.create_index("expires_at", expireAfterSeconds=0)

            # Analytics
            await self._db.analytics_visits.create_index("session_id")
            await self._db.analytics_visits.create_index("timestamp")
            await self._db.analytics_visits.create_index("page")

            await self._db.analytics_clicks.create_index("session_id")
            await self._db.analytics_clicks.create_index("timestamp")

            # Login attempts
            await self._db.login_attempts.create_index("email")
            await self._db.login_attempts.create_index("timestamp", expireAfterSeconds=3600)

            logger.info("Database indexes created")
        except Exception as e:
            logger.error(f"Index creation failed: {e}")
            raise

    @property
    def db(self) -> AsyncIOMotorDatabase:
        if self._db is None:
            raise RuntimeError("Database not connected")
        return self._db

    async def close(self):
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            logger.info("Database connection closed")

db_manager = Database()

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def generate_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}" if prefix else uuid.uuid4().hex[:12]

def now_iso() -> str:
    """Get current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()

def parse_iso_to_datetime(iso_str: str) -> datetime:
    """Parse ISO datetime string to datetime object."""
    return datetime.fromisoformat(iso_str.replace('Z', '+00:00'))

def is_valid_uuid(uuid_str: str) -> bool:
    """Check if string is a valid UUID."""
    try:
        uuid.UUID(uuid_str)
        return True
    except ValueError:
        return False

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal."""
    filename = filename.replace('../', '').replace('..\\', '')
    filename = filename.replace('/', '_').replace('\\', '_')
    filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
    if not filename or filename.startswith('.'):
        filename = f"file_{uuid.uuid4().hex[:8]}.jpg"
    return filename[:255]

def get_client_ip(request: Request) -> str:
    """Get client IP address from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def is_admin(user: dict) -> bool:
    """Check if user has admin role."""
    return user.get("role") == "admin"

# ============================================================================
# SECURITY UTILITIES
# ============================================================================

class PasswordHasher:
    """Password hashing using bcrypt."""

    @staticmethod
    def hash(password: str) -> str:
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    @staticmethod
    def verify(password: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        except (ValueError, TypeError):
            return False

class JWTManager:
    """JWT token management with full security claims."""

    def __init__(self):
        self.secret = Settings.JWT_SECRET
        self.algorithm = Settings.JWT_ALGORITHM
        self.issuer = Settings.JWT_ISSUER
        self.audience = Settings.JWT_AUDIENCE

    def create_access_token(self, user_id: str, email: str, role: str = "customer") -> str:
        jti = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        payload = {
            "jti": jti,
            "sub": user_id,
            "email": email,
            "role": role,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=Settings.ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
            "type": "access",
            "iss": self.issuer,
            "aud": self.audience,
        }

        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: str) -> str:
        jti = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        payload = {
            "jti": jti,
            "sub": user_id,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(days=Settings.REFRESH_TOKEN_EXPIRE_DAYS)).timestamp()),
            "type": "refresh",
            "iss": self.issuer,
            "aud": self.audience,
        }

        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def decode_token(self, token: str, verify_type: Optional[str] = None) -> Dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "nbf", "jti"]}
            )

            if verify_type and payload.get("type") != verify_type:
                raise jwt.InvalidTokenError("Invalid token type")

            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise HTTPException(status_code=401, detail="Invalid token")
        except Exception as e:
            logger.error(f"Token decode error: {e}")
            raise HTTPException(status_code=401, detail="Invalid token")

    async def revoke_token(self, jti: str, expires_at: int) -> bool:
        try:
            await db_manager.db.token_blacklist.insert_one({
                "jti": jti,
                "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc),
                "revoked_at": datetime.now(timezone.utc),
            })
            return True
        except Exception as e:
            logger.error(f"Token revocation failed: {e}")
            return False

    async def is_token_revoked(self, jti: str) -> bool:
        try:
            result = await db_manager.db.token_blacklist.find_one({"jti": jti})
            return result is not None
        except Exception:
            return False

password_hasher = PasswordHasher()
jwt_manager = JWTManager()

# ============================================================================
# RATE LIMITING
# ============================================================================

class RateLimiter:
    """In-memory rate limiter."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> bool:
        now = time.time()

        async with self._lock:
            if key not in self._requests:
                self._requests[key] = []

            self._requests[key] = [
                ts for ts in self._requests[key]
                if now - ts < self.window_seconds
            ]

            if len(self._requests[key]) >= self.max_requests:
                return False

            self._requests[key].append(now)
            return True

rate_limiters = {
    "login": RateLimiter(Settings.RATE_LIMIT_LOGIN, 300),
    "register": RateLimiter(Settings.RATE_LIMIT_REGISTER, 3600),
    "checkout": RateLimiter(Settings.RATE_LIMIT_CHECKOUT, 300),
    "upload": RateLimiter(Settings.RATE_LIMIT_UPLOAD, 3600),
}

async def check_rate_limit(request: Request, limiter_key: str) -> None:
    """Check rate limit for a request."""
    key_prefix = limiter_key
    user_id = "anonymous"

    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if token:
        try:
            payload = jwt.decode(token, Settings.JWT_SECRET, algorithms=[Settings.JWT_ALGORITHM])
            user_id = payload.get("sub", "anonymous")
        except Exception:
            pass

    client_ip = get_client_ip(request)
    key = f"{key_prefix}:{user_id if user_id != 'anonymous' else client_ip}"

    limiter = rate_limiters.get(limiter_key)
    if not limiter:
        return

    if not await limiter.check(key):
        logger.warning(f"Rate limit exceeded: {key}")
        raise HTTPException(
            status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later."
        )

# ============================================================================
# MIDDLEWARE
# ============================================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), "
            "payment=(), usb=(), magnetometer=(), accelerometer=(), "
            "gyroscope=(), speaker=(), vibrate=(), fullscreen=()"
        )

        if Settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        csp = (
            "default-src 'self'; "
            "img-src 'self' data: https://res.cloudinary.com https://images.unsplash.com https://*.googleusercontent.com https://*.google.com; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://checkout.razorpay.com https://accounts.google.com https://*.google.com; "
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self' data:; "
            "connect-src 'self' https://api.razorpay.com https://accounts.google.com https://*.google.com; "
            "frame-src 'self' https://checkout.razorpay.com https://accounts.google.com https://*.google.com;"
        )
        response.headers["Content-Security-Policy"] = csp

        if "Cross-Origin-Opener-Policy" in response.headers:
            del response.headers["Cross-Origin-Opener-Policy"]

        return response

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add request ID for tracing."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        return response

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        logger.info(f"Request: {request.method} {request.url.path} from {get_client_ip(request)}")

        response = await call_next(request)

        duration = time.time() - start_time
        logger.info(
            f"Response: {request.method} {request.url.path} "
            f"status={response.status_code} duration={duration:.3f}s"
        )

        return response

# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password")

    @validator('password')
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v

class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=12, description="User password")
    name: str = Field(..., min_length=2, max_length=100, description="Full name")
    confirm_password: str = Field(..., description="Confirm password")

    @validator('password')
    def validate_password_strength(cls, v):
        if len(v) < 12:
            raise ValueError('Password must be at least 12 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v

    @validator('confirm_password')
    def validate_password_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v

class GoogleLoginRequest(BaseModel):
    id_token: str = Field(..., description="Google ID token")
    email: EmailStr = Field(..., description="User email")
    name: str = Field(..., min_length=1, max_length=100, description="Full name")
    picture: Optional[str] = Field("", description="Profile picture URL")

class RefreshTokenRequest(BaseModel):
    refresh_token: Optional[str] = Field(None, description="Refresh token")

class UserResponse(BaseModel):
    user_id: str
    email: str
    name: str
    role: str = "customer"
    picture: Optional[str] = ""
    auth_provider: str = "password"
    created_at: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    user: UserResponse

class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)
    category: str = Field(..., min_length=1, max_length=50)
    mrp: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    bv: float = Field(0, ge=0)
    cc: float = Field(0, ge=0)
    stock: int = Field(0, ge=0)
    status: Literal["active", "out_of_stock", "discontinued"] = "active"
    images: List[str] = Field(default_factory=list, max_items=10)
    featured: bool = False
    sku: Optional[str] = Field(None, max_length=50)

    @validator('price')
    def validate_price(cls, v, values):
        if 'mrp' in values and v > values['mrp']:
            raise ValueError('Price cannot exceed MRP')
        return v

class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=10, max_length=2000)
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    mrp: Optional[float] = Field(None, gt=0)
    price: Optional[float] = Field(None, gt=0)
    bv: Optional[float] = Field(None, ge=0)
    cc: Optional[float] = Field(None, ge=0)
    stock: Optional[int] = Field(None, ge=0)
    status: Optional[Literal["active", "out_of_stock", "discontinued"]] = None
    images: Optional[List[str]] = Field(None, max_items=10)
    featured: Optional[bool] = None
    sku: Optional[str] = Field(None, max_length=50)


class ProductResponse(ProductBase):
    product_id: str
    created_at: str
    updated_at: str

class CartItem(BaseModel):
    product_id: str
    quantity: int = Field(1, gt=0)

class CartItemAdd(CartItem):
    pass

class CartItemUpdate(CartItem):
    pass

class CartResponse(BaseModel):
    user_id: str
    items: List[dict]
    subtotal: float
    total_bv: float
    total_cc: float

class Address(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., min_length=10, max_length=10)
    line1: str = Field(..., min_length=3, max_length=200)
    line2: Optional[str] = Field(None, max_length=200)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    pincode: str = Field(..., min_length=6, max_length=6)

    @validator('phone')
    def validate_phone(cls, v):
        if not re.match(r'^[6-9]\d{9}$', v):
            raise ValueError('Invalid phone number. Must be 10 digits starting with 6-9')
        return v

    @validator('pincode')
    def validate_pincode(cls, v):
        if not re.match(r'^[1-9][0-9]{5}$', v):
            raise ValueError('Invalid pincode')
        return v

class CheckoutRequest(BaseModel):
    address: Address
    payment_method: Literal["upi", "razorpay", "cod"] = "upi"

class UTRSubmitRequest(BaseModel):
    order_id: str
    utr: str = Field(..., min_length=6, max_length=32)

    @validator('utr')
    def validate_utr(cls, v):
        if not re.match(r'^[A-Za-z0-9]{6,32}$', v):
            raise ValueError('Invalid UTR format')
        return v

class OrderResponse(BaseModel):
    order_id: str
    user_id: str
    user_email: str
    items: List[dict]
    address: dict
    payment_method: str
    subtotal: float
    shipping: float
    total: float
    total_bv: float
    total_cc: float
    status: str
    upi_id: Optional[str] = None
    upi_url: Optional[str] = None
    created_at: str

class VisitTrack(BaseModel):
    page: str = Field(..., max_length=200)
    referrer: Optional[str] = Field("", max_length=500)
    device: Optional[str] = Field("", max_length=50)
    browser: Optional[str] = Field("", max_length=50)
    os: Optional[str] = Field("", max_length=50)
    screen: Optional[str] = Field("", max_length=50)
    session_id: str = Field(..., max_length=100)
    utm_source: Optional[str] = Field("", max_length=100)
    utm_medium: Optional[str] = Field("", max_length=100)
    utm_campaign: Optional[str] = Field("", max_length=100)
    utm_content: Optional[str] = Field("", max_length=100)

class ClickTrack(BaseModel):
    session_id: str = Field(..., max_length=100)
    element: str = Field(..., max_length=100)
    page: str = Field(..., max_length=200)
    label: Optional[str] = Field("", max_length=200)

class StatusUpdate(BaseModel):
    status: str

class PaymentVerification(BaseModel):
    action: Literal["verify", "reject"]
    notes: Optional[str] = Field(None, max_length=500)

# ============================================================================
# AUTHENTICATION DEPENDENCIES
# ============================================================================

security = HTTPBearer(auto_error=False)

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Get current user from token."""
    token = None

    if credentials:
        token = credentials.credentials

    if not token:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt_manager.decode_token(token, verify_type="access")

        if await jwt_manager.is_token_revoked(payload["jti"]):
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED,
                detail="Token revoked"
            )

        user = await db_manager.db.users.find_one(
            {"user_id": payload["sub"]},
            {"_id": 0, "password_hash": 0}
        )

        if not user:
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication"
        )

async def get_current_active_user(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """Get current active user."""
    return current_user

async def get_current_admin_user(
    current_user: dict = Depends(get_current_active_user)
) -> dict:
    """Get current admin user."""
    if not is_admin(current_user):
        logger.warning(f"Admin access denied for user: {current_user.get('user_id')}")
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """Get current user if authenticated, otherwise None."""
    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None

# ============================================================================
# GOOGLE OAUTH VERIFICATION
# ============================================================================

async def verify_google_token(id_token_str: str) -> Dict[str, Any]:
    """Verify a Google ID token and return trusted claims."""
    if not Settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google authentication is not configured")
    try:
        try:
            from google.oauth2 import id_token as google_id_token
            from google.auth.transport import requests as google_requests
            payload = await asyncio.to_thread(
                google_id_token.verify_oauth2_token,
                id_token_str, google_requests.Request(), Settings.GOOGLE_CLIENT_ID
            )
        except ImportError:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(
                    "https://oauth2.googleapis.com/tokeninfo",
                    params={"id_token": id_token_str}
                )
            if response.status_code != 200:
                raise ValueError("Invalid Google token")
            payload = response.json()
        if payload.get("aud") != Settings.GOOGLE_CLIENT_ID:
            raise ValueError("Invalid token audience")
        if payload.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
            raise ValueError("Invalid token issuer")
        if payload.get("email_verified") is not True:
            raise ValueError("Google email is not verified")
        if not payload.get("sub") or not payload.get("email"):
            raise ValueError("Google token is missing required claims")
        return payload
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Google authentication timeout")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Google authentication service unavailable")
    except Exception as e:
        logger.warning("Google verification failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid Google authentication")

# ============================================================================
# EMAIL FUNCTIONS
# ============================================================================

def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """Send email using SMTP."""
    if not Settings.SMTP_USER or not Settings.SMTP_PASS:
        logger.warning("Email not configured")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{Settings.SMTP_FROM_NAME} <{Settings.SMTP_FROM_EMAIL or Settings.SMTP_USER}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(Settings.SMTP_HOST, Settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(Settings.SMTP_USER, Settings.SMTP_PASS)
            server.sendmail(Settings.SMTP_USER, to_email, msg.as_string())

        logger.info(f"Email sent to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False

def send_order_confirmation_email(to_email: str, user_name: str, order: dict) -> bool:
    """Send order confirmation email."""
    items_rows = ""
    for item in order.get("items", []):
        items_rows += f"""
        <tr>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;">{item.get('name', 'Product')}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center;">{item.get('quantity', 0)}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:right;">₹{item.get('price', 0) * item.get('quantity', 0):.2f}</td>
        </tr>"""

    addr = order.get("address", {})
    address_str = f"{addr.get('full_name', '')}, {addr.get('line1', '')}, {addr.get('city', '')}, {addr.get('state', '')} - {addr.get('pincode', '')}"

    html = f"""
    <html>
    <body style="font-family:Arial,sans-serif;background:#f9f9f9;margin:0;padding:0;">
        <div style="max-width:600px;margin:30px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
            <div style="background:#1a5c38;padding:28px 32px;">
                <h1 style="color:#fff;margin:0;font-size:22px;">🌿 Order Confirmed!</h1>
                <p style="color:#a8d5b5;margin:6px 0 0;">Thank you for your order</p>
            </div>
            <div style="padding:28px 32px;">
                <p style="font-size:15px;color:#333;">Hi <strong>{user_name}</strong>,</p>
                <p style="color:#555;font-size:14px;">We received your order request. Payment is awaiting completion/verification. Here are the details:</p>
                <div style="background:#f0f7f3;border-left:4px solid #1a5c38;padding:12px 16px;border-radius:6px;margin:16px 0;">
                    <strong style="color:#1a5c38;">Order ID:</strong>
                    <span style="font-family:monospace;color:#333;margin-left:8px;">{order.get('order_id', '')}</span>
                </div>
                <table style="width:100%;border-collapse:collapse;margin:20px 0;font-size:14px;">
                    <thead>
                        <tr style="background:#f5f5f5;">
                            <th style="padding:10px 12px;text-align:left;color:#555;">Product</th>
                            <th style="padding:10px 12px;text-align:center;color:#555;">Qty</th>
                            <th style="padding:10px 12px;text-align:right;color:#555;">Amount</th>
                        </tr>
                    </thead>
                    <tbody>{items_rows}</tbody>
                </table>
                <table style="width:100%;font-size:14px;margin-top:8px;">
                    <tr><td style="color:#777;padding:4px 0;">Subtotal</td><td style="text-align:right;color:#333;">₹{order.get('subtotal', 0):.2f}</td></tr>
                    <tr><td style="color:#777;padding:4px 0;">Shipping</td><td style="text-align:right;color:#333;">{"Free" if order.get('shipping', 0) == 0 else f"₹{order.get('shipping', 0):.2f}"}</td></tr>
                    <tr style="font-weight:bold;font-size:15px;border-top:2px solid #eee;">
                        <td style="padding-top:8px;color:#1a5c38;">Total</td>
                        <td style="text-align:right;padding-top:8px;color:#1a5c38;">₹{order.get('total', 0):.2f}</td>
                    </tr>
                </table>
                <div style="margin-top:24px;padding:14px 16px;border:1px solid #eee;border-radius:8px;font-size:13px;color:#555;">
                    <strong style="color:#333;">Delivery Address:</strong><br/>
                    <span style="margin-top:4px;display:block;">{address_str}</span>
                </div>
                <p style="font-size:13px;color:#777;margin-top:16px;">
                    <strong>Payment:</strong> {order.get('payment_method', 'UPI').upper()} &nbsp;|&nbsp;
                    <strong>Status:</strong> {order.get('status', 'awaiting_payment').replace('_', ' ').title()}
                </p>
                <p style="font-size:14px;color:#333;margin-top:24px;">
                    Thank you for choosing <strong style="color:#1a5c38;">ShopVerse FBO</strong>! 🌿
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    return send_email(to_email, f"Order Confirmed — {order.get('order_id', '')}", html)

def send_delivery_email(to_email: str, user_name: str, order: dict) -> bool:
    """Send delivery confirmation email."""
    addr = order.get("address", {})
    address_str = f"{addr.get('full_name', '')}, {addr.get('line1', '')}, {addr.get('city', '')}, {addr.get('state', '')} - {addr.get('pincode', '')}"

    html = f"""
    <html>
    <body style="font-family:Arial,sans-serif;background:#f9f9f9;">
        <div style="max-width:600px;margin:30px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
            <div style="background:#1a5c38;padding:28px 32px;">
                <h1 style="color:#fff;margin:0;font-size:22px;">📦 Order Delivered!</h1>
                <p style="color:#a8d5b5;margin:6px 0 0;">Your order has been successfully delivered</p>
            </div>
            <div style="padding:28px 32px;">
                <p style="font-size:15px;color:#333;">Hi <strong>{user_name}</strong>,</p>
                <p style="color:#555;font-size:14px;">Great news! Your order has been delivered.</p>
                <div style="background:#f0f7f3;border-left:4px solid #1a5c38;padding:12px 16px;border-radius:6px;margin:16px 0;">
                    <strong style="color:#1a5c38;">Order ID:</strong>
                    <span style="font-family:monospace;color:#333;margin-left:8px;">{order.get('order_id', '')}</span>
                </div>
                <div style="margin-top:16px;padding:14px 16px;border:1px solid #eee;border-radius:8px;font-size:13px;color:#555;">
                    <strong>Delivered To:</strong><br/>{address_str}
                </div>
                <p style="font-size:14px;color:#333;margin-top:24px;">
                    Thank you for choosing <strong style="color:#1a5c38;">ShopVerse FBO</strong>! 🌿
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    return send_email(to_email, f"Your Order {order.get('order_id', '')} Has Been Delivered!", html)

# ============================================================================
# API ROUTES - AUTHENTICATION
# ============================================================================

def create_auth_response(user: dict, access_token: str, refresh_token: Optional[str] = None) -> dict:
    """Create standardized auth response."""
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": Settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "refresh_token": refresh_token,
        "user": {
            "user_id": user["user_id"],
            "email": user["email"],
            "name": user.get("name", ""),
            "role": user.get("role", "customer"),
            "picture": user.get("picture", ""),
            "auth_provider": user.get("auth_provider", "password"),
            "created_at": user.get("created_at", ""),
        }
    }

async def register_user(email: str, password: str, name: str) -> dict:
    """Register a new user."""
    existing = await db_manager.db.users.find_one({"email": email})
    if existing:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Registration failed"  # Generic message to prevent enumeration
        )

    user_id = generate_id("user")
    user_doc = {
        "user_id": user_id,
        "email": email,
        "name": name,
        "password_hash": password_hasher.hash(password),
        "role": "customer",
        "auth_provider": "password",
        "created_at": now_iso(),
    }

    await db_manager.db.users.insert_one(user_doc)
    user_doc.pop("password_hash", None)

    return user_doc

# ============================================================================
# FILE UPLOAD VALIDATION
# ============================================================================

async def validate_uploaded_file(file: UploadFile) -> bytes:
    """Validate uploaded file with multiple checks."""
    content = await file.read()

    if len(content) > Settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Max {Settings.MAX_FILE_SIZE // (1024*1024)}MB"
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Empty file"
        )

    mime_type = magic.from_buffer(content[:1024], mime=True)
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/gif"]

    if mime_type not in allowed_types:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {mime_type}. Allowed: {', '.join(allowed_types)}"
        )

    ext_map = {
        "image/jpeg": [".jpg", ".jpeg"],
        "image/png": [".png"],
        "image/webp": [".webp"],
        "image/gif": [".gif"],
    }

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ext_map.get(mime_type, []):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="File extension does not match content type"
        )

    try:
        img = Image.open(io.BytesIO(content))
        width, height = img.size

        if width > Settings.MAX_IMAGE_WIDTH or height > Settings.MAX_IMAGE_HEIGHT:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Image too large. Max {Settings.MAX_IMAGE_WIDTH}x{Settings.MAX_IMAGE_HEIGHT}"
            )

        img.verify()
        img.close()

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file"
        )

    return content

# ============================================================================
# API ROUTES - AUTHENTICATION ENDPOINTS
# ============================================================================

async def auth_register_endpoint(request: Request, data: RegisterRequest):
    """Register a new user."""
    await check_rate_limit(request, "register")

    email = data.email.lower()
    user = await register_user(email, data.password, data.name)

    access_token = jwt_manager.create_access_token(user["user_id"], user["email"], user["role"])
    refresh_token = jwt_manager.create_refresh_token(user["user_id"])

    response = create_auth_response(user, access_token, refresh_token)

    response_obj = JSONResponse(content=response)
    if Settings.SECURE_COOKIES:
        response_obj.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="none",  # cross-site cookie: frontend and backend are on different domains
            max_age=Settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            path=f"{Settings.API_PREFIX}/auth/refresh"
        )

    logger.info(f"User registered: {email}")
    return response_obj

async def auth_login_endpoint(request: Request, data: LoginRequest):
    """Login user."""
    await check_rate_limit(request, "login")

    email = data.email.lower()

    login_attempt = await db_manager.db.login_attempts.insert_one({
        "email": email,
        "timestamp": datetime.now(timezone.utc),
        "success": False,
        "ip": get_client_ip(request),
    })

    user = await db_manager.db.users.find_one({"email": email})
    if not user:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not password_hasher.verify(data.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    access_token = jwt_manager.create_access_token(
        user["user_id"],
        user["email"],
        user.get("role", "customer")
    )
    refresh_token = jwt_manager.create_refresh_token(user["user_id"])

    # Update the exact login_attempts row we just inserted, by _id - not by
    # re-matching on {email, success: False} with a sort. update_one()'s sort
    # parameter must be a dict (e.g. {"timestamp": -1}), not a list of tuples
    # like [("timestamp", -1)] (that shape is only valid for cursor.sort()).
    # Passing the list-of-tuples form gets BSON-encoded as an array, which
    # MongoDB's server rejects with "sort must be a document" -> pymongo
    # raises OperationFailure -> uncaught 500 on every successful login.
    await db_manager.db.login_attempts.update_one(
        {"_id": login_attempt.inserted_id},
        {"$set": {"success": True, "user_id": user["user_id"]}}
    )

    user.pop("password_hash", None)
    response = create_auth_response(user, access_token, refresh_token)

    response_obj = JSONResponse(content=response)
    if Settings.SECURE_COOKIES:
        response_obj.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="none",  # cross-site cookie: frontend and backend are on different domains
            max_age=Settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            path=f"{Settings.API_PREFIX}/auth/refresh"
        )

    logger.info(f"User logged in: {email}")
    return response_obj

# ============================================================================
# GOOGLE LOGIN ENDPOINT
# ============================================================================

async def auth_google_login_endpoint(request: Request):
    """
    Google OAuth login. Accepts several credential shapes so it works with
    both Google Identity Services One Tap (`credential`) and hand-rolled
    clients (`id_token` / `token` + `email`/`name`/`picture`).
    """
    await check_rate_limit(request, "login")

    try:
        data = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON request body"
        )

    logger.info(f"Google login - received keys: {list(data.keys())}")

    # Accept credential / id_token / token, in that order of preference.
    token = data.get("credential") or data.get("id_token") or data.get("token")

    if not token:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Missing credential or id_token"
        )

    # Try to pull email/name/picture out of the unverified JWT payload as a
    # fallback if the client didn't send them explicitly. This is ONLY used
    # to pre-fill fields; the token is still verified against Google below,
    # and the verified email always takes precedence.
    user_email = data.get("email")
    user_name = data.get("name", "")
    user_picture = data.get("picture", "")

    if not user_email:
        try:
            parts = token.split('.')
            if len(parts) != 3:
                raise ValueError("Invalid JWT format")
            payload_b64 = parts[1] + '=' * (-len(parts[1]) % 4)
            token_data = json.loads(base64.urlsafe_b64decode(payload_b64))
            user_email = token_data.get('email')
            user_name = user_name or token_data.get('name', '')
            user_picture = user_picture or token_data.get('picture', '')
        except Exception as e:
            logger.warning(f"Could not pre-decode Google token payload: {e}")

    if not user_email:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Missing email - please ensure your Google account has an email"
        )

    # Verify the token with Google. This is the authoritative check; the
    # verified email always overrides whatever the client claimed.
    google_payload = await verify_google_token(token)
    verified_email = google_payload.get('email')

    if not verified_email:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Google token did not include an email"
        )

    if verified_email != user_email:
        logger.warning(f"Client-claimed email {user_email} != verified email {verified_email}")

    email = verified_email.lower()

    user = await db_manager.db.users.find_one({"email": email})

    if not user:
        user_id = generate_id("user")
        user_doc = {
            "user_id": user_id,
            "email": email,
            "name": user_name or email.split('@')[0],
            "picture": user_picture,
            "role": "customer",
            "auth_provider": "google",
            "created_at": now_iso(),
        }
        await db_manager.db.users.insert_one(user_doc)
        user = user_doc
        logger.info(f"New user created via Google: {email}")
    else:
        update_data = {
            "auth_provider": "google",
            "last_login": now_iso(),
        }
        if user_name:
            update_data["name"] = user_name
        if user_picture:
            update_data["picture"] = user_picture

        await db_manager.db.users.update_one(
            {"email": email},
            {"$set": update_data}
        )
        user = await db_manager.db.users.find_one(
            {"email": email},
            {"_id": 0, "password_hash": 0}
        )
        logger.info(f"User updated via Google: {email}")

    access_token = jwt_manager.create_access_token(
        user["user_id"],
        user["email"],
        user.get("role", "customer")
    )
    refresh_token = jwt_manager.create_refresh_token(user["user_id"])

    response = create_auth_response(user, access_token, refresh_token)

    response_obj = JSONResponse(content=response)
    if Settings.SECURE_COOKIES:
        response_obj.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="none",  # cross-site cookie: frontend and backend are on different domains
            max_age=Settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            path=f"{Settings.API_PREFIX}/auth/refresh"
        )

    logger.info(f"Google login successful: {email}")
    return response_obj

# ============================================================================
# REFRESH / LOGOUT / ME
# ============================================================================

async def auth_refresh_endpoint(request: Request):
    """Refresh access token."""
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        try:
            body = await request.json()
            refresh_token = body.get("refresh_token")
        except Exception:
            pass

    if not refresh_token:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required"
        )

    try:
        payload = jwt_manager.decode_token(refresh_token, verify_type="refresh")

        if await jwt_manager.is_token_revoked(payload["jti"]):
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED,
                detail="Token revoked"
            )

        await jwt_manager.revoke_token(payload["jti"], payload["exp"])

        user = await db_manager.db.users.find_one(
            {"user_id": payload["sub"]},
            {"_id": 0, "password_hash": 0}
        )

        if not user:
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        access_token = jwt_manager.create_access_token(
            user["user_id"],
            user["email"],
            user.get("role", "customer")
        )
        new_refresh_token = jwt_manager.create_refresh_token(user["user_id"])

        response = create_auth_response(user, access_token, new_refresh_token)

        response_obj = JSONResponse(content=response)
        if Settings.SECURE_COOKIES:
            response_obj.set_cookie(
                key="refresh_token",
                value=new_refresh_token,
                httponly=True,
                secure=True,
                samesite="none",  # cross-site cookie: frontend and backend are on different domains
                max_age=Settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
                path=f"{Settings.API_PREFIX}/auth/refresh"
            )

        return response_obj

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Refresh error: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

async def auth_logout_endpoint(request: Request):
    """Logout user and revoke tokens."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if token:
        try:
            payload = jwt_manager.decode_token(token)
            await jwt_manager.revoke_token(payload["jti"], payload["exp"])
        except Exception:
            pass

    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            payload = jwt_manager.decode_token(refresh_token)
            await jwt_manager.revoke_token(payload["jti"], payload["exp"])
        except Exception:
            pass

    response = JSONResponse(content={"ok": True, "message": "Logged out successfully"})
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path=f"{Settings.API_PREFIX}/auth/refresh")

    logger.info(f"User logged out from {get_client_ip(request)}")
    return response

async def auth_me_endpoint(current_user: dict = Depends(get_current_user)):
    """Get current user info."""
    return current_user

# ============================================================================
# API ROUTES - PRODUCTS
# ============================================================================

async def list_products_endpoint(
    category: Optional[str] = Query(None, max_length=50),
    q: Optional[str] = Query(None, max_length=200),
    featured: Optional[bool] = None,
    status_filter: Optional[str] = Query(None, max_length=20, alias="status"),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    sort_by: Optional[str] = Query(None, regex="^(price|created_at|name)$"),
    sort_order: Literal["asc", "desc"] = "desc",
):
    """List products with filtering and pagination."""
    query = {}

    if category:
        query["category"] = category

    if featured is not None:
        query["featured"] = featured

    if status_filter:
        if status_filter not in ["active", "out_of_stock", "discontinued"]:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Invalid status"
            )
        query["status"] = status_filter
    else:
        query["status"] = {"$in": ["active", "out_of_stock"]}

    if q:
        sanitized_q = re.escape(q)
        query["$or"] = [
            {"name": {"$regex": sanitized_q, "$options": "i"}},
            {"description": {"$regex": sanitized_q, "$options": "i"}},
        ]

    if min_price is not None or max_price is not None:
        price_filter = {}
        if min_price is not None:
            price_filter["$gte"] = min_price
        if max_price is not None:
            price_filter["$lte"] = max_price
        query["price"] = price_filter

    sort_field = sort_by or "created_at"
    sort_direction = -1 if sort_order == "desc" else 1

    cursor = db_manager.db.products.find(query, {"_id": 0})
    cursor = cursor.sort(sort_field, sort_direction).skip(skip).limit(limit)
    products = await cursor.to_list(length=limit)

    total = await db_manager.db.products.count_documents(query)

    return {
        "items": products,
        "total": total,
        "limit": limit,
        "skip": skip,
        "has_more": skip + limit < total,
    }

async def get_product_endpoint(product_id: str = PathParam(..., regex=r'^prod_[a-f0-9]{12}$')):
    """Get single product by ID."""
    product = await db_manager.db.products.find_one(
        {"product_id": product_id},
        {"_id": 0}
    )

    if not product:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    return product

async def list_categories_endpoint():
    """List all product categories."""
    return {"categories": Settings.CATEGORIES}

# ============================================================================
# API ROUTES - ADMIN PRODUCTS
# ============================================================================

async def admin_create_product_endpoint(
    data: ProductCreate,
    admin: dict = Depends(get_current_admin_user)
):
    """Create a new product (admin only)."""
    product_id = generate_id("prod")
    now = now_iso()

    product_doc = data.dict()
    product_doc.update({
        "product_id": product_id,
        "created_at": now,
        "updated_at": now,
    })

    await db_manager.db.products.insert_one(product_doc)
    product_doc.pop("_id", None)

    logger.info(f"Admin {admin['user_id']} created product: {product_id}")
    return product_doc

async def admin_update_product_endpoint(
    product_id: str = PathParam(..., regex=r'^prod_[a-f0-9]{12}$'),
    data: ProductUpdate = None,
    admin: dict = Depends(get_current_admin_user)
):
    """Update a product (admin only)."""
    update_data = data.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    update_data["updated_at"] = now_iso()

    result = await db_manager.db.products.update_one(
        {"product_id": product_id},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    product = await db_manager.db.products.find_one(
        {"product_id": product_id},
        {"_id": 0}
    )

    logger.info(f"Admin {admin['user_id']} updated product: {product_id}")
    return product

async def admin_delete_product_endpoint(
    product_id: str = PathParam(..., regex=r'^prod_[a-f0-9]{12}$'),
    admin: dict = Depends(get_current_admin_user)
):
    """Delete a product (admin only)."""
    result = await db_manager.db.products.delete_one({"product_id": product_id})

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    logger.info(f"Admin {admin['user_id']} deleted product: {product_id}")
    return {"ok": True}

async def admin_update_product_status_endpoint(
    product_id: str = PathParam(..., regex=r'^prod_[a-f0-9]{12}$'),
    new_status: str = Form(..., alias="status"),
    admin: dict = Depends(get_current_admin_user)
):
    """Update product status (admin only)."""
    if new_status not in ["active", "out_of_stock", "discontinued"]:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid status"
        )

    result = await db_manager.db.products.update_one(
        {"product_id": product_id},
        {"$set": {"status": new_status, "updated_at": now_iso()}}
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    logger.info(f"Admin {admin['user_id']} updated product status: {product_id} -> {new_status}")
    return {"ok": True, "status": new_status}

async def admin_list_all_products_endpoint(
    admin: dict = Depends(get_current_admin_user),
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0),
):
    """List all products with pagination (admin only)."""
    cursor = db_manager.db.products.find({}, {"_id": 0})
    cursor = cursor.skip(skip).limit(limit)
    products = await cursor.to_list(length=limit)
    total = await db_manager.db.products.count_documents({})

    return {
        "items": products,
        "total": total,
        "limit": limit,
        "skip": skip,
    }

# ============================================================================
# API ROUTES - FILE UPLOADS
# ============================================================================

async def upload_image_endpoint(
    request: Request,
    file: UploadFile = File(...),
    admin: dict = Depends(get_current_admin_user)
):
    """Upload product image (admin only)."""
    await check_rate_limit(request, "upload")

    content = await validate_uploaded_file(file)

    safe_filename = sanitize_filename(file.filename)
    unique_filename = f"{uuid.uuid4().hex}_{safe_filename}"

    if Settings.CLOUDINARY_CLOUD_NAME:
        try:
            result = cloudinary.uploader.upload(
                io.BytesIO(content),
                folder="shopverse",
                resource_type="image",
                public_id=f"img_{uuid.uuid4().hex[:12]}"
            )

            url = result.get("secure_url", "")
            logger.info(f"Image uploaded to Cloudinary: {url}")
            return {"filename": result.get("public_id", ""), "url": url}

        except Exception as e:
            logger.error(f"Cloudinary upload failed: {e}")
            # Fall through to local upload

    upload_dir = Path("uploads")
    upload_dir.mkdir(exist_ok=True)

    file_path = upload_dir / unique_filename

    try:
        file_path.resolve().relative_to(upload_dir.resolve())
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path"
        )

    with open(file_path, "wb") as f:
        f.write(content)

    url = f"{Settings.RENDER_URL}/uploads/{unique_filename}"
    logger.info(f"Image uploaded locally: {url}")

    return {"filename": unique_filename, "url": url}

# ============================================================================
# API ROUTES - CART
# ============================================================================

async def get_cart_endpoint(current_user: dict = Depends(get_current_user)):
    """Get user's cart."""
    cart = await db_manager.db.carts.find_one(
        {"user_id": current_user["user_id"]},
        {"_id": 0}
    )

    if not cart:
        return {
            "user_id": current_user["user_id"],
            "items": [],
            "subtotal": 0.0,
            "total_bv": 0.0,
            "total_cc": 0.0,
        }

    items_out = []
    subtotal = 0.0
    total_bv = 0.0
    total_cc = 0.0

    for item in cart.get("items", []):
        product = await db_manager.db.products.find_one(
            {"product_id": item["product_id"]},
            {"_id": 0}
        )

        if not product or product.get("status") != "active":
            continue

        line_total = product["price"] * item["quantity"]
        subtotal += line_total
        total_bv += product.get("bv", 0) * item["quantity"]
        total_cc += product.get("cc", 0) * item["quantity"]

        items_out.append({
            "product": product,
            "quantity": item["quantity"],
            "line_total": line_total,
        })

    return {
        "user_id": current_user["user_id"],
        "items": items_out,
        "subtotal": subtotal,
        "total_bv": total_bv,
        "total_cc": total_cc,
    }

async def add_to_cart_endpoint(
    data: CartItemAdd,
    current_user: dict = Depends(get_current_user)
):
    """Add item to cart."""
    product = await db_manager.db.products.find_one(
        {"product_id": data.product_id},
        {"_id": 0}
    )

    if not product:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    if product.get("status") != "active":
        raise HTTPException(status_code=400, detail="Product not available")
    if int(product.get("stock", 0)) < data.quantity:
        raise HTTPException(status_code=400, detail="Not enough stock available")

    cart = await db_manager.db.carts.find_one({"user_id": current_user["user_id"]})

    if not cart:
        await db_manager.db.carts.insert_one({
            "user_id": current_user["user_id"],
            "items": [{"product_id": data.product_id, "quantity": data.quantity}]
        })
    else:
        items = cart.get("items", [])
        found = False

        for item in items:
            if item["product_id"] == data.product_id:
                item["quantity"] += data.quantity
                found = True
                break

        if not found:
            items.append({"product_id": data.product_id, "quantity": data.quantity})

        await db_manager.db.carts.update_one(
            {"user_id": current_user["user_id"]},
            {"$set": {"items": items}}
        )

    return {"ok": True}

async def update_cart_item_endpoint(
    data: CartItemUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update cart item quantity."""
    cart = await db_manager.db.carts.find_one({"user_id": current_user["user_id"]})

    if not cart:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Cart is empty"
        )

    items = cart.get("items", [])

    if data.quantity <= 0:
        items = [item for item in items if item["product_id"] != data.product_id]
    else:
        found = False
        for item in items:
            if item["product_id"] == data.product_id:
                item["quantity"] = data.quantity
                found = True
                break

        if not found:
            items.append({"product_id": data.product_id, "quantity": data.quantity})

    await db_manager.db.carts.update_one(
        {"user_id": current_user["user_id"]},
        {"$set": {"items": items}}
    )

    return {"ok": True}

async def remove_cart_item_endpoint(
    product_id: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """Remove item from cart."""
    cart = await db_manager.db.carts.find_one({"user_id": current_user["user_id"]})

    if not cart:
        return {"ok": True}

    items = [item for item in cart.get("items", []) if item["product_id"] != product_id]

    await db_manager.db.carts.update_one(
        {"user_id": current_user["user_id"]},
        {"$set": {"items": items}}
    )

    return {"ok": True}

async def clear_cart_endpoint(current_user: dict = Depends(get_current_user)):
    """Clear all items from cart."""
    await db_manager.db.carts.update_one(
        {"user_id": current_user["user_id"]},
        {"$set": {"items": []}},
        upsert=True
    )

    return {"ok": True}

# ============================================================================
# API ROUTES - ORDERS & CHECKOUT
# ============================================================================

def build_upi_url(upi_id: str, name: str, amount: float, order_id: str) -> str:
    """Build UPI payment URL."""
    from urllib.parse import quote
    pn = quote(name)
    tn = quote(f"Order {order_id}")
    return f"upi://pay?pa={upi_id}&pn={pn}&am={amount:.2f}&tn={tn}&cu=INR"

async def checkout_endpoint(
    request: Request,
    data: CheckoutRequest,
    current_user: dict = Depends(get_current_user)
):
    """Process checkout and create order."""
    await check_rate_limit(request, "checkout")

    cart = await db_manager.db.carts.find_one({"user_id": current_user["user_id"]})

    if not cart or not cart.get("items"):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Cart is empty"
        )

    items_snapshot = []
    subtotal = 0.0
    total_bv = 0.0
    total_cc = 0.0

    for item in cart["items"]:
        product = await db_manager.db.products.find_one(
            {"product_id": item["product_id"]},
            {"_id": 0}
        )

        if not product or product.get("status") != "active":
            continue
        quantity = int(item.get("quantity", 0))
        if quantity <= 0 or quantity > Settings.MAX_CART_QUANTITY:
            raise HTTPException(status_code=400, detail="Invalid cart quantity")
        if int(product.get("stock", 0)) < quantity:
            raise HTTPException(status_code=409, detail=f"Insufficient stock for {product.get('name', 'a product')}")

        items_snapshot.append({
            "product_id": product["product_id"],
            "name": product["name"],
            "price": product["price"],
            "bv": product.get("bv", 0),
            "cc": product.get("cc", 0),
            "quantity": item["quantity"],
            "image": (product.get("images") or [""])[0],
        })

        subtotal += product["price"] * item["quantity"]
        total_bv += product.get("bv", 0) * item["quantity"]
        total_cc += product.get("cc", 0) * item["quantity"]

    if not items_snapshot:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="No purchasable items in cart"
        )

    shipping = 0.0 if subtotal >= Settings.SHIPPING_THRESHOLD else Settings.SHIPPING_FEE
    total = subtotal + shipping

    order_id = generate_id("ord")
    upi_url = build_upi_url(
        Settings.MERCHANT_UPI_ID,
        Settings.MERCHANT_NAME,
        total,
        order_id
    ) if Settings.MERCHANT_UPI_ID else ""

    order_doc = {
        "order_id": order_id,
        "user_id": current_user["user_id"],
        "user_email": current_user["email"],
        "items": items_snapshot,
        "address": data.address.dict(),
        "payment_method": data.payment_method,
        "subtotal": subtotal,
        "shipping": shipping,
        "total": total,
        "total_bv": total_bv,
        "total_cc": total_cc,
        "status": "awaiting_payment",
        "upi_id": Settings.MERCHANT_UPI_ID,
        "merchant_name": Settings.MERCHANT_NAME,
        "upi_url": upi_url,
        "created_at": now_iso(),
    }

    # Reserve stock atomically before creating the order. Roll back if order insert fails.
    reserved = []
    try:
        for item in items_snapshot:
            result = await db_manager.db.products.update_one(
                {"product_id": item["product_id"], "status": "active", "stock": {"$gte": item["quantity"]}},
                {"$inc": {"stock": -item["quantity"]}, "$set": {"updated_at": now_iso()}},
            )
            if result.modified_count != 1:
                raise HTTPException(status_code=409, detail=f"Stock changed for {item['name']}. Please review your cart.")
            reserved.append(item)
        await db_manager.db.orders.insert_one(order_doc)
    except Exception:
        for item in reserved:
            await db_manager.db.products.update_one(
                {"product_id": item["product_id"]},
                {"$inc": {"stock": item["quantity"]}},
            )
        raise
    order_doc.pop("_id", None)

    user_name = current_user.get("name", "Valued Customer")
    asyncio.create_task(
        asyncio.to_thread(send_order_confirmation_email, current_user["email"], user_name, order_doc)
    )

    await db_manager.db.carts.update_one(
        {"user_id": current_user["user_id"]},
        {"$set": {"items": []}}
    )

    logger.info(f"Order created: {order_id} by user {current_user['user_id']}")
    return {"order": order_doc}

async def submit_utr_endpoint(
    data: UTRSubmitRequest,
    current_user: dict = Depends(get_current_user)
):
    """Submit UTR for payment verification."""
    order = await db_manager.db.orders.find_one(
        {"order_id": data.order_id, "user_id": current_user["user_id"]},
        {"_id": 0}
    )

    if not order:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    if order["status"] not in ("awaiting_payment", "payment_failed"):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Order is not awaiting payment"
        )

    utr = data.utr.strip().upper()
    duplicate = await db_manager.db.orders.find_one(
        {"payment_ref": utr, "order_id": {"$ne": data.order_id}}, {"_id": 1}
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="This UTR has already been submitted")

    result = await db_manager.db.orders.update_one(
        {"order_id": data.order_id, "user_id": current_user["user_id"], "status": {"$in": ["awaiting_payment", "payment_failed"]}},
        {"$set": {"payment_ref": utr, "status": "awaiting_verification", "utr_submitted_at": now_iso(), "updated_at": now_iso()}}
    )
    if result.modified_count != 1:
        raise HTTPException(status_code=409, detail="Order payment status changed. Please refresh and try again.")

    logger.info(f"UTR submitted for order {data.order_id}")
    return {"ok": True, "order_id": data.order_id, "status": "awaiting_verification"}

async def list_user_orders_endpoint(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
):
    """List user's orders."""
    cursor = db_manager.db.orders.find(
        {"user_id": current_user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit)

    orders = await cursor.to_list(length=limit)
    total = await db_manager.db.orders.count_documents({"user_id": current_user["user_id"]})

    return {
        "items": orders,
        "total": total,
        "limit": limit,
        "skip": skip,
    }

async def get_user_order_endpoint(
    order_id: str = PathParam(..., regex=r'^ord_[a-f0-9]{12}$'),
    current_user: dict = Depends(get_current_user)
):
    """Get single order by ID."""
    order = await db_manager.db.orders.find_one(
        {"order_id": order_id, "user_id": current_user["user_id"]},
        {"_id": 0}
    )

    if not order:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    return order

async def upi_info_endpoint():
    """Get UPI payment information."""
    return {
        "upi_id": Settings.MERCHANT_UPI_ID,
        "merchant_name": Settings.MERCHANT_NAME,
    }

# ============================================================================
# API ROUTES - ADMIN ORDERS
# ============================================================================

async def admin_list_orders_endpoint(
    admin: dict = Depends(get_current_admin_user),
    status_filter: Optional[str] = Query(None, max_length=50),
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0),
):
    """List all orders with filters (admin only)."""
    query = {}
    if status_filter:
        query["status"] = status_filter

    cursor = db_manager.db.orders.find(query, {"_id": 0})
    cursor = cursor.sort("created_at", -1).skip(skip).limit(limit)
    orders = await cursor.to_list(length=limit)
    total = await db_manager.db.orders.count_documents(query)

    return {
        "items": orders,
        "total": total,
        "limit": limit,
        "skip": skip,
    }

async def restore_order_stock_once(order: dict) -> None:
    """Restore reserved stock once for a cancelled/rejected order."""
    claim = await db_manager.db.orders.update_one(
        {"order_id": order["order_id"], "stock_restored_at": {"$exists": False}},
        {"$set": {"stock_restored_at": now_iso()}},
    )
    if claim.modified_count != 1:
        return
    try:
        for item in order.get("items", []):
            qty = int(item.get("quantity", 0))
            if qty > 0:
                await db_manager.db.products.update_one(
                    {"product_id": item.get("product_id")},
                    {"$inc": {"stock": qty}, "$set": {"updated_at": now_iso()}},
                )
    except Exception:
        await db_manager.db.orders.update_one(
            {"order_id": order["order_id"]},
            {"$unset": {"stock_restored_at": ""}},
        )
        raise


async def admin_update_order_status_endpoint(
    order_id: str = PathParam(..., regex=r'^ord_[a-f0-9]{12}$'),
    new_status: str = Form(..., alias="status"),
    admin: dict = Depends(get_current_admin_user)
):
    """Update fulfillment status using safe state transitions."""
    transitions = {
        "awaiting_payment": {"awaiting_verification", "payment_failed", "cancelled"},
        "awaiting_verification": {"confirmed", "payment_failed", "cancelled"},
        "payment_failed": {"awaiting_payment", "awaiting_verification", "cancelled"},
        "confirmed": {"shipped", "cancelled"},
        "shipped": {"delivered"},
        "delivered": set(),
        "cancelled": set(),
    }
    if new_status not in transitions:
        raise HTTPException(status_code=400, detail="Invalid order status")

    order = await db_manager.db.orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    current = order.get("status")
    if new_status != current and new_status not in transitions.get(current, set()):
        raise HTTPException(status_code=409, detail=f"Cannot change order from {current} to {new_status}")

    update = {"status": new_status, "updated_at": now_iso()}
    if new_status == "confirmed" and not order.get("paid_at"):
        update["paid_at"] = now_iso()
    if new_status == "shipped":
        update["shipped_at"] = now_iso()
    if new_status == "delivered":
        update["delivered_at"] = now_iso()
    if new_status == "cancelled":
        await restore_order_stock_once(order)
        update["cancelled_at"] = now_iso()
        update["cancelled_by"] = admin["user_id"]

    await db_manager.db.orders.update_one({"order_id": order_id}, {"$set": update})

    if new_status == "delivered":
        user = await db_manager.db.users.find_one({"user_id": order["user_id"]}, {"_id": 0})
        asyncio.create_task(asyncio.to_thread(
            send_delivery_email, order["user_email"],
            user.get("name", "Valued Customer") if user else "Valued Customer",
            {**order, **update},
        ))

    logger.info("Admin %s changed order %s: %s -> %s", admin["user_id"], order_id, current, new_status)
    return {"ok": True, "status": new_status}

async def admin_verify_payment_endpoint(
    order_id: str = PathParam(..., regex=r'^ord_[a-f0-9]{12}$'),
    data: PaymentVerification = None,
    admin: dict = Depends(get_current_admin_user)
):
    """Verify or reject payment (admin only)."""
    if data is None:
        raise HTTPException(status_code=422, detail="Verification action is required")
    order = await db_manager.db.orders.find_one({"order_id": order_id}, {"_id": 0})

    if not order:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    if order.get("status") != "awaiting_verification":
        raise HTTPException(status_code=400, detail="Order is not awaiting payment verification")

    update_data = {"updated_at": now_iso()}

    if data.action == "verify":
        update_data["status"] = "confirmed"
        update_data["paid_at"] = now_iso()
        update_data["verified_by"] = admin["user_id"]
    else:
        update_data["status"] = "payment_failed"
        update_data["rejected_by"] = admin["user_id"]
        await restore_order_stock_once(order)

    if data.notes:
        update_data["payment_notes"] = data.notes

    await db_manager.db.orders.update_one(
        {"order_id": order_id},
        {"$set": update_data}
    )

    logger.info(f"Admin {admin['user_id']} {data.action}ed payment for order {order_id}")
    return {"ok": True, "status": update_data["status"]}

async def admin_delete_order_endpoint(
    order_id: str = PathParam(..., regex=r'^ord_[a-f0-9]{12}$'),
    admin: dict = Depends(get_current_admin_user)
):
    """Delete an order (admin only)."""
    result = await db_manager.db.orders.delete_one({"order_id": order_id})

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    logger.info(f"Admin {admin['user_id']} deleted order {order_id}")
    return {"ok": True}

# ============================================================================
# API ROUTES - ADMIN STATS
# ============================================================================

async def admin_stats_endpoint(admin: dict = Depends(get_current_admin_user)):
    """Get admin dashboard statistics."""
    total_products = await db_manager.db.products.count_documents({})
    active_products = await db_manager.db.products.count_documents({"status": "active"})
    out_of_stock = await db_manager.db.products.count_documents({"status": "out_of_stock"})
    discontinued = await db_manager.db.products.count_documents({"status": "discontinued"})

    total_orders = await db_manager.db.orders.count_documents({})
    awaiting_verification = await db_manager.db.orders.count_documents({"status": "awaiting_verification"})

    revenue_pipeline = [
        {"$match": {"status": {"$in": ["confirmed", "shipped", "delivered"]}}},
        {"$group": {
            "_id": None,
            "total": {"$sum": "$total"},
            "bv": {"$sum": "$total_bv"},
            "cc": {"$sum": "$total_cc"}
        }}
    ]
    revenue_doc = await db_manager.db.orders.aggregate(revenue_pipeline).to_list(1)
    revenue = revenue_doc[0] if revenue_doc else {"total": 0, "bv": 0, "cc": 0}

    total_users = await db_manager.db.users.count_documents({})

    return {
        "products": {
            "total": total_products,
            "active": active_products,
            "out_of_stock": out_of_stock,
            "discontinued": discontinued,
        },
        "orders": {
            "total": total_orders,
            "awaiting_verification": awaiting_verification,
        },
        "revenue": {
            "total": revenue.get("total", 0),
            "bv": revenue.get("bv", 0),
            "cc": revenue.get("cc", 0),
        },
        "users": {
            "total": total_users,
        },
    }

# ============================================================================
# API ROUTES - ANALYTICS
# ============================================================================

async def track_visit_endpoint(data: VisitTrack, request: Request):
    """Track page visit."""
    await db_manager.db.analytics_visits.insert_one({
        "session_id": data.session_id,
        "page": data.page,
        "referrer": data.referrer,
        "device": data.device,
        "browser": data.browser,
        "os": data.os,
        "screen": data.screen,
        "ip": get_client_ip(request),
        "utm_source": data.utm_source,
        "utm_medium": data.utm_medium,
        "utm_campaign": data.utm_campaign,
        "utm_content": data.utm_content,
        "timestamp": now_iso(),
    })
    return {"ok": True}

async def track_click_endpoint(data: ClickTrack, request: Request):
    """Track element click."""
    await db_manager.db.analytics_clicks.insert_one({
        "session_id": data.session_id,
        "element": data.element,
        "page": data.page,
        "label": data.label,
        "timestamp": now_iso(),
    })
    return {"ok": True}

async def admin_get_analytics_endpoint(admin: dict = Depends(get_current_admin_user)):
    """Get analytics data (admin only)."""
    total_visits = await db_manager.db.analytics_visits.count_documents({})
    unique_visitors = len(await db_manager.db.analytics_visits.distinct("session_id"))

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_visits = await db_manager.db.analytics_visits.count_documents(
        {"timestamp": {"$regex": f"^{today}"}}
    )

    page_pipeline = [
        {"$group": {"_id": "$page", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    top_pages = [
        {"page": d["_id"], "count": d["count"]}
        async for d in db_manager.db.analytics_visits.aggregate(page_pipeline)
    ]

    daily = []
    for i in range(6, -1, -1):
        day = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
        count = await db_manager.db.analytics_visits.count_documents(
            {"timestamp": {"$regex": f"^{day}"}}
        )
        daily.append({"date": day, "visits": count})

    click_pipeline = [
        {"$group": {
            "_id": {"element": "$element", "label": "$label", "page": "$page"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 15},
    ]
    top_clicks = [
        {
            "element": d["_id"]["element"],
            "label": d["_id"]["label"],
            "page": d["_id"]["page"],
            "count": d["count"]
        }
        async for d in db_manager.db.analytics_clicks.aggregate(click_pipeline)
    ]

    return {
        "total_visits": total_visits,
        "unique_visitors": unique_visitors,
        "today_visits": today_visits,
        "top_pages": top_pages,
        "daily_visits": daily,
        "top_clicks": top_clicks,
    }

# ============================================================================
# API ROUTES - HEALTH
# ============================================================================

async def health_check_endpoint():
    """Health check endpoint."""
    try:
        await db_manager.db.command("ping")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    return {
        "status": "ok",
        "service": Settings.APP_NAME,
        "version": Settings.APP_VERSION,
        "environment": Settings.ENVIRONMENT,
        "timestamp": now_iso(),
        "database": db_status,
    }

async def readiness_check_endpoint():
    """
    Readiness endpoint, distinct from /health.
    /health = process is up. /ready = process is up AND dependencies (DB) are
    reachable, so it can safely receive traffic behind a load balancer.
    """
    try:
        await db_manager.db.command("ping")
        return {"status": "ready"}
    except Exception as e:
        return JSONResponse(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "reason": str(e)}
        )

async def metrics_endpoint():
    """Minimal public metrics; detailed business counts are admin-only."""
    return {"status": "ok", "service": Settings.APP_NAME, "version": Settings.APP_VERSION, "timestamp": now_iso()}

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info(f"Starting {Settings.APP_NAME} v{Settings.APP_VERSION}")
    await db_manager.connect()
    await seed_initial_data()
    logger.info("Application started successfully")

    yield

    logger.info("Shutting down application...")
    await db_manager.close()
    logger.info("Application shutdown complete")

def _mongo_safe(value):
    """
    Recursively converts values that json.dumps can't handle on its own —
    bson ObjectId and datetime — into JSON-safe equivalents.
    """
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _mongo_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_mongo_safe(v) for v in value]
    return value


class SafeJSONResponse(JSONResponse):
    """Default response class for the app — see _mongo_safe() above."""
    def render(self, content: Any) -> bytes:
        return super().render(_mongo_safe(content))


app = FastAPI(
    title=Settings.APP_NAME,
    version=Settings.APP_VERSION,
    description="E-commerce backend for ShopVerse FBO",
    docs_url="/docs" if Settings.DEBUG else None,
    redoc_url="/redoc" if Settings.DEBUG else None,
    openapi_url="/openapi.json" if Settings.DEBUG else None,
    lifespan=lifespan,
    default_response_class=SafeJSONResponse,
)

# ============================================================================
# MIDDLEWARE SETUP
# ============================================================================
#
# IMPORTANT — middleware order:
# Starlette wraps middleware so that the FIRST one added via add_middleware()
# ends up OUTERMOST (it sees the request first and the response last); the
# LAST one added ends up innermost, right next to routing/exception handling.
#
# CORS must therefore be added FIRST, not last. If TrustedHostMiddleware (or
# anything else) runs outside of CORSMiddleware, any response it generates
# directly (e.g. its 400 for an untrusted Host header) never passes through
# CORSMiddleware and will be reported by the browser as a CORS failure even
# though the real cause is something else entirely. This exact ordering bug
# is a likely contributor to the "blocked by CORS policy" symptom paired
# with a 500 response.

app.add_middleware(
    CORSMiddleware,
    allow_origins=Settings.CORS_ORIGINS,
    allow_origin_regex=r"https://(?:shopbyfbo|shopbyfbo-repo)(?:-[a-z0-9-]+)?\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "X-Request-ID",
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
    ],
    expose_headers=[
        "X-Request-ID",
        "Content-Disposition",
    ],
    max_age=86400,
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,*.vercel.app,*.onrender.com").split(",") if h.strip()]
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(RequestLoggingMiddleware)

# ============================================================================
# SEED DATA
# ============================================================================

async def seed_initial_data():
    """Seed initial data if database is empty."""
    existing_admin = await db_manager.db.users.find_one(
        {"email": Settings.ADMIN_EMAIL.lower()}
    )

    if not existing_admin:
        admin_doc = {
            "user_id": generate_id("user"),
            "email": Settings.ADMIN_EMAIL.lower(),
            "name": "FBO Admin",
            "password_hash": password_hasher.hash(Settings.ADMIN_PASSWORD),
            "role": "admin",
            "auth_provider": "password",
            "created_at": now_iso(),
        }
        await db_manager.db.users.insert_one(admin_doc)
        logger.info(f"Admin user created: {Settings.ADMIN_EMAIL}")
    else:
        if not password_hasher.verify(
            Settings.ADMIN_PASSWORD,
            existing_admin.get("password_hash", "")
        ):
            await db_manager.db.users.update_one(
                {"email": Settings.ADMIN_EMAIL.lower()},
                {"$set": {"password_hash": password_hasher.hash(Settings.ADMIN_PASSWORD)}}
            )
            logger.info(f"Admin password updated: {Settings.ADMIN_EMAIL}")

    product_count = await db_manager.db.products.count_documents({})

    if product_count == 0:
        sample_products = [
            {
                "name": "Forever Aloe Vera Gel",
                "category": "Aloe Drinks",
                "description": "Pure inner leaf aloe vera gel to support digestion and overall wellness. 1 Litre bottle.",
                "mrp": 1480.0,
                "price": 1480.0,
                "bv": 14.8,
                "cc": 0.099,
                "stock": 50,
                "status": "active",
                "images": ["https://images.unsplash.com/photo-1765357285820-7f4f17fdcce9?w=400&auto=format&fit=crop"],
                "featured": True,
                "sku": "FLP-015",
            },
            {
                "name": "Forever Aloe Berry Nectar",
                "category": "Aloe Drinks",
                "description": "Refreshing blend of aloe vera, apple and cranberry for urinary tract health.",
                "mrp": 1552.0,
                "price": 1552.0,
                "bv": 15.5,
                "cc": 0.103,
                "stock": 35,
                "status": "active",
                "images": ["https://images.unsplash.com/photo-1622484212850-eb596d769edc?w=400&auto=format&fit=crop"],
                "featured": True,
                "sku": "FLP-034",
            },
            {
                "name": "Forever Bee Honey",
                "category": "Bee Products",
                "description": "Premium raw honey, naturally sweet and pure. 500g jar.",
                "mrp": 1100.0,
                "price": 1100.0,
                "bv": 11.0,
                "cc": 0.073,
                "stock": 40,
                "status": "active",
                "images": ["https://images.unsplash.com/photo-1587049352846-4a222e784d38?w=400&auto=format&fit=crop"],
                "featured": True,
                "sku": "FLP-207",
            },
            {
                "name": "Forever Bee Propolis",
                "category": "Bee Products",
                "description": "Natural immune support from bee propolis. 60 tablets.",
                "mrp": 2800.0,
                "price": 2800.0,
                "bv": 28.0,
                "cc": 0.187,
                "stock": 22,
                "status": "active",
                "images": ["https://images.unsplash.com/photo-1472476443507-c7a5948772fc?w=400&auto=format&fit=crop"],
                "featured": False,
                "sku": "FLP-027",
            },
            {
                "name": "Aloe Lips Stick",
                "category": "Personal Care",
                "description": "Aloe & jojoba enriched lip balm for soft lips anywhere, anytime.",
                "mrp": 395.0,
                "price": 395.0,
                "bv": 3.9,
                "cc": 0.026,
                "stock": 120,
                "status": "active",
                "images": ["https://images.unsplash.com/photo-1586495777744-4413f21062fa?w=400&auto=format&fit=crop"],
                "featured": True,
                "sku": "FLP-022",
            },
        ]

        now = now_iso()
        for product in sample_products:
            product["product_id"] = generate_id("prod")
            product["created_at"] = now
            product["updated_at"] = now
            await db_manager.db.products.insert_one(product)

        logger.info(f"Seeded {len(sample_products)} sample products")

# ============================================================================
# AI CHATBOT - GEMINI
# ============================================================================

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: List[ChatMessage] = Field(default_factory=list, max_items=20)


class ChatResponse(BaseModel):
    reply: str
    products: List[dict] = Field(default_factory=list)
    order: Optional[dict] = None
    support_url: Optional[str] = None


CHAT_SYSTEM_PROMPT = """You are ShopVerse Assistant for the ShopVerse wellness store.
You help customers with product information, prices, stock availability, ordering,
payment, shipping, and order status using only the store context supplied to you.
Do not pretend to be Forever Living corporate staff. Do not invent products, prices,
stock, delivery times, payment details, or policies. Do not diagnose, treat, cure,
or promise medical results. For health questions, provide only general product
information from the supplied catalog and suggest speaking with a qualified
professional for medical advice. If information is unavailable, say so clearly and
offer human support. Keep answers friendly, concise, and useful.
"""

_chat_rate_buckets: Dict[str, List[float]] = {}
_chat_rate_lock = asyncio.Lock()


async def check_chat_rate_limit(key: str) -> None:
    now = time.time()
    async with _chat_rate_lock:
        recent = [
            ts for ts in _chat_rate_buckets.get(key, [])
            if now - ts < Settings.CHAT_RATE_WINDOW_SECONDS
        ]
        if len(recent) >= Settings.CHAT_RATE_LIMIT:
            raise HTTPException(
                status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many chat requests. Please try again shortly.",
            )
        recent.append(now)
        _chat_rate_buckets[key] = recent


def _chat_product_context(product: dict) -> dict:
    return {
        "product_id": product.get("product_id"),
        "name": product.get("name"),
        "category": product.get("category"),
        "description": product.get("description", ""),
        "price": product.get("price", 0),
        "mrp": product.get("mrp", 0),
        "bv": product.get("bv", 0),
        "cc": product.get("cc", 0),
        "stock": product.get("stock", 0),
        "status": product.get("status", "active"),
        "images": product.get("images", [])[:1],
        "featured": product.get("featured", False),
    }


async def chat_endpoint(request: Request, data: ChatRequest):
    """Answer customer questions using Gemini plus live MongoDB store context."""
    if not Settings.GEMINI_API_KEY or genai is None:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI assistant is not configured yet. Please use human support.",
        )

    current_user = await get_optional_user(request, None)
    rate_key = f"user:{current_user['user_id']}" if current_user else f"ip:{get_client_ip(request)}"
    await check_chat_rate_limit(rate_key)

    message = data.message.strip()
    words = [w for w in re.findall(r"[a-zA-Z0-9]+", message.lower()) if len(w) >= 3]

    product_query = {"status": {"$in": ["active", "out_of_stock"]}}
    if words:
        pattern = "|".join(re.escape(w) for w in words[:8])
        product_query["$or"] = [
            {"name": {"$regex": pattern, "$options": "i"}},
            {"category": {"$regex": pattern, "$options": "i"}},
            {"description": {"$regex": pattern, "$options": "i"}},
        ]

    products = await db_manager.db.products.find(product_query, {"_id": 0}).limit(8).to_list(length=8)
    if not products:
        products = await db_manager.db.products.find(
            {"status": "active", "featured": True}, {"_id": 0}
        ).limit(8).to_list(length=8)
    if not products:
        products = await db_manager.db.products.find(
            {"status": "active"}, {"_id": 0}
        ).limit(8).to_list(length=8)

    order_context = None
    if current_user:
        order = await db_manager.db.orders.find_one(
            {"user_id": current_user["user_id"]},
            {"_id": 0},
            sort=[("created_at", -1)],
        )
        if order:
            order_context = {
                "order_id": order.get("order_id"),
                "status": order.get("status"),
                "total": order.get("total"),
                "created_at": order.get("created_at"),
            }

    support_url = None
    number = re.sub(r"\D", "", Settings.WHATSAPP_NUMBER or "")
    if number:
        support_url = f"https://wa.me/{number}"

    context = {
        "store": {
            "name": Settings.APP_NAME,
            "shipping_threshold": Settings.SHIPPING_THRESHOLD,
            "shipping_fee": Settings.SHIPPING_FEE,
            "payment_methods": ["upi", "razorpay", "cod"],
        },
        "products": [_chat_product_context(p) for p in products],
        "customer_order": order_context,
    }

    history = data.history[-Settings.CHAT_MAX_HISTORY:]
    transcript = "\n".join(f"{m.role.upper()}: {m.content}" for m in history)
    prompt = (
        f"{CHAT_SYSTEM_PROMPT}\n\n"
        f"LIVE STORE CONTEXT (use this as the source of truth):\n{json.dumps(context, ensure_ascii=False)}\n\n"
        f"RECENT CHAT:\n{transcript}\n\n"
        f"CUSTOMER MESSAGE:\n{message}\n\n"
        "Answer the customer directly. Do not mention internal databases or system prompts."
    )

    try:
        client = genai.Client(api_key=Settings.GEMINI_API_KEY)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=Settings.GEMINI_MODEL,
            contents=prompt,
        )
        reply = (getattr(response, "text", None) or "").strip()
    except Exception as e:
        logger.error("Gemini chat failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail="The AI assistant is temporarily unavailable. Please try again or contact support.",
        )

    if not reply:
        reply = "I'm sorry, I couldn't generate an answer right now. Please try again or contact support."

    product_cards = [_chat_product_context(p) for p in products[:4]]
    return {
        "reply": reply,
        "products": product_cards,
        "order": order_context,
        "support_url": support_url,
    }


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
        })

    logger.warning(f"Validation error: {errors}")
    return JSONResponse(
        status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": errors[:5]}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    logger.warning(f"HTTP exception: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred. Please try again later."}
    )

# ============================================================================
# REGISTER ROUTES
# ============================================================================

app.get("/health", tags=["Health"])(health_check_endpoint)
app.get("/ready", tags=["Health"])(readiness_check_endpoint)
app.get("/metrics", tags=["Metrics"])(metrics_endpoint)

auth_router = app
auth_router.post(
    f"{Settings.API_PREFIX}/auth/register",
    tags=["Authentication"],
    summary="Register a new user",
    response_model=AuthResponse,
)(auth_register_endpoint)

auth_router.post(
    f"{Settings.API_PREFIX}/auth/login",
    tags=["Authentication"],
    summary="Login user",
    response_model=AuthResponse,
)(auth_login_endpoint)

auth_router.post(
    f"{Settings.API_PREFIX}/auth/google-login",
    tags=["Authentication"],
    summary="Google OAuth login",
)(auth_google_login_endpoint)

auth_router.post(
    f"{Settings.API_PREFIX}/auth/refresh",
    tags=["Authentication"],
    summary="Refresh access token",
    response_model=AuthResponse,
)(auth_refresh_endpoint)

auth_router.post(
    f"{Settings.API_PREFIX}/auth/logout",
    tags=["Authentication"],
    summary="Logout user",
)(auth_logout_endpoint)

auth_router.get(
    f"{Settings.API_PREFIX}/auth/me",
    tags=["Authentication"],
    summary="Get current user info",
    response_model=UserResponse,
)(auth_me_endpoint)

app.get(
    f"{Settings.API_PREFIX}/products",
    tags=["Products"],
    summary="List products with filters",
)(list_products_endpoint)

app.get(
    f"{Settings.API_PREFIX}/products/categories",
    tags=["Products"],
    summary="List product categories",
)(list_categories_endpoint)

app.get(
    f"{Settings.API_PREFIX}/products/{{product_id}}",
    tags=["Products"],
    summary="Get product by ID",
)(get_product_endpoint)

app.post(
    f"{Settings.API_PREFIX}/admin/products",
    tags=["Admin", "Products"],
    summary="Create product (admin only)",
    dependencies=[Depends(get_current_admin_user)],
)(admin_create_product_endpoint)

app.put(
    f"{Settings.API_PREFIX}/admin/products/{{product_id}}",
    tags=["Admin", "Products"],
    summary="Update product (admin only)",
    dependencies=[Depends(get_current_admin_user)],
)(admin_update_product_endpoint)

app.delete(
    f"{Settings.API_PREFIX}/admin/products/{{product_id}}",
    tags=["Admin", "Products"],
    summary="Delete product (admin only)",
    dependencies=[Depends(get_current_admin_user)],
)(admin_delete_product_endpoint)

app.patch(
    f"{Settings.API_PREFIX}/admin/products/{{product_id}}/status",
    tags=["Admin", "Products"],
    summary="Update product status (admin only)",
    dependencies=[Depends(get_current_admin_user)],
)(admin_update_product_status_endpoint)

app.get(
    f"{Settings.API_PREFIX}/admin/products",
    tags=["Admin", "Products"],
    summary="List all products (admin only)",
    dependencies=[Depends(get_current_admin_user)],
)(admin_list_all_products_endpoint)

app.post(
    f"{Settings.API_PREFIX}/admin/upload",
    tags=["Admin", "Uploads"],
    summary="Upload image (admin only)",
    dependencies=[Depends(get_current_admin_user)],
)(upload_image_endpoint)

app.get(
    f"{Settings.API_PREFIX}/cart",
    tags=["Cart"],
    summary="Get user cart",
    dependencies=[Depends(get_current_user)],
)(get_cart_endpoint)

app.post(
    f"{Settings.API_PREFIX}/cart/add",
    tags=["Cart"],
    summary="Add item to cart",
    dependencies=[Depends(get_current_user)],
)(add_to_cart_endpoint)

app.post(
    f"{Settings.API_PREFIX}/cart/update",
    tags=["Cart"],
    summary="Update cart item",
    dependencies=[Depends(get_current_user)],
)(update_cart_item_endpoint)

app.post(
    f"{Settings.API_PREFIX}/cart/remove",
    tags=["Cart"],
    summary="Remove item from cart",
    dependencies=[Depends(get_current_user)],
)(remove_cart_item_endpoint)

app.post(
    f"{Settings.API_PREFIX}/cart/clear",
    tags=["Cart"],
    summary="Clear cart",
    dependencies=[Depends(get_current_user)],
)(clear_cart_endpoint)

app.post(
    f"{Settings.API_PREFIX}/checkout",
    tags=["Orders"],
    summary="Checkout and create order",
    dependencies=[Depends(get_current_user)],
)(checkout_endpoint)

app.post(
    f"{Settings.API_PREFIX}/checkout/submit-utr",
    tags=["Orders"],
    summary="Submit UTR for payment",
    dependencies=[Depends(get_current_user)],
)(submit_utr_endpoint)

app.get(
    f"{Settings.API_PREFIX}/orders",
    tags=["Orders"],
    summary="List user orders",
    dependencies=[Depends(get_current_user)],
)(list_user_orders_endpoint)

app.get(
    f"{Settings.API_PREFIX}/orders/{{order_id}}",
    tags=["Orders"],
    summary="Get order by ID",
    dependencies=[Depends(get_current_user)],
)(get_user_order_endpoint)

app.get(
    f"{Settings.API_PREFIX}/payment/upi-info",
    tags=["Payment"],
    summary="Get UPI payment info",
)(upi_info_endpoint)

app.get(
    f"{Settings.API_PREFIX}/admin/orders",
    tags=["Admin", "Orders"],
    summary="List all orders (admin only)",
    dependencies=[Depends(get_current_admin_user)],
)(admin_list_orders_endpoint)

app.patch(
    f"{Settings.API_PREFIX}/admin/orders/{{order_id}}/status",
    tags=["Admin", "Orders"],
    summary="Update order status (admin only)",
    dependencies=[Depends(get_current_admin_user)],
)(admin_update_order_status_endpoint)

app.patch(
    f"{Settings.API_PREFIX}/admin/orders/{{order_id}}/verify-payment",
    tags=["Admin", "Orders"],
    summary="Verify or reject payment (admin only)",
    dependencies=[Depends(get_current_admin_user)],
)(admin_verify_payment_endpoint)

app.delete(
    f"{Settings.API_PREFIX}/admin/orders/{{order_id}}",
    tags=["Admin", "Orders"],
    summary="Delete order (admin only)",
    dependencies=[Depends(get_current_admin_user)],
)(admin_delete_order_endpoint)

app.get(
    f"{Settings.API_PREFIX}/admin/stats",
    tags=["Admin", "Statistics"],
    summary="Get admin statistics",
    dependencies=[Depends(get_current_admin_user)],
)(admin_stats_endpoint)

app.post(
    f"{Settings.API_PREFIX}/chat",
    tags=["Chat"],
    summary="AI customer assistant",
)(chat_endpoint)

app.post(
    f"{Settings.API_PREFIX}/analytics/visit",
    tags=["Analytics"],
    summary="Track page visit",
)(track_visit_endpoint)

app.post(
    f"{Settings.API_PREFIX}/analytics/click",
    tags=["Analytics"],
    summary="Track element click",
)(track_click_endpoint)

app.get(
    f"{Settings.API_PREFIX}/admin/analytics",
    tags=["Admin", "Analytics"],
    summary="Get analytics data (admin only)",
    dependencies=[Depends(get_current_admin_user)],
)(admin_get_analytics_endpoint)

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "service": Settings.APP_NAME,
        "version": Settings.APP_VERSION,
        "status": "healthy",
        "docs": f"{Settings.RENDER_URL}/docs" if Settings.DEBUG else None,
    }

# ============================================================================
# STATIC FILES
# ============================================================================

upload_path = Path("uploads")
upload_path.mkdir(exist_ok=True)

app.mount(
    "/uploads",
    StaticFiles(directory="uploads"),
    name="uploads",
)

# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host=Settings.HOST,
        port=Settings.PORT,
        reload=Settings.DEBUG,
        log_level=Settings.DEBUG and "debug" or "info",
    )
