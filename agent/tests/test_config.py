import pytest

from prompt_shop_live.config import DEFAULT_MODEL, LiveSettings
from prompt_shop_live.runtime import Runtime


def test_unset_settings_keep_existing_defaults(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_VOICE", raising=False)
    assert LiveSettings.from_env() == LiveSettings(DEFAULT_MODEL, None)
    monkeypatch.setenv("GEMINI_VOICE", "")
    assert LiveSettings.from_env().voice is None


@pytest.mark.parametrize("name,value", [
    ("GEMINI_MODEL", ""),
    ("GEMINI_MODEL", " "),
    ("GEMINI_MODEL", "https://example.test/model"),
    ("GEMINI_MODEL", "models/../../model"),
    ("GEMINI_MODEL", "secret-like-invalid\nvalue"),
    ("GEMINI_MODEL", "a" * 129),
    ("GEMINI_VOICE", " "),
    ("GEMINI_VOICE", "Aoede\nInjected"),
    ("GEMINI_VOICE", "https://example.test/voice"),
    ("GEMINI_VOICE", "a" * 65),
])
def test_bad_settings_fail_before_runtime_starts_without_echoing_value(monkeypatch, name, value):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_VOICE", raising=False)
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError) as error:
        Runtime(None)
    assert name in str(error.value)
    if value.strip():
        assert value not in str(error.value)
