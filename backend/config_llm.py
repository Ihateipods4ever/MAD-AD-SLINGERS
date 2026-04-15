import os
from crewai import LLM

def get_ollama_llm(model_name="llama3.2:1b"):
    """
    Configure CrewAI to use self-hosted Ollama instance
    """
    return LLM(
        model=f"ollama/{model_name}",
        base_url=os.getenv("OLLAMA_BASE_URL", "http://68.168.222.149:11434"),
        verbose=True
    )

def get_ollama_config():
    """
    Get Ollama configuration for use in agents
    """
    return {
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://68.168.222.149:11434"),
        "model": "llama3.2:1b",
        "verbose": True
    }
