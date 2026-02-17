"""
Shared utility functions for the PharmaPersonaSim backend.

This module consolidates common functionality used across multiple engine modules
to reduce code duplication and ensure consistent behavior.
"""

import os
import threading
from typing import Optional, Union
from dotenv import load_dotenv
from openai import OpenAI, AsyncOpenAI, AzureOpenAI, AsyncAzureOpenAI

# Load environment variables from the backend folder
backend_dir = os.path.dirname(os.path.dirname(__file__))
env_path = os.path.join(backend_dir, '.env')
load_dotenv(env_path)

# Shared constants
MODEL_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME") or os.getenv("OPENAI_MODEL", "gpt-5.2")

# Cache for the OpenAI client.
_openai_client: Optional[Union[OpenAI, AzureOpenAI]] = None
_async_openai_client: Optional[Union[AsyncOpenAI, AsyncAzureOpenAI]] = None
_client_lock = threading.Lock()
_async_client_lock = threading.Lock()


def get_openai_client() -> Optional[Union[OpenAI, AzureOpenAI]]:
    """Return a configured OpenAI or AzureOpenAI client.
    
    This function is thread-safe and caches the client instance for reuse.
    """
    global _openai_client
    with _client_lock:
        if _openai_client is None:
            # Check for Azure configuration first
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_key = os.getenv("AZURE_OPENAI_API_KEY")
            azure_version = os.getenv("AZURE_OPENAI_API_VERSION")
            
            if azure_endpoint and azure_key:
                _openai_client = AzureOpenAI(
                    api_key=azure_key,
                    api_version=azure_version,
                    azure_endpoint=azure_endpoint
                )
            else:
                # Fallback to standard OpenAI
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    _openai_client = OpenAI(api_key=api_key)

    return _openai_client

def get_async_openai_client() -> Optional[Union[AsyncOpenAI, AsyncAzureOpenAI]]:
    """Return a configured AsyncOpenAI or AsyncAzureOpenAI client.
    
    This function is thread-safe and caches the client instance for reuse.
    """
    global _async_openai_client
    with _async_client_lock:
        if _async_openai_client is None:
             # Check for Azure configuration first
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_key = os.getenv("AZURE_OPENAI_API_KEY")
            azure_version = os.getenv("AZURE_OPENAI_API_VERSION")
            
            if azure_endpoint and azure_key:
                _async_openai_client = AsyncAzureOpenAI(
                    api_key=azure_key,
                    api_version=azure_version,
                    azure_endpoint=azure_endpoint
                )
            else:
                # Fallback to standard OpenAI
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    _async_openai_client = AsyncOpenAI(api_key=api_key)

    return _async_openai_client
