"""Run manually: python tests/smoke_bedrock.py
Confirms Bedrock creds + model access via invoke_model."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import boto3
from llm.config import load_config


def main():
    cfg = load_config()
    bcfg = cfg["bedrock"]
    sess = boto3.Session(
        aws_access_key_id=bcfg.get("aws_access_key_id") or None,
        aws_secret_access_key=bcfg.get("aws_secret_access_key") or None,
        aws_session_token=bcfg.get("aws_session_token") or None,
        profile_name=bcfg.get("aws_profile") or None,
    )
    client = sess.client("bedrock-runtime", region_name=bcfg["region"])
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 16,
        "temperature": 0,
        "messages": [{"role": "user", "content": "Reply with the single word: OK"}],
    })
    resp = client.invoke_model(
        modelId=cfg["bedrock"]["query_model_id"],
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(resp["body"].read())
    text = result["content"][0]["text"]
    print("MODEL REPLIED:", text)
    assert "OK" in text.upper()


if __name__ == "__main__":
    main()
