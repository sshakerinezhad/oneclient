"""Unit tests for llm.config module."""
import pytest
import tempfile
from pathlib import Path
from llm.config import load_config


def test_load_config_file_not_found():
    """Test that load_config raises FileNotFoundError when file is missing."""
    with pytest.raises(FileNotFoundError) as exc_info:
        load_config("nonexistent.toml")
    assert "nonexistent.toml missing" in str(exc_info.value)
    assert "config.example.toml" in str(exc_info.value)


def test_load_config_valid_toml():
    """Test that load_config successfully loads a valid TOML file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_config.toml"
        config_path.write_text(
            """
[bedrock]
aws_profile = "test-profile"
region = "us-west-2"
query_model_id = "anthropic.claude-3-sonnet"
"""
        )

        config = load_config(str(config_path))

        assert config["bedrock"]["aws_profile"] == "test-profile"
        assert config["bedrock"]["region"] == "us-west-2"
        assert config["bedrock"]["query_model_id"] == "anthropic.claude-3-sonnet"


def test_load_config_default_path():
    """Test that load_config loads config.toml from default path when it exists."""
    config = load_config()
    assert "bedrock" in config
    assert "region" in config["bedrock"]
