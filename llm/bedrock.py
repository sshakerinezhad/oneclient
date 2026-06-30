"""BedrockClient: thin wrapper around boto3 Bedrock invoke_model API.

Provides buffered (converse) and streaming (converse_stream) calls, both
returning a uniform dict with text, tool_uses, stop_reason, and messages.
Uses Anthropic Messages API format via invoke_model (not the Converse API).
Supports tool-use blocks and extended thinking.
"""
import json
import time

import boto3
from botocore.exceptions import ClientError

MAX_RETRIES = 3
ANTHROPIC_VERSION = "bedrock-2023-05-31"


class BedrockClient:
    def __init__(self, cfg: dict):
        bedrock_cfg = cfg["bedrock"]
        sess = boto3.Session(
            aws_access_key_id=bedrock_cfg.get("aws_access_key_id") or None,
            aws_secret_access_key=bedrock_cfg.get("aws_secret_access_key") or None,
            aws_session_token=bedrock_cfg.get("aws_session_token") or None,
            profile_name=bedrock_cfg.get("aws_profile") or None,
        )
        self._client = sess.client(
            "bedrock-runtime", region_name=bedrock_cfg["region"]
        )
        self._thinking_budget = cfg.get("agent", {}).get("thinking_budget", 2048)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def converse(
        self,
        model_id: str,
        system: str,
        messages: list,
        tools: list | None = None,
        thinking: bool = False,
        max_tokens: int = 4096,
    ) -> dict:
        """Buffered call via invoke_model with automatic retry."""
        body = self._build_body(system, messages, tools, thinking, max_tokens)
        raw = self._call_with_retry(
            self._client.invoke_model,
            {"modelId": model_id, "body": json.dumps(body),
             "contentType": "application/json", "accept": "application/json"},
        )
        resp = json.loads(raw["body"].read())
        return self._parse_response(resp, messages)

    def converse_stream(
        self,
        model_id: str,
        system: str,
        messages: list,
        tools: list | None = None,
        thinking: bool = False,
        max_tokens: int = 4096,
        on_event=None,
    ) -> dict:
        """Streaming call via invoke_model_with_response_stream.

        Iterates the event stream, fires on_event(kind, text) for each delta
        (kinds: 'text', 'thinking', 'tool'), then returns the same shape as
        converse().  on_event=None disables callbacks but still aggregates.
        """
        body = self._build_body(system, messages, tools, thinking, max_tokens)
        raw = self._call_with_retry(
            self._client.invoke_model_with_response_stream,
            {"modelId": model_id, "body": json.dumps(body),
             "contentType": "application/json", "accept": "application/json"},
        )
        return self._consume_stream(raw["body"], messages, on_event)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_body(self, system, messages, tools, thinking, max_tokens):
        body = {
            "anthropic_version": ANTHROPIC_VERSION,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
            "temperature": 0,
        }
        if tools:
            body["tools"] = tools
        if thinking:
            body["thinking"] = {
                "type": "enabled",
                "budget_tokens": self._thinking_budget,
            }
        return body

    def _call_with_retry(self, fn, kwargs):
        """Call fn(**kwargs), retrying on throttling/service-unavailable errors."""
        for attempt in range(MAX_RETRIES + 1):
            try:
                return fn(**kwargs)
            except ClientError as exc:
                code = exc.response["Error"]["Code"]
                if code in ("ThrottlingException", "ServiceUnavailableException"):
                    if attempt == MAX_RETRIES:
                        raise
                    time.sleep(2 ** attempt)
                else:
                    raise

    def _parse_response(self, resp: dict, messages: list) -> dict:
        """Parse an Anthropic Messages API response into the standard return dict."""
        text_parts = []
        tool_uses = []
        for block in resp.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block["text"])
            elif block.get("type") == "tool_use":
                tool_uses.append({
                    "id": block["id"],
                    "name": block["name"],
                    "input": block["input"],
                })
        assistant_msg = {"role": "assistant", "content": resp.get("content", [])}
        return {
            "text": "".join(text_parts),
            "tool_uses": tool_uses,
            "stop_reason": resp.get("stop_reason", "end_turn"),
            "messages": messages + [assistant_msg],
        }

    def _consume_stream(self, event_stream, messages: list, on_event) -> dict:
        """Iterate an Anthropic streaming response, aggregate content, fire callbacks."""
        text_parts = []
        tool_uses = []
        content_blocks = []
        stop_reason = "end_turn"
        current_tool = None

        for event in event_stream:
            chunk = json.loads(event["chunk"]["bytes"])
            event_type = chunk.get("type")

            if event_type == "content_block_start":
                block = chunk.get("content_block", {})
                if block.get("type") == "tool_use":
                    current_tool = {
                        "id": block["id"],
                        "name": block["name"],
                        "input_json": "",
                    }
                    if on_event:
                        on_event("tool", block["name"])
                else:
                    current_tool = None

            elif event_type == "content_block_delta":
                delta = chunk.get("delta", {})
                delta_type = delta.get("type")

                if delta_type == "text_delta":
                    text_parts.append(delta["text"])
                    if on_event:
                        on_event("text", delta["text"])
                elif delta_type == "input_json_delta" and current_tool is not None:
                    current_tool["input_json"] += delta.get("partial_json", "")
                elif delta_type == "thinking_delta":
                    thinking_text = delta.get("thinking", "")
                    if thinking_text and on_event:
                        on_event("thinking", thinking_text)

            elif event_type == "content_block_stop":
                if current_tool is not None:
                    try:
                        parsed_input = json.loads(current_tool["input_json"]) if current_tool["input_json"] else {}
                    except json.JSONDecodeError:
                        parsed_input = {}
                    tool_uses.append({
                        "id": current_tool["id"],
                        "name": current_tool["name"],
                        "input": parsed_input,
                    })
                    content_blocks.append({
                        "type": "tool_use",
                        "id": current_tool["id"],
                        "name": current_tool["name"],
                        "input": parsed_input,
                    })
                    current_tool = None

            elif event_type == "message_delta":
                delta = chunk.get("delta", {})
                if "stop_reason" in delta:
                    stop_reason = delta["stop_reason"]

        combined_text = "".join(text_parts)
        if combined_text:
            content_blocks.insert(0, {"type": "text", "text": combined_text})

        return {
            "text": combined_text,
            "tool_uses": tool_uses,
            "stop_reason": stop_reason,
            "messages": messages + [{"role": "assistant", "content": content_blocks}],
        }
