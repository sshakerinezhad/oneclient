"""Unit tests for llm.bedrock module (BedrockClient)."""
import json
import pytest
from botocore.exceptions import ClientError
from llm.bedrock import BedrockClient


def _make_cfg():
    return {
        "bedrock": {"region": "us-east-1", "aws_profile": ""},
        "agent": {"thinking_budget": 1024},
    }


class FakeBedrockClient:
    """Mock boto3 bedrock-runtime client — no real AWS calls."""

    def __init__(self, responses):
        self._responses = list(responses)
        self._call_count = 0

    def converse(self, **kwargs):
        self._call_count += 1
        return self._responses.pop(0)

    def converse_stream(self, **kwargs):
        self._call_count += 1
        return self._responses.pop(0)


# ---------------------------------------------------------------------------
# Buffered converse()
# ---------------------------------------------------------------------------


def test_converse_parses_text_response():
    client = BedrockClient.__new__(BedrockClient)
    client._thinking_budget = 1024
    client._client = FakeBedrockClient([{
        "output": {"message": {
            "role": "assistant",
            "content": [{"text": "Hello world"}],
        }},
        "stopReason": "end_turn",
    }])
    result = client.converse(
        "model-id", "system prompt",
        [{"role": "user", "content": [{"text": "Hi"}]}],
    )
    assert result["text"] == "Hello world"
    assert result["tool_uses"] == []
    assert result["stop_reason"] == "end_turn"
    assert len(result["messages"]) == 2


def test_converse_parses_tool_use_response():
    client = BedrockClient.__new__(BedrockClient)
    client._thinking_budget = 1024
    client._client = FakeBedrockClient([{
        "output": {"message": {
            "role": "assistant",
            "content": [{"toolUse": {
                "toolUseId": "t1",
                "name": "query_data",
                "input": {"request": "find companies"},
            }}],
        }},
        "stopReason": "tool_use",
    }])
    result = client.converse(
        "model-id", "sys",
        [{"role": "user", "content": [{"text": "q"}]}],
    )
    assert len(result["tool_uses"]) == 1
    assert result["tool_uses"][0]["id"] == "t1"
    assert result["tool_uses"][0]["name"] == "query_data"
    assert result["tool_uses"][0]["input"] == {"request": "find companies"}
    assert result["stop_reason"] == "tool_use"
    assert result["text"] == ""


def test_converse_messages_updated():
    """converse() appends the assistant message to the returned messages list."""
    client = BedrockClient.__new__(BedrockClient)
    client._thinking_budget = 1024
    assistant_msg = {"role": "assistant", "content": [{"text": "Hi"}]}
    client._client = FakeBedrockClient([{
        "output": {"message": assistant_msg},
        "stopReason": "end_turn",
    }])
    user_messages = [{"role": "user", "content": [{"text": "Hello"}]}]
    result = client.converse("model-id", "sys", user_messages)
    assert result["messages"] == user_messages + [assistant_msg]


def test_converse_multiple_text_blocks_concatenated():
    """Multiple text blocks in one response are joined into a single string."""
    client = BedrockClient.__new__(BedrockClient)
    client._thinking_budget = 1024
    client._client = FakeBedrockClient([{
        "output": {"message": {
            "role": "assistant",
            "content": [{"text": "Foo"}, {"text": " Bar"}],
        }},
        "stopReason": "end_turn",
    }])
    result = client.converse("model-id", "sys", [])
    assert result["text"] == "Foo Bar"


# ---------------------------------------------------------------------------
# Streaming converse_stream()
# ---------------------------------------------------------------------------


def test_converse_stream_calls_on_event():
    events = [
        {"contentBlockStart": {"contentBlockIndex": 0, "start": {"text": ""}}},
        {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "Hello "}}},
        {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "world"}}},
        {"contentBlockStop": {"contentBlockIndex": 0}},
        {"messageStop": {"stopReason": "end_turn"}},
    ]
    client = BedrockClient.__new__(BedrockClient)
    client._thinking_budget = 1024
    client._client = FakeBedrockClient([{"stream": iter(events)}])

    collected = []

    result = client.converse_stream(
        "model-id", "sys",
        [{"role": "user", "content": [{"text": "q"}]}],
        on_event=lambda k, t: collected.append((k, t)),
    )
    assert result["text"] == "Hello world"
    assert ("text", "Hello ") in collected
    assert ("text", "world") in collected
    assert result["stop_reason"] == "end_turn"


def test_converse_stream_tool_use():
    """Tool-use JSON input is accumulated across deltas and parsed on block stop."""
    tool_input = {"query": "find clients", "limit": 10}
    tool_input_str = json.dumps(tool_input)
    half = len(tool_input_str) // 2
    events = [
        {"contentBlockStart": {"contentBlockIndex": 0, "start": {
            "toolUse": {"toolUseId": "tu-1", "name": "search_graph"},
        }}},
        {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {
            "toolUse": {"input": tool_input_str[:half]},
        }}},
        {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {
            "toolUse": {"input": tool_input_str[half:]},
        }}},
        {"contentBlockStop": {"contentBlockIndex": 0}},
        {"messageStop": {"stopReason": "tool_use"}},
    ]
    client = BedrockClient.__new__(BedrockClient)
    client._thinking_budget = 1024
    client._client = FakeBedrockClient([{"stream": iter(events)}])

    tool_events = []
    result = client.converse_stream(
        "model-id", "sys",
        [{"role": "user", "content": [{"text": "q"}]}],
        on_event=lambda k, t: tool_events.append((k, t)),
    )
    assert result["stop_reason"] == "tool_use"
    assert len(result["tool_uses"]) == 1
    tu = result["tool_uses"][0]
    assert tu["id"] == "tu-1"
    assert tu["name"] == "search_graph"
    assert tu["input"] == tool_input
    assert ("tool", "search_graph") in tool_events


def test_converse_stream_thinking():
    """Reasoning deltas fire on_event('thinking', ...) without polluting result text."""
    events = [
        {"contentBlockStart": {"contentBlockIndex": 0, "start": {}}},
        {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {
            "reasoningContent": {"text": "Let me think..."},
        }}},
        {"contentBlockStop": {"contentBlockIndex": 0}},
        {"contentBlockStart": {"contentBlockIndex": 1, "start": {"text": ""}}},
        {"contentBlockDelta": {"contentBlockIndex": 1, "delta": {"text": "Answer"}}},
        {"contentBlockStop": {"contentBlockIndex": 1}},
        {"messageStop": {"stopReason": "end_turn"}},
    ]
    client = BedrockClient.__new__(BedrockClient)
    client._thinking_budget = 1024
    client._client = FakeBedrockClient([{"stream": iter(events)}])

    collected = []
    result = client.converse_stream(
        "model-id", "sys",
        [{"role": "user", "content": [{"text": "q"}]}],
        on_event=lambda k, t: collected.append((k, t)),
    )
    assert ("thinking", "Let me think...") in collected
    assert ("text", "Answer") in collected
    assert result["text"] == "Answer"


def test_converse_stream_no_on_event():
    """converse_stream with on_event=None still returns correct aggregated result."""
    events = [
        {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "Silent"}}},
        {"messageStop": {"stopReason": "end_turn"}},
    ]
    client = BedrockClient.__new__(BedrockClient)
    client._thinking_budget = 1024
    client._client = FakeBedrockClient([{"stream": iter(events)}])
    result = client.converse_stream(
        "model-id", "sys",
        [{"role": "user", "content": [{"text": "q"}]}],
    )
    assert result["text"] == "Silent"
    assert result["tool_uses"] == []


def test_converse_stream_messages_updated():
    """converse_stream appends a reconstructed assistant message to messages."""
    events = [
        {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "Hi"}}},
        {"messageStop": {"stopReason": "end_turn"}},
    ]
    client = BedrockClient.__new__(BedrockClient)
    client._thinking_budget = 1024
    client._client = FakeBedrockClient([{"stream": iter(events)}])
    user_messages = [{"role": "user", "content": [{"text": "Hello"}]}]
    result = client.converse_stream("model-id", "sys", user_messages)
    assert len(result["messages"]) == 2
    assert result["messages"][-1]["role"] == "assistant"


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------


def test_converse_retry_on_throttle(monkeypatch):
    """converse() retries on ThrottlingException up to MAX_RETRIES times."""
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)

    error_resp = {"Error": {"Code": "ThrottlingException", "Message": "throttled"}}
    success_resp = {
        "output": {"message": {"role": "assistant", "content": [{"text": "ok"}]}},
        "stopReason": "end_turn",
    }

    class ThrottlingClient:
        def __init__(self):
            self._calls = 0

        def converse(self, **kwargs):
            self._calls += 1
            if self._calls < 3:
                raise ClientError(error_resp, "Converse")
            return success_resp

    client = BedrockClient.__new__(BedrockClient)
    client._thinking_budget = 1024
    client._client = ThrottlingClient()
    result = client.converse(
        "model-id", "sys",
        [{"role": "user", "content": [{"text": "q"}]}],
    )
    assert result["text"] == "ok"
    assert client._client._calls == 3


def test_converse_raises_on_non_retryable_error():
    """converse() does not retry on unrelated ClientErrors."""
    error_resp = {"Error": {"Code": "ValidationException", "Message": "bad request"}}

    class BadClient:
        def converse(self, **kwargs):
            raise ClientError(error_resp, "Converse")

    client = BedrockClient.__new__(BedrockClient)
    client._thinking_budget = 1024
    client._client = BadClient()
    with pytest.raises(ClientError) as exc_info:
        client.converse("model-id", "sys", [])
    assert exc_info.value.response["Error"]["Code"] == "ValidationException"
