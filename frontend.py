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

    # ユーザー入力を表示
    st.chat_message("user").write(prompt)

    # エージェントの回答をストリーム表示
    with st.chat_message("assistant"):
        try:
            container = st.container()
            text_holder = container.empty()
            buffer = ""

            # ----------------------------------------------------------
            # ✅ invoke_agent_runtime_stream() でリアルタイム応答
            # ----------------------------------------------------------
            payload = json.dumps({
                "inputText": prompt,
                "tavily_api_key": tavily_api_key
            })

            response = agentcore.invoke_agent_runtime_stream(
                agentRuntimeArn=agent_runtime_arn,
                payload=payload.encode("utf-8"),
                contentType="application/json",
                accept="application/json"
            )

            # レスポンスストリームを逐次処理
            for event in response.get("responseStream", []):
                # --- 出力テキストが届いたとき ---
                if "chunk" in event:
                    chunk = event["chunk"]
                    try:
                        data = json.loads(chunk.get("bytes", b"{}").decode("utf-8"))
                        if "outputText" in data:
                            buffer += data["outputText"]
                            text_holder.markdown(buffer)
                    except Exception:
                        continue

                # --- エラーイベント ---
                elif "error" in event:
                    err = event["error"]
                    st.error(f"❌ AgentCoreエラー: {err.get('message', str(err))}")

            # 最後に残ったテキストを確定表示
            if buffer:
                text_holder.markdown(buffer)

        except Exception as e:
            st.error("❌ エージェント呼び出し中にエラーが発生しました")
            st.code(str(e))
