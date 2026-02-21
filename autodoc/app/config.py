from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    xwiki_url: str = "http://xwiki:8080"
    xwiki_admin_user: str = "admin"
    xwiki_admin_password: str = ""
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"
    docker_hosts: str = ""
    scan_subnets: str = "192.168.1.0/24"
    scan_interval_hours: int = 24
    esxi_host: str = ""
    esxi_user: str = "root"
    esxi_ssh_key_path: str = "/keys/esxi_rsa"
    synology_host: str = ""
    synology_user: str = "root"
    synology_ssh_key_path: str = "/keys/synology_ed25519"

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
