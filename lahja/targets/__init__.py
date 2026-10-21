from lahja.config import GROQ_BASE_URL, ConfigError, ModelSpec, Settings
from lahja.targets.base import Message, ModelCallError, ModelClient
from lahja.targets.openai_compat import OpenAICompatClient


def make_client(spec: ModelSpec, settings: Settings) -> ModelClient:
    if spec.provider == "groq":
        if not settings.groq_api_key:
            raise ConfigError("GROQ_API_KEY is not set (copy .env.example to .env and fill it in)")
        return OpenAICompatClient(name=spec.key, base_url=GROQ_BASE_URL, model=spec.model, api_key=settings.groq_api_key)
    return OpenAICompatClient(name=spec.key, base_url=settings.ollama_base_url, model=spec.model)


__all__ = ["Message", "ModelCallError", "ModelClient", "OpenAICompatClient", "make_client"]
