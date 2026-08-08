import os
import time
import random
from typing import List, Dict, Any
from groq import Groq

def get_groq_client() -> Groq:
    """
    Retrieves the Groq API client, validating that the API key is configured.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY environment variable is not set. "
            "Please configure it to enable LLM-based discrepancy analysis."
        )
    return Groq(api_key=api_key)

def call_llm_with_backoff(
    messages: List[Dict[str, str]], 
    model: str = "llama-3.3-70b-versatile", 
    max_retries: int = 5
) -> str:
    """
    Calls the Groq chat completions API with exponential backoff and jitter.
    
    Args:
        messages: List of message dictionaries representing conversation history.
        model: LLM model to target (defaults to Llama 3.3 70B).
        max_retries: Maximum number of retry attempts on rate limit or connection errors.
    """
    client = get_groq_client()
    base_delay = 1.0
    
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                messages=messages,
                model=model,
                temperature=0.1,  # Low temperature for deterministic classification
            )
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("Groq returned an empty response.")
            return content
        except Exception as e:
            err_msg = str(e)
            is_rate_limit = "429" in err_msg or "rate_limit" in err_msg.lower()
            
            # If we have retries remaining, sleep and retry
            if attempt < max_retries - 1:
                # Exponential backoff: base_delay * 2^attempt + jitter
                sleep_time = base_delay * (2 ** attempt) + random.uniform(0.1, 0.5)
                print(f"[Groq LLM] Attempt {attempt + 1} failed. Retrying in {sleep_time:.2f} seconds. Error: {e}")
                time.sleep(sleep_time)
            else:
                print(f"[Groq LLM] Max retries ({max_retries}) reached. Raising error.")
                raise e
                
    raise RuntimeError("Max retries exceeded for LLM completion.")
