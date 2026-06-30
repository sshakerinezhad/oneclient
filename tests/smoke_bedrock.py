"""Run manually: python tests/smoke_bedrock.py
Confirms Bedrock creds + model access via a tiny Converse call."""
import boto3
from llm.config import load_config


def main():
    cfg = load_config()
    sess = boto3.Session(profile_name=cfg["bedrock"]["aws_profile"] or None)
    client = sess.client("bedrock-runtime", region_name=cfg["bedrock"]["region"])
    resp = client.converse(
        modelId=cfg["bedrock"]["query_model_id"],
        messages=[{"role": "user", "content": [{"text": "Reply with the single word: OK"}]}],
        inferenceConfig={"maxTokens": 16, "temperature": 0},
    )
    text = resp["output"]["message"]["content"][0]["text"]
    print("MODEL REPLIED:", text)
    assert "OK" in text.upper()


if __name__ == "__main__":
    main()
