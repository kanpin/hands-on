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

region = os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2")

# ----------------------------------------------------------
# ✅ Bedrock AgentCore クライアント
# ----------------------------------------------------------
agentcore = boto3.client("bedrock-agentcore", region_name=region)

# ----------------------------------------------------------
# ✅ UI構成（デザインそのまま）
# ----------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 設定")
    agent_runtime_arn = st.text_input("AgentCoreランタイムのARN")
    tavily_api_key = st.text_input("Tavily APIキー", type="password")

st.title("なんでも検索エージェント")
st.write("Strands AgentsがMCPサーバーを使って情報収集します！")

# ----------------------------------------------------------
# ✅ チャットボックス
# ----------------------------------------------------------
if prompt := st.chat_input("メッセージを入力してね"):
    if not agent_runtime_arn:
        st.warning("⚠️ AgentCoreランタイムARNを入力してください。")
        st.stop()

    st.chat_message("user").write(prompt)

    with st.chat_message("assistant"):
        try:
            container = st.container()
            text_holder = container.empty()
            buffer = ""

            # ----------------------------------------------------------
            # ✅ invoke_agent_runtime（StreamingBodyレスポンス）
            # ----------------------------------------------------------
            payload = json.dumps({
                "inputText": prompt,
                "tavily_api_key": tavily_api_key
            })

            response = agentcore.invoke_agent_runtime(
                agentRuntimeArn=agent_runtime_arn,
                payload=payload.encode("utf-8"),
                contentType="application/json",
                accept="text/event-stream"
            )

            # ----------------------------------------------------------
            # ✅ ストリーミングBodyを1行ずつ読み取り
            # ----------------------------------------------------------
            stream = response["response"]
            for line in stream.iter_lines():
                if not line:
                    continue
                if line.startswith(b"data: "):
                    data = line.decode("utf-8")[6:]
                    try:
                        event = json.loads(data)
                    except Exception:
                        continue

                    # delta（テキストの一部）を受け取る
                    if "delta" in event:
                        delta_text = event["delta"].get("text", "")
                        buffer += delta_text
                        text_holder.markdown(buffer)

                    # contentBlockDelta形式にも対応
                    elif "event" in event and "contentBlockDelta" in event["event"]:
                        delta_text = event["event"]["contentBlockDelta"]["delta"].get("text", "")
                        buffer += delta_text
                        text_holder.markdown(buffer)

                    # toolUseイベント
                    elif "event" in event and "contentBlockStart" in event["event"]:
                        if "toolUse" in event["event"]["contentBlockStart"].get("start", {}):
                            container.info("🔍 Tavily検索ツールを利用中…")

            # ----------------------------------------------------------
            # ✅ 最後に確定表示
            # ----------------------------------------------------------
            if buffer:
                text_holder.markdown(buffer)

        except Exception as e:
            st.error("❌ エージェント呼び出し中にエラーが発生しました")
            st.code(str(e))
