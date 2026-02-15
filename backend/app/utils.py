"""
Shared utility functions for the PharmaPersonaSim backend.

This module consolidates common functionality used across multiple engine modules
to reduce code duplication and ensure consistent behavior.
"""

import os
import threading
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI, AsyncOpenAI

# Load environment variables from the backend folder
backend_dir = os.path.dirname(os.path.dirname(__file__))
env_path = os.path.join(backend_dir, '.env')
load_dotenv(env_path)

# Shared constants
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5.2")

# Cache for the OpenAI client. The SDK requires an API key during
# instantiation, so we create the client lazily to avoid raising an exception
# when the key is absent (for example in local development or during unit tests).
_openai_client: Optional[OpenAI] = None
_async_openai_client: Optional[AsyncOpenAI] = None
_client_lock = threading.Lock()
_async_client_lock = threading.Lock()


def get_openai_client() -> Optional[OpenAI]:
    """Return a configured OpenAI client if an API key is available.
    
    This function is thread-safe and caches the client instance for reuse.
    Returns None if OPENAI_API_KEY is not set in the environment.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    global _openai_client
    with _client_lock:
        if _openai_client is None:
            _openai_client = OpenAI(api_key=api_key)

    return _openai_client

def get_async_openai_client() -> Optional[AsyncOpenAI]:
    """Return a configured AsyncOpenAI client if an API key is available.
    
    This function is thread-safe and caches the client instance for reuse.
    Returns None if OPENAI_API_KEY is not set in the environment.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    global _async_openai_client
    with _async_client_lock:
        if _async_openai_client is None:
            _async_openai_client = AsyncOpenAI(api_key=api_key)

    return _async_openai_client
