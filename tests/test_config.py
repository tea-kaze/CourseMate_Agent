"""LangSmith 可观测性配置的行为测试。"""

from __future__ import annotations

import os

import pytest

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
        LANGSMITH_API_KEY=api_key,
        LANGSMITH_TRACING=tracing,
        LANGSMITH_PROJECT=project,
    )


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
