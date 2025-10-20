# ----------------------------------------------------------
# ✅ frontend.py（Claude Haiku 4.5対応 / 安全なストリーミング処理版）
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

# 既定値を環境変数から取得
default_region = os.getenv("AWS_DEFAULT_REGION", "ap-northeast-1")
default_access_key = os.getenv("AWS_ACCESS_KEY_ID", "")
default_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")

# ----------------------------------------------------------
# ✅ UI構成
# ----------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 設定")

    st.subheader("🔐 AWS 認証情報")
    aws_access_key = st.text_input("AWS Access Key ID", value=default_access_key)
    aws_secret_key = st.text_input("AWS Secret Access Key", value=default_secret_key, type="password")
    aws_region = st.text_input("リージョン", value=default_region)

    st.subheader("🤖 AgentCore 設定")
    agent_runtime_arn = st.text_input("AgentCore ランタイム ARN")
    tavily_api_key = st.text_input("Tavily APIキー", type="password")

st.title("なんでも検索エージェント")
st.write("Strands AgentsがMCPサーバーを使って情報収集します！")

# ----------------------------------------------------------
# ✅ boto3クライアントの動的生成
# ----------------------------------------------------------
if aws_access_key and aws_secret_key:
    try:
        agentcore = boto3.client(
            "bedrock-agentcore",
            region_name=aws_region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )
    except Exception as e:
        st.error("❌ AWS認証情報が無効です。")
        st.code(str(e))
        st.stop()
else:
    st.warning("⚠️ AWS認証情報を入力してください。")
    st.stop()

# ----------------------------------------------------------
# ✅ チャットボックス
# ----------------------------------------------------------
if prompt := st.chat_input("メッセージを入力してね"):
    if not agent_runtime_arn:
        st.warning("⚠️ AgentCoreランタイムARNを入力してください。")
        st.stop()

    # ユーザー入力の表示
    st.chat_message("user").write(prompt)

    with st.chat_message("assistant"):
        try:
            container = st.container()
            text_holder = container.empty()
            debug_log = st.expander("🪵 デバッグログ（クリックで展開）")
            buffer = ""

            # ✅ ConverseStream v2 構造
            payload = json.dumps({
                "prompt": prompt,  # ← バックエンドの互換性維持
                "input": {
                    "messages": [
                        {"role": "user", "content": [{"text": prompt}]}
                    ]
                },
                "inferenceConfig": {"maxTokens": 512},
                "sessionAttributes": {"tavily_api_key": tavily_api_key or ""}
            })

            # AgentCoreランタイム呼び出し
            response = agentcore.invoke_agent_runtime(
                agentRuntimeArn=agent_runtime_arn,
                payload=payload.encode("utf-8"),
                contentType="application/json",
                accept="text/event-stream"
            )

            stream = response["response"]

            # ----------------------------------------------------------
            # ✅ 安全なストリーミング処理（型チェック付き）
            # ----------------------------------------------------------
            for line in stream.iter_lines():
                if not line:
                    continue

                if line.startswith(b"data: "):
                    data = line.decode("utf-8")[6:]

                    try:
                        event = json.loads(data)
                    except Exception:
                        # data が純テキストの場合はそのまま出力
                        buffer += data
                        text_holder.markdown(buffer)
                        continue

                    debug_log.write(event)

                    # event が辞書型（通常のdeltaイベント）
                    if isinstance(event, dict):
                        # delta テキスト更新イベント
                        if "delta" in event and isinstance(event["delta"], dict):
                            text = event["delta"].get("text", "")
                            buffer += text
                            text_holder.markdown(buffer)

                        # contentBlockDelta イベント
                        elif "event" in event and "contentBlockDelta" in event["event"]:
                            delta = event["event"]["contentBlockDelta"]["delta"]
                            if isinstance(delta, dict):
                                text = delta.get("text", "")
                                buffer += text
                                text_holder.markdown(buffer)

                    # event が文字列型（例：「申」など）
                    elif isinstance(event, str):
                        buffer += event
                        text_holder.markdown(buffer)

            # 出力が空の場合の警告
            if not buffer:
                st.warning("⚠️ 応答本文が空でした。")
            else:
                text_holder.markdown(buffer)

        except Exception as e:
            st.error("❌ エージェント呼び出し中にエラーが発生しました")
            st.code(str(e))
