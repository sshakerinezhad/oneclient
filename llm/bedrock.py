"""BedrockClient: thin wrapper around boto3 Bedrock Converse API.

Provides buffered (converse) and streaming (converse_stream) calls, both
returning a uniform dict with text, tool_uses, stop_reason, and messages.
Supports tool-use blocks and Anthropic extended thinking via additionalModelRequestFields.
"""
import json
import time

import boto3
from botocore.exceptions import ClientError

MAX_RETRIES = 3


class BedrockClient:
    def __init__(self, cfg: dict):
        bedrock_cfg = cfg["bedrock"]
        sess = boto3.Session(
            profile_name=bedrock_cfg.get("aws_profile") or None
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
        """Buffered (non-streaming) Converse call with automatic retry."""
        kwargs = self._build_kwargs(model_id, system, messages, tools, thinking, max_tokens)
        resp = self._call_with_retry(self._client.converse, kwargs)
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
        """Streaming Converse call.

        Iterates the EventStream, fires on_event(kind, text) for each delta
        (kinds: 'text', 'thinking', 'tool'), then returns the same shape as
        converse().  on_event=None disables callbacks but still aggregates.
        """
        kwargs = self._build_kwargs(model_id, system, messages, tools, thinking, max_tokens)
        raw = self._call_with_retry(self._client.converse_stream, kwargs)
        return self._consume_stream(raw["stream"], messages, on_event)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_kwargs(self, model_id, system, messages, tools, thinking, max_tokens):
        kwargs = {
            "modelId": model_id,
            "messages": messages,
            "system": [{"text": system}],
            "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0},
        }
        if tools:
            kwargs["toolConfig"] = {"tools": tools}
        if thinking:
            kwargs["additionalModelRequestFields"] = {
                "thinking": {"type": "enabled", "budget_tokens": self._thinking_budget}
            }
        return kwargs

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
        """Parse a buffered Converse response into the standard return dict."""
        content = resp["output"]["message"]["content"]
        text_parts = []
        tool_uses = []
        for block in content:
            if "text" in block:
                text_parts.append(block["text"])
            elif "toolUse" in block:
                tu = block["toolUse"]
                tool_uses.append({
                    "id": tu["toolUseId"],
                    "name": tu["name"],
                    "input": tu["input"],
                })
            # reasoningContent blocks (extended thinking) are intentionally
            # excluded from the return value; they are internal scratchpad.
        return {
            "text": "".join(text_parts),
            "tool_uses": tool_uses,
            "stop_reason": resp["stopReason"],
            "messages": messages + [resp["output"]["message"]],
        }

    def _consume_stream(self, stream, messages: list, on_event) -> dict:
        """Iterate an EventStream, aggregate content, fire callbacks."""
        text_parts = []
        tool_uses = []
        stop_reason = "end_turn"
        current_tool = None  # {"id", "name", "input_json"}

        for event in stream:
            if "contentBlockStart" in event:
                start = event["contentBlockStart"].get("start", {})
                if "toolUse" in start:
                    tu = start["toolUse"]
                    current_tool = {"id": tu["toolUseId"], "name": tu["name"], "input_json": ""}
                    if on_event:
                        on_event("tool", tu["name"])
                else:
                    current_tool = None

            elif "contentBlockDelta" in event:
                delta = event["contentBlockDelta"].get("delta", {})
                if "text" in delta:
                    text_parts.append(delta["text"])
                    if on_event:
                        on_event("text", delta["text"])
                elif "toolUse" in delta and current_tool is not None:
                    current_tool["input_json"] += delta["toolUse"].get("input", "")
                elif "reasoningContent" in delta:
                    rc_text = delta["reasoningContent"].get("text", "")
                    if rc_text and on_event:
                        on_event("thinking", rc_text)

            elif "contentBlockStop" in event:
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
                    current_tool = None

            elif "messageStop" in event:
                stop_reason = event["messageStop"].get("stopReason", "end_turn")

        combined_text = "".join(text_parts)

        # Reconstruct assistant message for the multi-turn messages list
        content_blocks = []
        if combined_text:
            content_blocks.append({"text": combined_text})
        for tu in tool_uses:
            content_blocks.append({"toolUse": {
                "toolUseId": tu["id"],
                "name": tu["name"],
                "input": tu["input"],
            }})

        return {
            "text": combined_text,
            "tool_uses": tool_uses,
            "stop_reason": stop_reason,
            "messages": messages + [{"role": "assistant", "content": content_blocks}],
        }
