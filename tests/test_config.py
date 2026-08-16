"""LangSmith 可观测性配置的行为测试。"""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from coursemate import config


_LANGSMITH_ENV_KEYS = (
    "LANGSMITH_TRACING",
    "LANGSMITH_API_KEY",
    "LANGSMITH_PROJECT",
    "LANGSMITH_ENDPOINT",
)


@pytest.fixture()
def clean_langsmith_env(monkeypatch: pytest.MonkeyPatch):
    for k in _LANGSMITH_ENV_KEYS:
        monkeypatch.delenv(k, raising=False)


def _settings(api_key="", tracing=False, project="coursemate"):
    return config.Settings(
        DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost/coursemate",
        MILVUS_URI="http://localhost:19530",
        LANGSMITH_API_KEY=api_key,
        LANGSMITH_TRACING=tracing,
        LANGSMITH_PROJECT=project,
    )


def test_settings_accepts_and_normalizes_supported_storage_urls():
    settings = config.Settings(
        DATABASE_URL="postgresql://postgres:postgres@localhost/coursemate",
        MILVUS_URI="https://milvus.example.com:19530",
    )

    assert settings.DATABASE_URL.startswith("postgresql+psycopg://")
    assert settings.MILVUS_URI == "https://milvus.example.com:19530"
    assert settings.MAX_UPLOAD_MB == 50


def test_settings_rejects_non_positive_upload_limit():
    with pytest.raises(ValidationError):
        config.Settings(
            DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost/coursemate",
            MILVUS_URI="http://localhost:19530",
            MAX_UPLOAD_MB=0,
        )


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite:///./data/coursemate.db",
        "mysql+pymysql://user:password@localhost/coursemate",
        "postgresql+psycopg2://postgres:postgres@localhost/coursemate",
    ],
)
def test_settings_rejects_unsupported_database_urls(database_url):
    with pytest.raises(ValidationError, match="PostgreSQL"):
        config.Settings(
            DATABASE_URL=database_url,
            MILVUS_URI="http://localhost:19530",
        )


@pytest.mark.parametrize(
    "milvus_uri",
    ["./data/milvus_lite.db", "file:///tmp/milvus.db", "localhost:19530", ""],
)
def test_settings_rejects_non_remote_milvus_uris(milvus_uri):
    with pytest.raises(ValidationError, match="MILVUS_URI"):
        config.Settings(
            DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost/coursemate",
            MILVUS_URI=milvus_uri,
        )


def test_settings_requires_database_and_milvus_configuration(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("MILVUS_URI", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        config.Settings(_env_file=None)

    missing_fields = {
        error["loc"][0]
        for error in exc_info.value.errors()
        if error["type"] == "missing"
    }
    assert missing_fields == {"DATABASE_URL", "MILVUS_URI"}


def test_apply_langsmith_env_enables_tracing(clean_langsmith_env):
    config._apply_langsmith_env(_settings(api_key="ls-key", tracing=True))
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "ls-key"
    assert os.environ["LANGSMITH_PROJECT"] == "coursemate"


def test_apply_langsmith_env_disabled_without_key(clean_langsmith_env):
    config._apply_langsmith_env(_settings(api_key="", tracing=True))
    assert "LANGSMITH_TRACING" not in os.environ


def test_apply_langsmith_env_disabled_without_tracing_flag(clean_langsmith_env):
    config._apply_langsmith_env(_settings(api_key="ls-key", tracing=False))
    assert "LANGSMITH_TRACING" not in os.environ
