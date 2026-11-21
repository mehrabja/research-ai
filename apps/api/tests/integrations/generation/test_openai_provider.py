from __future__ import annotations

import httpx
import pytest

from app.integrations.generation.base import (
    GenerationAuthenticationError,
    GenerationInvalidRequestError,
    GenerationInvalidResponseError,
    GenerationProviderUnavailableError,
    GenerationRateLimitError,
)
from app.integrations.generation.openai import OpenAIGenerationProvider


def _patch_post(monkeypatch, responder):  # type: ignore[no-untyped-def]
    import app.integrations.generation.openai as mod
    monkeypatch.setattr(mod.httpx, "post", lambda *a, **k: responder())


def _resp(*, status_code=200, body=None, headers=None) -> httpx.Response:
    return httpx.Response(
        status_code=status_code, json=body, headers=headers or {},
        request=httpx.Request("POST", "http://test/"),
    )


def _ok(text: str) -> dict:
    return {
        "choices": [{"message": {"content": text}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                  "total_tokens": 15},
    }


def test_success(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _patch_post(monkeypatch, lambda: _resp(
        body=_ok("Hello [E1]"), headers={"x-request-id": "req-1"},
    ))
    p = OpenAIGenerationProvider(model="gpt-4o-mini", api_key="k")
    r = p.generate(system_prompt="s", user_prompt="u",
                   temperature=0.2, max_output_tokens=100)
    assert r.text == "Hello [E1]"
    assert r.input_tokens == 10
    assert r.request_id == "req-1"


def test_429_maps_to_rate_limit(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _patch_post(monkeypatch, lambda: _resp(status_code=429))
    p = OpenAIGenerationProvider(model="m", api_key="k", max_retries=0)
    with pytest.raises(GenerationRateLimitError):
        p.generate(system_prompt="s", user_prompt="u",
                   temperature=0.2, max_output_tokens=100)


def test_401_maps_to_auth(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _patch_post(monkeypatch, lambda: _resp(status_code=401))
    p = OpenAIGenerationProvider(model="m", api_key="k", max_retries=0)
    with pytest.raises(GenerationAuthenticationError):
        p.generate(system_prompt="s", user_prompt="u",
                   temperature=0.2, max_output_tokens=100)


def test_400_maps_to_invalid_request(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _patch_post(monkeypatch, lambda: _resp(status_code=400))
    p = OpenAIGenerationProvider(model="m", api_key="k", max_retries=0)
    with pytest.raises(GenerationInvalidRequestError):
        p.generate(system_prompt="s", user_prompt="u",
                   temperature=0.2, max_output_tokens=100)


def test_5xx_maps_to_unavailable(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _patch_post(monkeypatch, lambda: _resp(status_code=503))
    p = OpenAIGenerationProvider(model="m", api_key="k", max_retries=0)
    with pytest.raises(GenerationProviderUnavailableError):
        p.generate(system_prompt="s", user_prompt="u",
                   temperature=0.2, max_output_tokens=100)


def test_malformed_response(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _patch_post(monkeypatch, lambda: _resp(body={"choices": []}))
    p = OpenAIGenerationProvider(model="m", api_key="k")
    with pytest.raises(GenerationInvalidResponseError):
        p.generate(system_prompt="s", user_prompt="u",
                   temperature=0.2, max_output_tokens=100)


class _FakeStreamingResponse:
    def __init__(self, lines: list[str], *, status_code: int = 200) -> None:
        self.status_code = status_code
        self.headers = {"x-request-id": "stream-req-1"}
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def iter_lines(self):
        return iter(self._lines)


def test_generate_stream_emits_deltas_and_normalizes_usage(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import app.integrations.generation.openai as mod

    captured: dict[str, object] = {}
    lines = [
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        "",
        'data: {"choices":[{"delta":{"content":" world"}}]}',
        'data: {"choices":[],"usage":{"prompt_tokens":20,"completion_tokens":4,"total_tokens":24}}',
        "data: [DONE]",
    ]

    def fake_stream(method, url, **kwargs):  # type: ignore[no-untyped-def]
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = kwargs.get("json")
        return _FakeStreamingResponse(lines)

    monkeypatch.setattr(mod.httpx, "stream", fake_stream)
    provider = OpenAIGenerationProvider(model="gpt-4o-mini", api_key="k")
    deltas: list[str] = []
    result = provider.generate_stream(
        system_prompt="system",
        user_prompt="user",
        temperature=0.2,
        max_output_tokens=100,
        on_delta=deltas.append,
    )

    assert captured["method"] == "POST"
    assert captured["url"].endswith("/chat/completions")
    assert captured["payload"]["stream"] is True  # type: ignore[index]
    assert captured["payload"]["stream_options"] == {"include_usage": True}  # type: ignore[index]
    assert deltas == ["Hello", " world"]
    assert result.text == "Hello world"
    assert result.input_tokens == 20
    assert result.output_tokens == 4
    assert result.total_tokens == 24
    assert result.request_id == "stream-req-1"


def test_generate_stream_maps_rate_limit_without_retrying(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import app.integrations.generation.openai as mod

    monkeypatch.setattr(
        mod.httpx,
        "stream",
        lambda *args, **kwargs: _FakeStreamingResponse([], status_code=429),
    )
    provider = OpenAIGenerationProvider(model="m", api_key="k", max_retries=0)
    with pytest.raises(GenerationRateLimitError):
        provider.generate_stream(
            system_prompt="s",
            user_prompt="u",
            temperature=0.2,
            max_output_tokens=100,
            on_delta=lambda _delta: None,
        )
