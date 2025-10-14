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
agentcore = boto3.client("bedrock-agentcore", region_name=region)

# ----------------------------------------------------------
# ✅ UI構成
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
            debug_log = st.expander("🪵 デバッグログ（クリックで展開）")
            buffer = ""

            # ✅ 正しいpayload構造（Converse準拠）
            payload = json.dumps({
                "inferenceConfig": {
                    "maxTokens": 512
                },
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "sessionAttributes": {
                    "tavily_api_key": tavily_api_key or ""
                }
            })

            response = agentcore.invoke_agent_runtime(
                agentRuntimeArn=agent_runtime_arn,
                payload=payload.encode("utf-8"),
                contentType="application/json",
                accept="text/event-stream"
            )

            # ----------------------------------------------------------
            # ✅ ストリームを処理
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

                    debug_log.write(event)

                    if "delta" in event:
                        text = event["delta"].get("text", "")
                        buffer += text
                        text_holder.markdown(buffer)
                    elif "event" in event and "contentBlockDelta" in event["event"]:
                        text = event["event"]["contentBlockDelta"]["delta"].get("text", "")
                        buffer += text
                        text_holder.markdown(buffer)

            if not buffer:
                st.warning("⚠️ 応答本文が空でした。")
            else:
                text_holder.markdown(buffer)

        except Exception as e:
            st.error("❌ エージェント呼び出し中にエラーが発生しました")
            st.code(str(e))
