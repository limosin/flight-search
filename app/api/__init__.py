"""
API routes package
"""

from fastapi import APIRouter
from .search import router as search_router

api_router = APIRouter()
api_router.include_router(search_router)

__all__ = ['api_router']
