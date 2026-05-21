#!/bin/bash
cd /Users/air/Desktop/ziwei-api
# Kill old processes
pkill -f "uvicorn.*8119" 2>/dev/null
pkill -f "localhost.run" 2>/dev/null
sleep 1
# Start API service
python3 run.py &
sleep 3
echo "=============================="
echo "🚀 服务已启动: http://localhost:8119"
echo ""
echo "📡 启动公开隧道..."
echo "=============================="
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=30 -R 80:localhost:8119 nokey@localhost.run 2>&1 | grep --line-buffered -o 'https://[^ ]*\.lhr\.life'
