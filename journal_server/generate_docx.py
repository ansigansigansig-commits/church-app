#!/usr/bin/env python3
"""
솔리데오글로리아교회 일지 HWPX 생성 모듈
python-hwpx로 원본 서식 유지 + lxml element 직접 치환
"""
import warnings
from pathlib import Path

from hwpx import HwpxDocument

warnings.filterwarnings("ignore")

TEMPLATE_PATH = Path(__file__).parent / "template.hwpx"


def _esc(s):
    """줄바꿈 제거 (lxml이 &/< 이스케이프는 자동 처리)."""
    if not isinstance(s, str):
        return str(s)
    return s.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


def generate_journal_docx(data: dict, output_path: str) -> str:
    """HWPX 템플릿의 데이터를 치환하여 저장."""
    out = Path(output_path)
    if out.suffix.lower() != ".hwpx":
        out = out.with_suffix(".hwpx")

    doc = HwpxDocument.open(str(TEMPLATE_PATH))
    section = doc.sections[0]
    root = section.element

    # 모든 텍스트 노드 수집
    all_t = [e for e in root.iter() if e.tag.split('}')[-1] == 't']

    # === 단순 텍스트 치환 ===
    simple = [
        ("2026. 02 .22", _esc(data.get("dateStr", data.get("date_str", "")))),
        ("문지영", _esc(data.get("author", ""))),
        ("10:45 ~ 13:00", _esc(data.get("am_time", ""))),
        ("   그 태를 여신고로", _esc(data.get("am_title", ""))),
        ("창 29:31-30:24(2)", _esc(data.get("am_scripture", ""))),
        ("니케아 신조", _esc(data.get("am_creed", ""))),
        ("14:45 ~16:30", _esc(data.get("pm_time", ""))),
        ("사사기 해설", _esc(data.get("pm_title", ""))),
        ("193(99편), 92(45편)", _esc(data.get("pm_hymns", ""))),
        ("안식 집사", _esc(data.get("pm_prayer", ""))),
        ("장진욱 (성동구) /오전만 참석, 권다인 (구미) ",
         _esc(data.get("visitors", "-"))),
        ("- 오전,오후: 이재우, 김해련(수술), 고영진,고윤석, 고영민, 고영우, 박송빈, 정다혜(포항)",
         _esc(data.get("absences", "-"))),
        ("- 오후: 김용래, 지영원, 김도예", "-"),
    ]

    for old, new in simple:
        if not old or not new:
            continue
        for e in all_t:
            if e.text and old in e.text:
                e.text = e.text.replace(old, new)
                break

    # === 오전 찬송 (긴 텍스트) ===
    for e in all_t:
        if e.text and "283장" in str(e.text):
            e.text = _esc(data.get("am_hymns", "-"))
            break

    # === 예배전 순서 ===
    pre_old = "  시편(\u2018성전에 올라가는 노래\u2019) 해설     "
    for e in all_t:
        if e.text and pre_old in e.text:
            e.text = _esc(data.get("am_pre", "-"))
            break

    # === 설교자/인도자 (김병혁 목사 3곳: 설교자, 인도자, 담임목사) ===
    kim_elems = [e for e in all_t if e.text and "김병혁 목사" in e.text]
    if len(kim_elems) >= 2:
        kim_elems[0].text = _esc(data.get("am_preacher", "김병혁 목사"))
        kim_elems[1].text = _esc(data.get("pm_leader", "김병혁 목사"))

    # === 인원수 ("계" 다음 3개씩) ===
    nums_map = {
        1: [("34", str(data.get("am_male", ""))),
            ("41", str(data.get("am_female", ""))),
            ("75", str(data.get("am_total", "")))],
        2: [("32", str(data.get("pm_male", ""))),
            ("40", str(data.get("pm_female", ""))),
            ("72", str(data.get("pm_total", "")))],
    }
    gye_count = 0
    for i, e in enumerate(all_t):
        if e.text and e.text.strip() == "계":
            gye_count += 1
            nums = nums_map.get(gye_count)
            if nums:
                for j, (old_n, new_n) in enumerate(nums):
                    idx = i + 1 + j
                    if idx < len(all_t) and all_t[idx].text and all_t[idx].text.strip() == old_n:
                        all_t[idx].text = new_n

    # === 공지사항 ===
    for e in all_t:
        if e.text and "1.금주일" in e.text:
            e.text = _esc(data.get("announcements", "-"))
            break

    # === linesegarray 전부 삭제 (텍스트 길이 변경 시 한글 렌더링 깨짐 방지) ===
    # list()로 먼저 수집 후 삭제 (순회 중 삭제 방지)
    to_remove = [e for e in root.iter() if "linesegarray" in e.tag]
    for e in to_remove:
        parent = e.getparent()
        if parent is not None:
            parent.remove(e)

    # === 저장 (python-hwpx가 ZIP 구조 보존) ===
    section.mark_dirty()
    doc.save_to_path(str(out))
    return str(out)


if __name__ == "__main__":
    import requests
    # Firebase에서 실제 데이터로 테스트
    resp = requests.get(
        "https://sdgc-ae7f9-default-rtdb.asia-southeast1.firebasedatabase.app/journal/2026-03-22.json"
    )
    if resp.ok and resp.json():
        data = resp.json()
        result = generate_journal_docx(data, "test_output.hwpx")
        print(f"생성 완료: {result}")
    else:
        # 테스트 데이터
        test_data = {
            "dateStr": "2026. 03. 23", "author": "문지영",
            "am_preacher": "김병혁 목사", "am_time": "10:45 ~ 13:00",
            "am_title": "테스트", "am_scripture": "창 1:1",
            "am_pre": "시편 해설", "am_hymns": "찬송 1",
            "am_creed": "사도신경", "am_sacrament": "-",
            "am_male": 34, "am_female": 41, "am_total": 75,
            "pm_prayer": "안식", "pm_leader": "김병혁 목사",
            "pm_time": "14:30", "pm_title": "오후",
            "pm_scripture": "-", "pm_hymns": "찬송 2", "pm_creed": "-",
            "pm_male": 32, "pm_female": 40, "pm_total": 72,
            "visitors": "-", "absences": "-", "announcements": "공지",
        }
        result = generate_journal_docx(test_data, "test_output.hwpx")
        print(f"생성 완료: {result}")
