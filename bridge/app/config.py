from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    xwiki_url: str = "http://xwiki:8080"
    xwiki_admin_user: str = "admin"
    xwiki_admin_password: str = ""
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"
    ollama_embed_model: str = "nomic-embed-text"
    github_user: str = ""
    github_token: str = ""
    anythingllm_url: str = "http://anythingllm:3001"
    anythingllm_api_key: str = ""

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
