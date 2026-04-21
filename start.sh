#!/bin/bash
# start.sh — Launch Jasper AI on Linux/Mac
# Make executable: chmod +x start.sh
# Then run: ./start.sh

echo ""
echo " ======================================"
echo "   JASPER AI — Starting Up"
echo " ======================================"
echo ""

# Activate virtual environment
source venv/bin/activate 2>/dev/null || {
    echo " ERROR: venv not found. Run setup.sh first."
    exit 1
}

# Start Ollama if not running
if ! curl -s http://localhost:11434 > /dev/null 2>&1; then
    echo " Starting Ollama..."
    ollama serve &
    sleep 3
else
    echo " Ollama is already running."
fi

# Start daemon in background
echo " Starting knowledge daemon..."
python daemon.py &
DAEMON_PID=$!
echo " Daemon running (PID: $DAEMON_PID)"

# Open browser after a moment
sleep 2
echo " Opening Jasper AI in browser at http://localhost:8501"
(sleep 3 && xdg-open http://localhost:8501 2>/dev/null || open http://localhost:8501 2>/dev/null) &

# Start Streamlit
streamlit run app_v2.py --server.headless false --server.port 8501

# Cleanup on exit
kill $DAEMON_PID 2>/dev/null
echo " Jasper AI stopped."
