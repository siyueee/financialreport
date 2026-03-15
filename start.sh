#!/bin/bash

echo "🚀 启动 Streamlit 服务..."
# 后台启动 Streamlit 服务（监听 0.0.0.0:8501）
streamlit run main.py --server.address=0.0.0.0 --server.port=8501 &
STREAMLIT_PID=$!

# 等待 5 秒，确保 Streamlit 完全启动
sleep 5

echo "🔗 启动 ngrok 内网穿透..."
# 启动 ngrok 映射 8501 端口
ngrok http 8501

# 当 ngrok 退出时，自动关闭 Streamlit 服务
trap "kill $STREAMLIT_PID" EXIT