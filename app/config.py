from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "wechat-rebate-bot"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    log_level: str = "INFO"

    wechat_token: str = "replace_me"
    wechat_aes_key: str = ""
    wechat_app_id: str = ""
    wechat_app_secret: str = ""

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    database_url: str = "sqlite:///./data.db"
    rebate_rate: float = 0.7

    jd_affiliate_app_key: str = ""
    jd_affiliate_app_secret: str = ""
    jd_affiliate_access_token: str = ""
    jd_affiliate_api_url: str = "https://api.jd.com/routerjson"
    jd_affiliate_method: str = "jd.union.open.goods.jingfen.query"
    jd_affiliate_elite_id: int = 1
    pdd_client_id: str = ""
    pdd_client_secret: str = ""
    taobao_app_key: str = ""
    taobao_app_secret: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
