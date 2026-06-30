"""Unit tests for llm.bedrock module (BedrockClient via invoke_model)."""
import io
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

    def invoke_model(self, **kwargs):
        self._call_count += 1
        resp_body = self._responses.pop(0)
        return {"body": io.BytesIO(json.dumps(resp_body).encode())}

    def invoke_model_with_response_stream(self, **kwargs):
        self._call_count += 1
        events = self._responses.pop(0)
        return {"body": events}


def _make_client(responses):
    """Create a BedrockClient with a fake boto3 backend."""
    client = BedrockClient.__new__(BedrockClient)
    client._thinking_budget = 1024
    client._client = FakeBedrockClient(responses)
    return client


# ---------------------------------------------------------------------------
# Buffered converse()
# ---------------------------------------------------------------------------


def test_converse_parses_text_response():
    client = _make_client([{
        "content": [{"type": "text", "text": "Hello world"}],
        "stop_reason": "end_turn",
    }])
    result = client.converse(
        "model-id", "system prompt",
        [{"role": "user", "content": "Hi"}],
    )
    assert result["text"] == "Hello world"
    assert result["tool_uses"] == []
    assert result["stop_reason"] == "end_turn"
    assert len(result["messages"]) == 2


def test_converse_parses_tool_use_response():
    client = _make_client([{
        "content": [{
            "type": "tool_use",
            "id": "t1",
            "name": "query_data",
            "input": {"request": "find companies"},
        }],
        "stop_reason": "tool_use",
    }])
    result = client.converse(
        "model-id", "sys",
        [{"role": "user", "content": "q"}],
    )
    assert len(result["tool_uses"]) == 1
    assert result["tool_uses"][0]["id"] == "t1"
    assert result["tool_uses"][0]["name"] == "query_data"
    assert result["tool_uses"][0]["input"] == {"request": "find companies"}
    assert result["stop_reason"] == "tool_use"
    assert result["text"] == ""


def test_converse_messages_updated():
    client = _make_client([{
        "content": [{"type": "text", "text": "Hi"}],
        "stop_reason": "end_turn",
    }])
    user_messages = [{"role": "user", "content": "Hello"}]
    result = client.converse("model-id", "sys", user_messages)
    assert len(result["messages"]) == 2
    assert result["messages"][-1]["role"] == "assistant"
    assert result["messages"][-1]["content"][0]["text"] == "Hi"


def test_converse_multiple_text_blocks_concatenated():
    client = _make_client([{
        "content": [
            {"type": "text", "text": "Foo"},
            {"type": "text", "text": " Bar"},
        ],
        "stop_reason": "end_turn",
    }])
    result = client.converse("model-id", "sys", [])
    assert result["text"] == "Foo Bar"


# ---------------------------------------------------------------------------
# Streaming converse_stream()
# ---------------------------------------------------------------------------


def _stream_events(events):
    """Wrap event dicts as fake Bedrock invoke_model_with_response_stream chunks."""
    for ev in events:
        yield {"chunk": {"bytes": json.dumps(ev).encode()}}


def test_converse_stream_calls_on_event():
    events = list(_stream_events([
        {"type": "content_block_start", "index": 0,
         "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "text_delta", "text": "Hello "}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "text_delta", "text": "world"}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {}},
    ]))
    client = _make_client([events])

    collected = []
    result = client.converse_stream(
        "model-id", "sys",
        [{"role": "user", "content": "q"}],
        on_event=lambda k, t: collected.append((k, t)),
    )
    assert result["text"] == "Hello world"
    assert ("text", "Hello ") in collected
    assert ("text", "world") in collected
    assert result["stop_reason"] == "end_turn"


def test_converse_stream_tool_use():
    tool_input = {"query": "find clients", "limit": 10}
    tool_input_str = json.dumps(tool_input)
    half = len(tool_input_str) // 2

    events = list(_stream_events([
        {"type": "content_block_start", "index": 0,
         "content_block": {"type": "tool_use", "id": "tu-1", "name": "search_graph"}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "input_json_delta", "partial_json": tool_input_str[:half]}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "input_json_delta", "partial_json": tool_input_str[half:]}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {}},
    ]))
    client = _make_client([events])

    tool_events = []
    result = client.converse_stream(
        "model-id", "sys",
        [{"role": "user", "content": "q"}],
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
    events = list(_stream_events([
        {"type": "content_block_start", "index": 0,
         "content_block": {"type": "thinking"}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "thinking_delta", "thinking": "Let me think..."}},
        {"type": "content_block_stop", "index": 0},
        {"type": "content_block_start", "index": 1,
         "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 1,
         "delta": {"type": "text_delta", "text": "Answer"}},
        {"type": "content_block_stop", "index": 1},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {}},
    ]))
    client = _make_client([events])

    collected = []
    result = client.converse_stream(
        "model-id", "sys",
        [{"role": "user", "content": "q"}],
        on_event=lambda k, t: collected.append((k, t)),
    )
    assert ("thinking", "Let me think...") in collected
    assert ("text", "Answer") in collected
    assert result["text"] == "Answer"


def test_converse_stream_no_on_event():
    events = list(_stream_events([
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "text_delta", "text": "Silent"}},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {}},
    ]))
    client = _make_client([events])
    result = client.converse_stream(
        "model-id", "sys",
        [{"role": "user", "content": "q"}],
    )
    assert result["text"] == "Silent"
    assert result["tool_uses"] == []


def test_converse_stream_messages_updated():
    events = list(_stream_events([
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "text_delta", "text": "Hi"}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {}},
    ]))
    client = _make_client([events])
    user_messages = [{"role": "user", "content": "Hello"}]
    result = client.converse_stream("model-id", "sys", user_messages)
    assert len(result["messages"]) == 2
    assert result["messages"][-1]["role"] == "assistant"


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------


def test_converse_retry_on_throttle(monkeypatch):
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)

    error_resp = {"Error": {"Code": "ThrottlingException", "Message": "throttled"}}
    success_body = {
        "content": [{"type": "text", "text": "ok"}],
        "stop_reason": "end_turn",
    }

    class ThrottlingClient:
        def __init__(self):
            self._calls = 0

        def invoke_model(self, **kwargs):
            self._calls += 1
            if self._calls < 3:
                raise ClientError(error_resp, "InvokeModel")
            return {"body": io.BytesIO(json.dumps(success_body).encode())}

    client = BedrockClient.__new__(BedrockClient)
    client._thinking_budget = 1024
    client._client = ThrottlingClient()
    result = client.converse(
        "model-id", "sys",
        [{"role": "user", "content": "q"}],
    )
    assert result["text"] == "ok"
    assert client._client._calls == 3


def test_converse_raises_on_non_retryable_error():
    error_resp = {"Error": {"Code": "ValidationException", "Message": "bad request"}}

    class BadClient:
        def invoke_model(self, **kwargs):
            raise ClientError(error_resp, "InvokeModel")

    client = BedrockClient.__new__(BedrockClient)
    client._thinking_budget = 1024
    client._client = BadClient()
    with pytest.raises(ClientError) as exc_info:
        client.converse("model-id", "sys", [])
    assert exc_info.value.response["Error"]["Code"] == "ValidationException"
