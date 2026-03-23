#!/bin/bash
# 교회 일지 서버 설치 스크립트
# Mac 부팅 시 자동으로 시작됩니다.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_PATH="$HOME/Library/LaunchAgents/com.sdg.journal-server.plist"
VENV_DIR="$SCRIPT_DIR/venv"

echo "=== 교회 일지 서버 설치 ==="

# 기존 서비스 중지 (있으면)
launchctl unload "$PLIST_PATH" 2>/dev/null

# 가상환경 생성 (없으면)
if [ ! -d "$VENV_DIR" ]; then
    echo "가상환경 생성 중..."
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
else
    echo "가상환경 이미 존재"
fi

# LaunchAgent plist 생성
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sdg.journal-server</string>
    <key>ProgramArguments</key>
    <array>
        <string>${VENV_DIR}/bin/python</string>
        <string>${SCRIPT_DIR}/server.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>StandardOutPath</key>
    <string>${SCRIPT_DIR}/server.log</string>
    <key>StandardErrorPath</key>
    <string>${SCRIPT_DIR}/server_error.log</string>
</dict>
</plist>
EOF

# LaunchAgent 로드
launchctl load "$PLIST_PATH"

echo ""
echo "✅ 설치 완료!"
echo "- 서버가 자동으로 시작되었습니다"
echo "- Mac 재부팅 후에도 자동 실행됩니다"
echo "- 일지는 바탕화면에 저장됩니다"
echo ""
echo "상태 확인: curl http://localhost:5050/health"
echo "중지: launchctl unload $PLIST_PATH"
echo "로그: tail -f $SCRIPT_DIR/server.log"
