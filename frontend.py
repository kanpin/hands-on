# ----------------------------------------------------------
# ✅ frontend_filtered_safe.py
# 中間イベントを除外し、最終「message」イベントだけ出力（完全対応版）
# ----------------------------------------------------------
import os
import json
import boto3
import streamlit as st
from dotenv import load_dotenv

# ----------------------------------------------------------
# ✅ 環境変数読み込み
# ----------------------------------------------------------
if os.path.exists(".env"):
    load_dotenv()

default_region = os.getenv("AWS_DEFAULT_REGION", "ap-northeast-1")
default_access_key = os.getenv("AWS_ACCESS_KEY_ID", "")
default_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")

# ----------------------------------------------------------
# ✅ UI構成
# ----------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 設定")
    aws_access_key = st.text_input("AWS Access Key ID", value=default_access_key)
    aws_secret_key = st.text_input("AWS Secret Access Key", value=default_secret_key, type="password")
    aws_region = st.text_input("リージョン", value=default_region)
    agent_runtime_arn = st.text_input("AgentCore ランタイム ARN")
    tavily_api_key = st.text_input("Tavily APIキー", type="password")

st.title("なんでも検索エージェント")
st.write("中間イベントを除外し、最終回答のみを出力します。")

# ----------------------------------------------------------
# ✅ boto3クライアント生成
# ----------------------------------------------------------
agentcore = boto3.client(
    "bedrock-agentcore",
    region_name=aws_region,
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key
)

# ----------------------------------------------------------
# ✅ チャット処理
# ----------------------------------------------------------
if prompt := st.chat_input("質問を入力してください"):
    if not agent_runtime_arn:
        st.warning("⚠️ AgentCoreランタイムARNを入力してください。")
        st.stop()

    st.chat_message("user").write(prompt)

    with st.chat_message("assistant"):
        container = st.container()
        text_holder = container.empty()
        debug_log = st.expander("🪵 デバッグログ（クリックで展開）")

        try:
            payload = json.dumps({
                "prompt": prompt,
                "input": {
                    "messages": [
                        {"role": "user", "content": [{"text": prompt}]}
                    ]
                },
                "inferenceConfig": {"maxTokens": 512},
                "sessionAttributes": {"tavily_api_key": tavily_api_key or ""}
            })

            response = agentcore.invoke_agent_runtime(
                agentRuntimeArn=agent_runtime_arn,
                payload=payload.encode("utf-8"),
                contentType="application/json",
                accept="text/event-stream"
            )

            stream = response["response"]
            final_json = None

            for line in stream.iter_lines():
                if not line or not line.startswith(b"data: "):
                    continue

                data = line.decode("utf-8")[6:]
                try:
                    event = json.loads(data)
                except Exception:
                    continue  # 不完全JSONは無視

                # 「message」キーがあるものだけ残す
                if "message" in event:
                    final_json = event

            # ----------------------------------------------------------
            # ✅ 最終イベント出力（どの形式でも安全）
            # ----------------------------------------------------------
            if final_json:
                msg = final_json.get("message", {})
                content = msg.get("content", "")
                text_output = ""

                # contentがリストの場合
                if isinstance(content, list) and len(content) > 0:
                    first = content[0]
                    if isinstance(first, dict) and "text" in first:
                        text_output = first["text"]
                # contentが文字列の場合
                elif isinstance(content, str):
                    text_output = content
                else:
                    text_output = json.dumps(content, ensure_ascii=False)

                st.success("✅ 最終出力を取得しました")
                text_holder.markdown(text_output)
                debug_log.code(json.dumps(final_json, ensure_ascii=False, indent=2), language="json")
            else:
                st.warning("⚠️ 有効な最終イベントを取得できませんでした。")

        except Exception as e:
            st.error("❌ エージェント呼び出し中にエラーが発生しました")
            st.code(str(e))
