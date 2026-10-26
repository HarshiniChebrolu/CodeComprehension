import os
import secrets
import logging
from pathlib import Path
from typing import Literal, Dict, Any
from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base workspace directory
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables cleanly via python-dotenv
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv()

logger = logging.getLogger("codecomprehension.config")


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Environment & Server
    FLASK_ENV: Literal["development", "production", "testing"] = "development"
    FLASK_DEBUG: bool = False
    HOST: str = "127.0.0.1"
    PORT: int = 5000

    # Secret Key Management
    SECRET_KEY: str = Field(default="")

    # Database
    DATABASE_PATH: str = str(BASE_DIR / "codecomprehension.db")

    # AI / LLM Configuration
    DEFAULT_AI_PROVIDER: Literal["offline", "gemini", "openai"] = "offline"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    AI_TIMEOUT_SECONDS: float = 10.0

    # Execution Sandbox
    EXECUTION_BACKEND: Literal["docker", "disabled", "local_dev_unsafe"] = "docker"
    EXECUTION_TIMEOUT: float = 5.0
    MAX_OUTPUT_CHARS: int = 10000

    # Language Registry
    SUPPORTED_LANGUAGES: Dict[str, Dict[str, Any]] = {
        "python": {
            "extension": "py",
            "docker_image": "python:3.10-slim-bullseye",
            "compile_command": None,
            "run_command": "python main.py",
            "compile_timeout": 5.0,
            "run_timeout": 5.0,
        },
        "javascript": {
            "extension": "js",
            "docker_image": "node:18-slim",
            "compile_command": None,
            "run_command": "node main.js",
            "compile_timeout": 5.0,
            "run_timeout": 5.0,
        },
        "java": {
            "extension": "java",
            "docker_image": "openjdk:17-jdk-slim",
            "compile_command": "javac Main.java",
            "run_command": "java Main",
            "compile_timeout": 10.0,
            "run_timeout": 5.0,
        },
        "c": {
            "extension": "c",
            "docker_image": "gcc:latest",
            "compile_command": "gcc main.c -o main",
            "run_command": "./main",
            "compile_timeout": 10.0,
            "run_timeout": 5.0,
        },
        "cpp": {
            "extension": "cpp",
            "docker_image": "gcc:latest",
            "compile_command": "g++ main.cpp -o main",
            "run_command": "./main",
            "compile_timeout": 10.0,
            "run_timeout": 5.0,
        },
    }

    LANGUAGE_ALIASES: Dict[str, str] = {
        "py": "python",
        "js": "javascript",
        "c++": "cpp",
    }

    # Request limits
    MAX_CODE_LENGTH: int = 50000
    MAX_STDIN_LENGTH: int = 10000 # Cap for stdin input
    MAX_CONTENT_LENGTH: int = 1048576  # 1 MB

    # Docker specific configurations
    DOCKER_CONTAINER_NAME_PREFIX: str = "codecomp_sandbox_"

    # Rate Limiting & Proxy
    TRUSTED_PROXIES: int = 0
    RATELIMIT_DEFAULT: str = "100 per minute"
    RATELIMIT_REVIEW: str = "20 per minute"
    RATELIMIT_EXECUTE: str = "15 per minute"

    @field_validator("PORT")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, received {v}")
        return v

    @field_validator("DATABASE_PATH")
    @classmethod
    def validate_database_path(cls, v: str) -> str:
        p = Path(v)
        if not p.is_absolute():
            p = (BASE_DIR / p).resolve()
        return str(p)

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str, info) -> str:
        flask_env = os.environ.get("FLASK_ENV", "development").lower()
        if info.data and "FLASK_ENV" in info.data:
            flask_env = str(info.data["FLASK_ENV"]).lower()

        insecure_placeholders = {
            "", "changeme", "secret", "secretkey", "1234567812345678",
            "development_secret_key", "password", "supersecretkey"
        }
        if flask_env == "production":
            clean_v = v.strip() if v else ""
            if (
                not clean_v
                or len(clean_v) < 16
                or clean_v.lower() in insecure_placeholders
                or any(p in clean_v.lower() for p in ("changeme", "placeholder", "12345678", "secretkey"))
            ):
                raise ValueError(
                    "CRITICAL SECURITY ERROR: In production mode, SECRET_KEY must be explicitly set "
                    "to a strong secret with at least 16 characters. Refusing to start with missing or weak key."
                )
        if not v:
            generated_key = secrets.token_hex(32)
            logger.warning(
                "WARNING: No SECRET_KEY found in environment. Generated ephemeral development secret. "
                "Set a permanent SECRET_KEY in .env for production."
            )
            return generated_key
        return v

    @field_validator("EXECUTION_BACKEND")
    @classmethod
    def validate_execution_backend(cls, v: str, info) -> str:
        flask_env = os.environ.get("FLASK_ENV", "development").lower()
        if info.data and "FLASK_ENV" in info.data:
            flask_env = str(info.data["FLASK_ENV"]).lower()

        if flask_env == "production" and v == "local_dev_unsafe":
            raise ValueError(
                "CRITICAL SECURITY ERROR: EXECUTION_BACKEND 'local_dev_unsafe' is strictly forbidden "
                "in production environments. Use 'docker' or 'disabled'."
            )
        return v


# Instantiate validated configuration singleton
try:
    settings = AppSettings()
except Exception as err:
    # Print clear, understandable error message instead of mysterious import crashes
    print(f"\n[CONFIGURATION ERROR] Failed to initialize CodeComprehension settings:\n  -> {err}\n")
    raise SystemExit(1) from err

# Backwards compatibility accessor object
class Config:
    SECRET_KEY = settings.SECRET_KEY
    DEBUG = settings.FLASK_DEBUG
    DATABASE_PATH = settings.DATABASE_PATH
    DEFAULT_AI_PROVIDER = settings.DEFAULT_AI_PROVIDER
    GEMINI_API_KEY = settings.GEMINI_API_KEY
    OPENAI_API_KEY = settings.OPENAI_API_KEY
    AI_TIMEOUT_SECONDS = settings.AI_TIMEOUT_SECONDS
    EXECUTION_BACKEND = settings.EXECUTION_BACKEND
    EXECUTION_TIMEOUT = settings.EXECUTION_TIMEOUT
    MAX_OUTPUT_CHARS = settings.MAX_OUTPUT_CHARS
    SUPPORTED_LANGUAGES = settings.SUPPORTED_LANGUAGES
    LANGUAGE_ALIASES = settings.LANGUAGE_ALIASES
    MAX_CODE_LENGTH = settings.MAX_CODE_LENGTH
    MAX_CONTENT_LENGTH = settings.MAX_CONTENT_LENGTH
    HOST = settings.HOST
    PORT = settings.PORT
    FLASK_ENV = settings.FLASK_ENV
    TRUSTED_PROXIES = settings.TRUSTED_PROXIES
    RATELIMIT_DEFAULT = settings.RATELIMIT_DEFAULT
    RATELIMIT_REVIEW = settings.RATELIMIT_REVIEW
    RATELIMIT_EXECUTE = settings.RATELIMIT_EXECUTE
