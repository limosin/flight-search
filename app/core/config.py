"""
Configuration settings for the application
Uses Memgraph graph database for all flight search operations
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings"""
    
    # App settings
    APP_NAME: str = "Flight Search API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    MEMGRAPH_HOST: str = os.getenv('MEMGRAPH_HOST', 'localhost')
    MEMGRAPH_PORT: int = int(os.getenv('MEMGRAPH_PORT', '7687'))
    MEMGRAPH_USER: str = os.getenv('MEMGRAPH_USER', '')
    MEMGRAPH_PASSWORD: str = os.getenv('MEMGRAPH_PASSWORD', '')
    
    DATABASE_URL: str = os.getenv('DATABASE_URL', 'sqlite:///flight_search.db')
    
    # API settings
    API_V1_PREFIX: str = "/v1"
    
    # Search settings
    DEFAULT_MAX_HOPS: int = 2
    DEFAULT_MAX_RESULTS: int = 50
    MAX_RESULTS_LIMIT: int = 100
    
    # Connection time rules (in minutes)
    MINIMUM_CONNECTION_TIME_DOMESTIC: int = 45
    MINIMUM_CONNECTION_TIME_INTERNATIONAL: int = 90
    MAXIMUM_LAYOVER_TIME: int = 720  # 12 hours
    
    # CORS
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:3001",  # Updated for Memgraph Lab on 3000
        "http://localhost:8000",
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
