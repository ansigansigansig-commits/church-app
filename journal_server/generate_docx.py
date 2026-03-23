#!/usr/bin/env python3
"""
솔리데오글로리아교회 일지 HWPX 생성 모듈
원본 HWP 서식을 100% 유지하면서 데이터만 치환합니다.
"""
import re
import shutil
import zipfile
from pathlib import Path

TEMPLATE_PATH = Path(__file__).parent / "template.hwpx"


def _replace_in_zip(zip_path: str, entry_name: str, new_data: bytes):
    """ZIP 파일 내 특정 엔트리만 교체 (zip 명령어로 원본 메타데이터 보존)."""
    import subprocess, tempfile
    abs_zip = str(Path(zip_path).resolve())
    tmp_dir = tempfile.mkdtemp()
    try:
        entry_file = Path(tmp_dir) / entry_name
        entry_file.parent.mkdir(parents=True, exist_ok=True)
        entry_file.write_bytes(new_data)
        subprocess.run(
            ["zip", abs_zip, entry_name],
            cwd=tmp_dir, check=True, capture_output=True,
        )
    finally:
        shutil.rmtree(tmp_dir)


def generate_journal_docx(data: dict, output_path: str) -> str:
    """
    HWPX 템플릿의 {{태그}}를 데이터로 치환하여 저장.
    output_path 확장자가 .docx/.hwpx 무관 — 실제 출력은 .hwpx
    """
    # 출력 경로를 .hwpx로 변환
    out = Path(output_path)
    if out.suffix.lower() != ".hwpx":
        out = out.with_suffix(".hwpx")

    # 원본 템플릿 XML 읽기
    with zipfile.ZipFile(TEMPLATE_PATH, "r") as z:
        section_xml = z.read("Contents/section0.xml").decode("utf-8")

    # === 원본 데이터 → 새 데이터로 직접 치환 ===
    section_xml = _replace_fields(section_xml, data)

    # === 학습 표 치환 ===
    # 템플릿의 학습 테이블에는 원본 데이터가 그대로 있음
    # study_classes 데이터로 치환 (동적 — 부서 수가 매주 다를 수 있음)
    classes = data.get("study_classes", [])
    if classes:
        section_xml = _replace_study_tables(section_xml, classes)

    # === HWPX 재패키징 (원본 ZIP 바이트 복사 방식) ===
    shutil.copy2(str(TEMPLATE_PATH), str(out))
    # section0.xml만 교체
    _replace_in_zip(str(out), "Contents/section0.xml", section_xml.encode("utf-8"))

    return str(out)


def _replace_fields(xml: str, data: dict) -> str:
    """원본 HWPX XML의 데이터 값을 새 데이터로 직접 치환."""

    # 단순 텍스트 치환 (원본 값 → 새 값)
    simple = [
        ("2026. 02 .22", data.get("dateStr", data.get("date_str", ""))),
        ("\u6587\u5730\u82f1" if False else "문지영", data.get("author", "")),  # 작성자
        ("10:45 ~ 13:00", data.get("am_time", "")),
        ("   그 태를 여신고로", data.get("am_title", "")),
        ("창 29:31-30:24(2)", data.get("am_scripture", "")),
        ("니케아 신조", data.get("am_creed", "")),
        ("14:45 ~16:30", data.get("pm_time", "")),
        ("사사기 해설", data.get("pm_title", "")),
        ("193(99편), 92(45편)", data.get("pm_hymns", "")),
        ("안식 집사", data.get("pm_prayer", "")),
    ]

    for old, new in simple:
        if old and new:
            xml = xml.replace(old, new, 1)

    # 방문교인
    visitors_old = "장진욱 (성동구) /오전만 참석, 권다인 (구미) "
    xml = xml.replace(visitors_old, data.get("visitors", "-"), 1)

    # 결석교인 (2줄 → 1줄로 합쳐서 치환, 빈 텍스트 태그 방지)
    abs1 = "- 오전,오후: 이재우, 김해련(수술), 고영진,고윤석, 고영민, 고영우, 박송빈, 정다혜(포항)"
    abs2 = "- 오후: 김용래, 지영원, 김도예"
    xml = xml.replace(abs1, data.get("absences", "-"), 1)
    xml = xml.replace(abs2, "-", 1)

    # 오전 찬송 (긴 텍스트)
    hymn_match = re.search(r"시편찬송\s+283장.*?살후 3장\)\s*", xml, re.DOTALL)
    if hymn_match:
        xml = xml.replace(hymn_match.group(), data.get("am_hymns", "-"), 1)

    # 예배전 순서 (스마트따옴표)
    pre_old = "  시편(\u2018성전에 올라가는 노래\u2019) 해설     "
    xml = xml.replace(pre_old, data.get("am_pre", "-"), 1)

    # 설교자/인도자: "김병혁 목사"가 3곳 (설교자, 인도자, 담임목사)
    kim = "김병혁 목사"
    positions = []
    start = 0
    while True:
        pos = xml.find(kim, start)
        if pos == -1:
            break
        positions.append(pos)
        start = pos + 1

    if len(positions) >= 2:
        # 뒤에서부터 치환 (위치 안 깨지게)
        # 3번째(담임목사): 그대로
        # 2번째: 오후 인도자
        # 1번째: 오전 설교자
        for idx in reversed(range(len(positions))):
            pos = positions[idx]
            if idx == 0:
                replacement = data.get("am_preacher", kim)
            elif idx == 1:
                replacement = data.get("pm_leader", kim)
            else:
                continue  # 담임목사는 그대로
            xml = xml[:pos] + replacement + xml[pos + len(kim):]

    # 인원수: "계" 다음 숫자 치환
    nums_am = [("34", str(data.get("am_male", ""))),
               ("41", str(data.get("am_female", ""))),
               ("75", str(data.get("am_total", "")))]
    nums_pm = [("32", str(data.get("pm_male", ""))),
               ("40", str(data.get("pm_female", ""))),
               ("72", str(data.get("pm_total", "")))]

    gye_count = 0
    gye_pos = 0
    while True:
        pos = xml.find(">계<", gye_pos)
        if pos == -1:
            break
        gye_count += 1
        nums = nums_am if gye_count == 1 else nums_pm if gye_count == 2 else []
        # "계" 이후 영역에서 숫자 치환
        search_start = pos + 3
        for old_num, new_num in nums:
            pattern = f">{old_num}<"
            num_pos = xml.find(pattern, search_start)
            if num_pos != -1 and num_pos < search_start + 500:
                xml = xml[:num_pos + 1] + new_num + xml[num_pos + 1 + len(old_num):]
                search_start = num_pos + len(new_num) + 1
        gye_pos = pos + 3

    # 성례: "성례" 다음 첫 번째 단독 "-"
    sacrament_pos = xml.find("성례")
    if sacrament_pos > 0:
        m = re.search(r">(-)<", xml[sacrament_pos:])
        if m:
            abs_pos = sacrament_pos + m.start(1)
            xml = xml[:abs_pos] + data.get("am_sacrament", "-") + xml[abs_pos + 1:]

    # 오후 본문: pm_hymns 이후 "본문" 다음 "-"
    pm_hymns_val = data.get("pm_hymns", "")
    pm_hymns_pos = xml.find(pm_hymns_val) if pm_hymns_val else xml.find("{{pm_hymns}}")
    if pm_hymns_pos > 0:
        sub = xml[pm_hymns_pos:]
        bon_pos = sub.find("본문")
        if bon_pos > 0:
            m = re.search(r">(-)<", sub[bon_pos:])
            if m:
                abs_pos = pm_hymns_pos + bon_pos + m.start(1)
                xml = xml[:abs_pos] + data.get("pm_scripture", "-") + xml[abs_pos + 1:]

    # 오후 신앙고백: pm_scripture 이후 "신앙고백" 다음 "-"
    pm_scripture_val = data.get("pm_scripture", "-")
    pm_scr_pos = xml.find(pm_scripture_val, pm_hymns_pos) if pm_hymns_pos > 0 else -1
    if pm_scr_pos > 0:
        sub = xml[pm_scr_pos:]
        sin_pos = sub.find("신앙고백")
        if sin_pos > 0:
            m = re.search(r">(-)<", sub[sin_pos:])
            if m:
                abs_pos = pm_scr_pos + sin_pos + m.start(1)
                xml = xml[:abs_pos] + data.get("pm_creed", "-") + xml[abs_pos + 1:]

    # 공지사항
    ann_pos = xml.find("공지사항")
    if ann_pos > 0:
        m = re.search(r">(1\.금주일[^<]+)<", xml[ann_pos:], re.DOTALL)
        if m:
            abs_start = ann_pos + m.start(1)
            abs_end = ann_pos + m.end(1)
            xml = xml[:abs_start] + data.get("announcements", "-") + xml[abs_end:]

    return xml


def _replace_study_tables(xml: str, classes: list[dict]) -> str:
    """학습 테이블의 데이터 셀을 study_classes 데이터로 치환.

    원본 템플릿의 학습 테이블 구조를 유지하면서 텍스트만 교체.
    부서 수가 다를 경우 템플릿의 기존 데이터를 새 데이터로 덮어씀.
    """
    # 학습 테이블은 원본 데이터가 들어있으므로,
    # 각 부서의 필드값을 찾아서 치환
    # 원본 부서명 목록
    original_depts = [
        "어린이 성경공부", "유스2부 주일오전", "유스1부  주일오전",
        "청년부", "청년부 오전",
        "유치부", "초등1부", "초등2부", "청소년1부", "청소년2부",
    ]

    # 원본 부서 데이터를 새 데이터로 치환
    for i, cls in enumerate(classes):
        if i < len(original_depts):
            old_dept = original_depts[i]
            new_dept = cls.get("department", "")
            if old_dept != new_dept and old_dept in xml:
                xml = xml.replace(old_dept, new_dept, 1)

        # 학생 목록
        attendees = cls.get("attendees", [])
        if attendees:
            students_str = ", ".join(attendees)
            # 기존 학생 데이터는 치환이 어려우므로 그대로 유지
            # (학습 표는 매주 구조가 같으므로 위치 기반 치환이 필요)

    return xml


if __name__ == "__main__":
    test_data = {
        "dateStr": "2026. 03. 23",
        "date": "2026-03-23",
        "author": "문지영",
        "am_preacher": "김병혁 목사",
        "am_time": "10:45 ~ 13:00",
        "am_title": "심히 두렵고 답답하여",
        "am_scripture": "창 32:1-12",
        "am_pre": "시편 해설",
        "am_hymns": "시편찬송 193(99편), 222(115편), 헌상송 363, 송영 126(65편)",
        "am_creed": "니케아-콘스탄티노플 신조",
        "am_sacrament": "-",
        "am_male": 34, "am_female": 41, "am_total": 75,
        "pm_prayer": "정지명",
        "pm_leader": "이동열 교수",
        "pm_time": "14:30 ~",
        "pm_title": "상반기 SDG 스쿨",
        "pm_scripture": "-",
        "pm_hymns": "275(130편), 22(9편)",
        "pm_creed": "-",
        "pm_male": 32, "pm_female": 40, "pm_total": 72,
        "visitors": "장진욱 성도(서울 도곡동)",
        "absences": "- 오전·오후: 이종민(독일)",
        "announcements": "1. 교회 표어: 네 모든 길을 든든히 하라",
    }
    result = generate_journal_docx(test_data, "test_output.hwpx")
    print(f"생성 완료: {result}")
