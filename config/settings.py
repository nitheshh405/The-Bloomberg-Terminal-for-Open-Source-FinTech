"""
Central configuration management for the FinTech OSINT Platform.
All settings are loaded from environment variables with sensible defaults.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class GitHubSettings(BaseSettings):
    token: str = Field("", env="GITHUB_TOKEN")
    api_url: str = "https://api.github.com"
    rate_limit_pause: int = 60  # seconds to wait on rate limit
    max_repos_per_run: int = 5000


class GitLabSettings(BaseSettings):
    token: str = Field("", env="GITLAB_TOKEN")
    api_url: str = "https://gitlab.com/api/v4"
    max_repos_per_run: int = 2000


class BitbucketSettings(BaseSettings):
    username: str = Field("", env="BITBUCKET_USERNAME")
    app_password: str = Field("", env="BITBUCKET_APP_PASSWORD")
    api_url: str = "https://api.bitbucket.org/2.0"


class Neo4jSettings(BaseSettings):
    uri: str = Field("bolt://localhost:7687", env="NEO4J_URI")
    username: str = Field("neo4j", env="NEO4J_USERNAME")
    password: str = Field("password", env="NEO4J_PASSWORD")
    database: str = Field("fintech", env="NEO4J_DATABASE")
    max_connection_pool: int = 50


class ElasticsearchSettings(BaseSettings):
    hosts: List[str] = Field(["http://localhost:9200"], env="ES_HOSTS")
    index_prefix: str = "fintech-osint"
    username: Optional[str] = Field(None, env="ES_USERNAME")
    password: Optional[str] = Field(None, env="ES_PASSWORD")


class MLSettings(BaseSettings):
    model_path: str = "models/"
    classification_model: str = "distilbert-base-uncased-finetuned-fintech"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    disruption_model_path: str = "models/disruption_predictor.pkl"
    batch_size: int = 32
    device: str = "cpu"  # "cuda" for GPU


class AnthropicSettings(BaseSettings):
    api_key: str = Field("", env="ANTHROPIC_API_KEY")
    model: str = "claude-opus-4-6"
    max_tokens: int = 4096


class RegulatorySettings(BaseSettings):
    federal_register_api: str = "https://www.federalregister.gov/api/v1"
    sec_edgar_api: str = "https://data.sec.gov"
    cfpb_api: str = "https://api.consumerfinance.gov"
    update_interval_hours: int = 6


class Settings(BaseSettings):
    # App
    app_name: str = "FinTech OSINT Platform"
    app_version: str = "1.0.0"
    debug: bool = Field(False, env="DEBUG")
    log_level: str = Field("INFO", env="LOG_LEVEL")

    # API
    api_host: str = Field("0.0.0.0", env="API_HOST")
    api_port: int = Field(8000, env="API_PORT")
    api_secret_key: str = Field("change-me-in-production", env="API_SECRET_KEY")
    allowed_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Sub-settings
    github: GitHubSettings = GitHubSettings()
    gitlab: GitLabSettings = GitLabSettings()
    bitbucket: BitbucketSettings = BitbucketSettings()
    neo4j: Neo4jSettings = Neo4jSettings()
    elasticsearch: ElasticsearchSettings = ElasticsearchSettings()
    ml: MLSettings = MLSettings()
    anthropic: AnthropicSettings = AnthropicSettings()
    regulatory: RegulatorySettings = RegulatorySettings()

    # Pipeline
    weekly_run_day: str = "monday"
    weekly_run_hour: int = 6
    max_concurrent_agents: int = 4
    pipeline_timeout_seconds: int = 3600

    # Scoring weights
    innovation_velocity_weight: float = 0.20
    ecosystem_influence_weight: float = 0.18
    tech_maturity_weight: float = 0.15
    sector_relevance_weight: float = 0.17
    adoption_potential_weight: float = 0.15
    disruption_potential_weight: float = 0.15

    @field_validator("weekly_run_day")
    @classmethod
    def validate_day(cls, v: str) -> str:
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        if v.lower() not in days:
            raise ValueError(f"Invalid day: {v}")
        return v.lower()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
