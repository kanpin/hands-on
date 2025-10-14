# 必要なライブラリをインポート
import os, boto3, json
import streamlit as st
from dotenv import load_dotenv

# .envファイルから環境変数をロード
load_dotenv(override=True)

# サイドバーで設定を入力
with st.sidebar:
    agent_runtime_arn = st.text_input("AgentCoreランタイムのARN")
    tavily_api_key = st.text_input("Tavily APIキー", type="password")

# タイトルを描画
st.title("なんでも検索エージェント")
st.write("Strands AgentsがMCPサーバーを使って情報収集します！")

# チャットボックスを描画
if prompt := st.chat_input("メッセージを入力してね"):
    # ユーザーのプロンプトを表示
    with st.chat_message("user"):
        st.markdown(prompt)

    # エージェントの回答を表示
    with st.chat_message("assistant"):
        # AgentCoreランタイムを呼び出し
        agentcore = boto3.client('bedrock-agentcore')
        payload = json.dumps({
            "prompt": prompt,
            "tavily_api_key": tavily_api_key
        })
        response = agentcore.invoke_agent_runtime(
            agentRuntimeArn=agent_runtime_arn,
            payload=payload.encode()
        )

        ### ここから下はストリーミングレスポンスの処理 ------------------------------------------
        container = st.container()
        text_holder = container.empty()
        buffer = ""

        # レスポンスを1行ずつチェック
        for line in response["response"].iter_lines():
            if line and line.decode("utf-8").startswith("data: "):
                data = line.decode("utf-8")[6:]

                # 文字列コンテンツの場合は無視
                if data.startswith('"') or data.startswith("'"):
                    continue

                # 読み込んだ行をJSONに変換
                event = json.loads(data)

                # ツール利用を検出
                if "event" in event and "contentBlockStart" in event["event"]:
                    if "toolUse" in event["event"]["contentBlockStart"].get("start", {}):
                        # 現在のテキストを確定
                        if buffer:
                            text_holder.markdown(buffer)
                            buffer = ""
                        # ツールステータスを表示
                        container.info("🔍 Tavily検索ツールを利用しています")
                        text_holder = container.empty()

                # テキストコンテンツを検出
                if "data" in event and isinstance(event["data"], str):
                    buffer += event["data"]
                    text_holder.markdown(buffer)
                elif "event" in event and "contentBlockDelta" in event["event"]:
                    buffer += event["event"]["contentBlockDelta"]["delta"].get("text", "")
                    text_holder.markdown(buffer)

        # 最後に残ったテキストを表示
        text_holder.markdown(buffer)
        ### ------------------------------------------------------------------------------
