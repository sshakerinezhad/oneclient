"""Run manually: python tests/smoke_bedrock.py
Confirms Bedrock creds + model access via invoke_model."""
import json
import boto3
from llm.config import load_config


def main():
    cfg = load_config()
    sess = boto3.Session(profile_name=cfg["bedrock"]["aws_profile"] or None)
    client = sess.client("bedrock-runtime", region_name=cfg["bedrock"]["region"])
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
