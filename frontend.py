# ----------------------------------------------------------
# ✅ frontend_final_assistant_only_safe_v4.py
# Claude 4.5 + Bedrock AgentCore + Tavily MCP Server 対応
# 「最終回答のみ表示」＋「応答本文が空」誤検知防止版
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
st.write("最終的な assistant の回答のみを出力します。")

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
# ✅ 多段JSON安全パース関数
# ----------------------------------------------------------
def deep_json_parse(data):
    """
    何重にJSON文字列化されていても、辞書になるまで再帰的にjson.loads()する
    """
    if not isinstance(data, str):
        return data
    try:
        parsed = json.loads(data)
        if isinstance(parsed, str):
            return deep_json_parse(parsed)
        return parsed
    except Exception:
        return data

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

            # ConverseStream v2形式
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
            # ✅ "message" イベントだけ抽出
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
                if "message" in event:
                    final_json = event

            # ----------------------------------------------------------
            # ✅ assistant の回答のみ抽出（構造安全版）
            # ----------------------------------------------------------
            if final_json:
                raw_msg = final_json.get("message", "")
                msg_obj = deep_json_parse(raw_msg)

                text_output = ""

                if isinstance(msg_obj, dict) and msg_obj.get("role") == "assistant":
                    content = msg_obj.get("content", [])
                    if isinstance(content, list):
                        for c in content:
                            if isinstance(c, dict) and "text" in c:
                                text_output += c["text"]
                    elif isinstance(content, str):
                        text_output = content

                if text_output.strip():
                    text_holder.markdown(text_output.strip())
                    st.success("✅ assistantの最終回答を取得しました。")
                else:
                    st.warning("⚠️ 応答本文が空でした。構造を確認してください。")

                # 🪵 デバッグログ出力
                debug_log.code(json.dumps(final_json, ensure_ascii=False, indent=2), language="json")
            else:
                st.warning("⚠️ 最終 'message' イベントが取得できませんでした。")

        except Exception as e:
            st.error("❌ エージェント呼び出し中にエラーが発生しました")
            st.code(str(e))
