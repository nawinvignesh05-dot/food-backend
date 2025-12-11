# Example wrapper if you want to use OpenAI instead.
# Keep as template; not required to run.
import os
from app.core.config import settings
# from openai import OpenAI  # if using official SDK

def parse_query_with_openai(prompt: str) -> dict:
    raise NotImplementedError("Fill in with real OpenAI call using settings.OPENAI_API_KEY")
