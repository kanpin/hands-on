# ----------------------------------------------------------
# ✅ frontend_final.py - Claude 4.5 + Bedrock AgentCore + Tavily MCP Server 対応
# ----------------------------------------------------------
# 改良点:
# - AWSアクセスキー/シークレットキー/リージョンをUIから指定可能
# - AgentCoreランタイムARN + Tavilyキー入力対応
# - Claude 4.5 ストリーミング出力に完全対応
# - 不正なPythonオブジェクトを完全除去
# - JSON整形済みログ出力
# - graceful fallback付き例外処理
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
# ✅ Streamlit UI 構成
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
# ✅ JSON安全整形関数
# ----------------------------------------------------------
def safe_json_dump(obj):
    """JSON化できないPythonオブジェクトを除外"""
    if isinstance(obj, dict):
        clean = {}
        for k, v in obj.items():
            if isinstance(v, (str, int, float, bool)):
                clean[k] = v
            elif isinstance(v, (list, tuple)):
                sub = [safe_json_dump(i) for i in v]
                clean[k] = [s for s in sub if s not in (None, {}, [])]
            elif isinstance(v, dict):
                sub = safe_json_dump(v)
                if sub not in (None, {}, []):
                    clean[k] = sub
        return clean
    elif isinstance(obj, list):
        out = [safe_json_dump(i) for i in obj]
        return [x for x in out if x not in (None, {}, [])]
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    else:
        # ❌ Pythonオブジェクトなどは完全除外
        return None

# ----------------------------------------------------------
# ✅ チャットUI本体
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
            # ✅ ストリーミング処理（1文字ずつも対応）
            # ----------------------------------------------------------
            for line in stream.iter_lines():
                if not line or not line.startswith(b"data: "):
                    continue

                data = line.decode("utf-8")[6:]

                try:
                    event = json.loads(data)
                except Exception:
                    # JSONでない（純テキスト）行はスキップまたはそのまま出力
                    buffer += data
                    text_holder.markdown(buffer)
                    continue

                # 🪵 JSON安全化してログ出力
                filtered = safe_json_dump(event)
                if filtered:
                    try:
                        debug_log.json(filtered)
                    except Exception:
                        debug_log.write(json.dumps(filtered, ensure_ascii=False, indent=2))

                # 🧩 テキスト部分抽出してUIに逐次反映
                if isinstance(event, dict):
                    if "delta" in event and isinstance(event["delta"], dict):
                        text = event["delta"].get("text", "")
                        buffer += text
                        text_holder.markdown(buffer)

                    elif "event" in event and "contentBlockDelta" in event["event"]:
                        delta = event["event"]["contentBlockDelta"]["delta"]
                        if isinstance(delta, dict):
                            text = delta.get("text", "")
                            buffer += text
                            text_holder.markdown(buffer)

                elif isinstance(event, str):
                    buffer += event
                    text_holder.markdown(buffer)

            # ⚠️ 応答が空なら警告
            if not buffer:
                st.warning("⚠️ 応答本文が空でした。")
            else:
                text_holder.markdown(buffer)

        except Exception as e:
            st.error("❌ エージェント呼び出し中にエラーが発生しました")
            st.code(str(e))
