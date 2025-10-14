import os
import json
import boto3
import streamlit as st
from dotenv import load_dotenv

# ----------------------------------------------------------
# ✅ 環境変数の読み込み
# ----------------------------------------------------------
if os.path.exists(".env"):
    load_dotenv()

region = os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2")

# ----------------------------------------------------------
# ✅ Bedrock AgentCore クライアント初期化
# ----------------------------------------------------------
try:
    agentcore = boto3.client("bedrock-agentcore", region_name=region)
except Exception as e:
    st.error(f"❌ Bedrock AgentCoreクライアント初期化失敗: {e}")
    st.stop()

# ----------------------------------------------------------
# ✅ UI構成（デザインはそのまま）
# ----------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 設定")
    agent_runtime_arn = st.text_input("AgentCoreランタイムのARN")
    tavily_api_key = st.text_input("Tavily APIキー", type="password")

st.title("なんでも検索エージェント")
st.write("Strands AgentsがMCPサーバーを使って情報収集します！")

# チャットボックス
if prompt := st.chat_input("メッセージを入力してね"):
    if not agent_runtime_arn:
        st.warning("⚠️ AgentCoreランタイムARNを入力してください。")
        st.stop()

    st.chat_message("user").write(prompt)
    st.chat_message("assistant").write("🔎 検索中...")

    try:
        # ✅ invoke_agent_runtimeを利用
        response = agentcore.invoke_agent_runtime(
            agentRuntimeArn=agent_runtime_arn,
            inputText=prompt
        )

        # ✅ 応答の抽出
        output = response.get("completion", "（応答がありません）")
        st.chat_message("assistant").write(output)

    except Exception as e:
        st.error("❌ エージェント呼び出し中にエラーが発生しました")
        st.code(str(e))
