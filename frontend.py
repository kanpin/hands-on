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
# ✅ UI構成（デザインはそのまま）
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
            text_holder.markdown("🔎 検索中...")

            # ✅ invoke_agent_runtime (同期呼び出し)
            payload = json.dumps({
                "inputText": prompt,
                "tavily_api_key": tavily_api_key
            })

            response = agentcore.invoke_agent_runtime(
                agentRuntimeArn=agent_runtime_arn,
                payload=payload.encode("utf-8"),
                contentType="application/json",
                accept="application/json"
            )

            # ✅ 応答の中身を判定して抽出
            output = None
            if "body" in response:
                body = json.loads(response["body"].read())
                output = body.get("outputText") or body
            elif "responseBody" in response:
                body = response["responseBody"]
                output = body.get("outputText") or body
            else:
                output = response

            text_holder.markdown(output)

        except Exception as e:
            st.error("❌ エージェント呼び出し中にエラーが発生しました")
            st.code(str(e))
