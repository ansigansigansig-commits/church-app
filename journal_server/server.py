#!/usr/bin/env python3
"""
교회 일지 DOCX 생성 서버

Firebase에서 일지 생성 요청을 감시하고 DOCX 파일을 자동 생성합니다.
폰 앱에서 "일지 생성 요청" 버튼을 누르면 맥북에서 자동으로 DOCX를 만들어줍니다.
"""
import logging
import subprocess
import threading
import time
from pathlib import Path

import requests
from flask import Flask, jsonify, request

from generate_docx import generate_journal_docx

app = Flask(__name__)
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

FB_URL = "https://sdgc-ae7f9-default-rtdb.asia-southeast1.firebasedatabase.app"
OUTPUT_DIR = Path.home() / "Desktop"


def notify_mac(title, message):
    """macOS 알림"""
    subprocess.run(
        [
            "osascript", "-e",
            f'display notification "{message}" with title "{title}" sound name "Glass"',
        ],
        check=False,
    )


def check_firebase():
    """Firebase에서 생성 요청 확인"""
    try:
        resp = requests.get(f"{FB_URL}/journal.json", timeout=10)
        if resp.status_code != 200:
            return
        journals = resp.json()
        if not journals:
            return

        for date_key, data in journals.items():
            if not data or not isinstance(data, dict):
                continue
            if data.get("generate_requested") and not data.get("generated"):
                log.info(f"일지 생성 요청 감지: {date_key}")

                filename = f"SDG일지_{date_key}.docx"
                output_path = OUTPUT_DIR / filename

                try:
                    generate_journal_docx(data, str(output_path))
                except Exception as e:
                    log.error(f"DOCX 생성 실패: {e}")
                    notify_mac("일지 생성 실패", str(e)[:50])
                    continue

                # 생성 완료 플래그
                requests.patch(
                    f"{FB_URL}/journal/{date_key}.json",
                    json={"generated": True, "generate_requested": False},
                    timeout=10,
                )

                log.info(f"일지 생성 완료: {output_path}")
                notify_mac("교회 일지 생성 완료", f"{filename}이 바탕화면에 저장되었습니다.")

                # Finder에서 파일 보여주기
                subprocess.run(["open", "-R", str(output_path)], check=False)

    except Exception as e:
        log.error(f"Firebase 체크 오류: {e}")


def polling_loop():
    """10초마다 Firebase 체크"""
    while True:
        check_firebase()
        time.sleep(10)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "output_dir": str(OUTPUT_DIR)})


@app.route("/generate", methods=["POST"])
def manual_generate():
    """수동 생성 엔드포인트"""
    data = request.json
    if not data or not data.get("date"):
        return jsonify({"error": "date required"}), 400
    filename = f"SDG일지_{data['date']}.docx"
    output_path = OUTPUT_DIR / filename
    generate_journal_docx(data, str(output_path))
    return jsonify({"status": "ok", "path": str(output_path)})


def main():
    log.info(f"교회 일지 서버 시작 (저장 위치: {OUTPUT_DIR})")
    log.info("Firebase 폴링 중... 폰에서 '일지 생성 요청' 버튼을 눌러주세요.")

    t = threading.Thread(target=polling_loop, daemon=True)
    t.start()

    app.run(host="0.0.0.0", port=5050, debug=False)


if __name__ == "__main__":
    main()
