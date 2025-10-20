# ----------------------------------------------------------
# Claude 4.5 + Bedrock AgentCore + Tavily MCP Server 対応
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
# ✅ Streamlit UI
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
st.write("Strands Agents + Bedrock AgentCore + Tavily MCP Server を利用します。")

# ----------------------------------------------------------
# ✅ boto3 クライアント生成
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
# ✅ チャットUI
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

            # ConverseStream v2形式（Claude 4.5互換）
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

            # ランタイム呼び出し
            response = agentcore.invoke_agent_runtime(
                agentRuntimeArn=agent_runtime_arn,
                payload=payload.encode("utf-8"),
                contentType="application/json",
                accept="text/event-stream"
            )

            stream = response["response"]

            # ----------------------------------------------------------
            # ✅ 最終回答のみ抽出
            # ----------------------------------------------------------
            final_json = None
            for line in stream.iter_lines():
                if not line or not line.startswith(b"data: "):
                    continue

                data = line.decode("utf-8")[6:]
                try:
                    event = json.loads(data)
                except Exception:
                    continue

                # 🧩 "message" キーがあるものだけ保持
                if "message" in event:
                    final_json = event

            # ----------------------------------------------------------
            # ✅ assistant の最終メッセージだけ出力
            # ----------------------------------------------------------
            if final_json:
                msg = final_json.get("message")
                text_output = ""

                # messageが文字列の場合（JSON埋め込みの可能性あり）
                if isinstance(msg, str):
                    try:
                        msg_obj = json.loads(msg)
                    except Exception:
                        msg_obj = {"content": [{"text": msg}]}
                else:
                    msg_obj = msg

                # content抽出
                if isinstance(msg_obj, dict):
                    role = msg_obj.get("role", "")
                    content = msg_obj.get("content", [])
                    if role == "assistant" and isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and "text" in block:
                                text_output += block["text"] + "\n"

                # 出力処理
                if text_output:
                    text_holder.markdown(text_output)
                    st.success("✅ 回答を取得しました。")
                else:
                    st.warning("⚠️ 有効なassistant応答が見つかりませんでした。")

                # デバッグログ出力
                debug_log.code(json.dumps(final_json, ensure_ascii=False, indent=2), language="json")

            else:
                st.warning("⚠️ 最終イベント（message）が取得できませんでした。")

        except Exception as e:
            st.error("❌ エージェント呼び出し中にエラーが発生しました")
            st.code(str(e))
