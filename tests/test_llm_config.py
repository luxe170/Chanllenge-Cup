from __future__ import annotations

from pathlib import Path

from src.llm_client import ChatCompletionsClient, load_llm_config, llm_config_status, write_llm_config


def test_load_llm_config_reads_project_dotenv(tmp_path: Path, monkeypatch) -> None:
    for name in ("LLM_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "LLM_MODEL", "LLM_BASE_URL", "LLM_RESUME_ENABLED"):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "LLM_API_KEY=test-key",
                "LLM_BASE_URL=https://api.deepseek.com",
                "LLM_MODEL=deepseek-v4-flash",
                "LLM_RESUME_ENABLED=true",
            ]
        ),
        encoding="utf-8",
    )

    config = load_llm_config(tmp_path)

    assert config.api_key == "test-key"
    assert config.base_url == "https://api.deepseek.com"
    assert config.model == "deepseek-v4-flash"
    assert config.resume_enabled is True


def test_environment_overrides_dotenv(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("LLM_API_KEY=file-key\nLLM_MODEL=file-model\n", encoding="utf-8")
    monkeypatch.setenv("LLM_API_KEY", "env-key")
    monkeypatch.setenv("LLM_MODEL", "env-model")

    config = load_llm_config(tmp_path)

    assert config.api_key == "env-key"
    assert config.model == "env-model"


def test_llm_config_status_does_not_expose_secret(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    (tmp_path / ".env").write_text("LLM_API_KEY=secret-value\n", encoding="utf-8")

    status = llm_config_status(tmp_path)

    assert status["configured"] is True
    assert "secret-value" not in str(status)


def test_chat_client_from_env_uses_unified_config(tmp_path: Path, monkeypatch) -> None:
    import src.llm_client as llm_client

    monkeypatch.setattr(llm_client, "project_root", lambda: tmp_path)
    (tmp_path / ".env").write_text(
        "LLM_API_KEY=test-key\nLLM_MODEL=deepseek-v4-flash\nLLM_BASE_URL=https://api.deepseek.com\n",
        encoding="utf-8",
    )

    client = ChatCompletionsClient.from_env()

    assert client.api_key == "test-key"
    assert client.model == "deepseek-v4-flash"
    assert client.base_url == "https://api.deepseek.com"


def test_write_llm_config_writes_gitignored_dotenv_shape(tmp_path: Path) -> None:
    config = write_llm_config(
        "test-key",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        resume_enabled=True,
        root=tmp_path,
    )

    stored = (tmp_path / ".env").read_text(encoding="utf-8")
    assert config.configured is True
    assert "LLM_API_KEY=test-key" in stored
    assert "LLM_MODEL=deepseek-v4-flash" in stored
    assert "LLM_RESUME_ENABLED=true" in stored
