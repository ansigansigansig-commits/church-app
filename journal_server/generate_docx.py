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
    return s.replace("\r\n", " ").replace("\n", " ").replace("\r", "")


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

    # === 공지사항 (paragraph별 줄바꿈 분배) ===
    for tbl in root.iter():
        if tbl.tag.split('}')[-1] != 'tbl':
            continue
        tbl_text = " ".join(
            t.text for t in tbl.iter()
            if t.tag.split('}')[-1] == 't' and t.text
        )
        if "공지사항" in tbl_text and "금주일" in tbl_text:
            cells = [c for c in tbl.iter() if c.tag.split('}')[-1] == 'tc']
            if len(cells) >= 2:
                content_cell = cells[1]
                # subList > p 구조에서 paragraph별로 텍스트 분배
                sub_list = None
                for child in content_cell:
                    if child.tag.split('}')[-1] == 'subList':
                        sub_list = child
                        break
                if sub_list is not None:
                    paras = [p for p in sub_list if p.tag.split('}')[-1] == 'p']
                    ann_text = data.get("announcements", "-")
                    ann_lines = ann_text.split("\n") if ann_text else ["-"]
                    # 빈 줄 제거
                    ann_lines = [l for l in ann_lines if l.strip()]

                    # paragraph 부족 시 복제 추가
                    from copy import deepcopy
                    while len(paras) < len(ann_lines):
                        new_p = deepcopy(paras[-1])
                        sub_list.append(new_p)
                        paras.append(new_p)

                    for pi, para in enumerate(paras):
                        t_elems = [t for t in para.iter()
                                  if t.tag.split('}')[-1] == 't']
                        if not t_elems:
                            continue
                        if pi < len(ann_lines):
                            t_elems[0].text = _esc(ann_lines[pi])
                        else:
                            t_elems[0].text = " "
                        for t in t_elems[1:]:
                            t.text = " "
            break

    # === 기타 모임 ===
    for tbl in root.iter():
        if tbl.tag.split('}')[-1] != 'tbl':
            continue
        tbl_text = " ".join(
            t.text for t in tbl.iter()
            if t.tag.split('}')[-1] == 't' and t.text
        )
        if "기타 모임" in tbl_text:
            # 실제로는 기타 모임 섹션 제목이지 테이블이 아님
            break

    # === 학습 표 ===
    classes = data.get("study_classes", [])
    if classes:
        _replace_study(root, classes)

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


def _replace_study(root, classes):
    """학습 표 치환. 테이블 셀(tc) 기반으로 안전하게 치환."""
    # 학습 테이블 찾기: 부서명이 포함된 테이블
    dept_markers = ["어린이 성경공부", "유치부"]
    study_tables = []

    for tbl in root.iter():
        if tbl.tag.split('}')[-1] != 'tbl':
            continue
        tbl_text = " ".join(
            t.text for t in tbl.iter()
            if t.tag.split('}')[-1] == 't' and t.text
        )
        if any(m in tbl_text for m in dept_markers):
            study_tables.append(tbl)

    if not study_tables:
        return

    # 행 필드 매핑
    row_map = {
        "시간": "time", "학생": "attendees", "교사": "teacher",
        "교재": "material", "진도": "content", "비고": "note",
        "참석인원": "attendance_count",
    }

    for tbl_idx, tbl in enumerate(study_tables):
        rows = [r for r in tbl if r.tag.split('}')[-1] == 'tr']

        for row in rows:
            cells = [c for c in row if c.tag.split('}')[-1] == 'tc']
            if not cells:
                continue

            # 첫 셀의 텍스트 = 레이블
            label_texts = [t.text.strip() for t in cells[0].iter()
                          if t.tag.split('}')[-1] == 't' and t.text and t.text.strip()]
            label = label_texts[0] if label_texts else ""

            # 헤더 행 (부서명)
            if not label and len(cells) > 1:
                for col_idx, cell in enumerate(cells[1:], 0):
                    cls_idx = tbl_idx * 5 + col_idx
                    cls = classes[cls_idx] if cls_idx < len(classes) else None
                    t_elems = [t for t in cell.iter() if t.tag.split('}')[-1] == 't']
                    for t in t_elems:
                        t.text = _esc(cls.get("department", "-")) if cls else "-"
                continue

            field = row_map.get(label)
            if not field:
                continue

            # 데이터 셀 (col 1~5)
            for col_idx, cell in enumerate(cells[1:], 0):
                cls_idx = tbl_idx * 5 + col_idx
                cls = classes[cls_idx] if cls_idx < len(classes) else None

                t_elems = [t for t in cell.iter() if t.tag.split('}')[-1] == 't']
                if not t_elems:
                    continue

                if cls:
                    if field == "attendees":
                        names = cls.get("attendees", [])
                        val = _esc(", ".join(names)) if names else "-"
                    elif field == "attendance_count":
                        val = f"{cls.get('attendance_count', 0)}명"
                    elif field == "note":
                        parts = []
                        note = cls.get("note", "")
                        if note and note not in ("-", "없음", ""):
                            parts.append(note)
                        absentees = cls.get("absentees", [])
                        if absentees:
                            parts.append(f"결석: {cls.get('absent_count', len(absentees))}명 ({', '.join(absentees)})")
                        val = _esc(" / ".join(parts)) if parts else "-"
                    else:
                        v = cls.get(field, "-")
                        val = _esc(v) if v else "-"
                else:
                    val = "-"

                # 첫 텍스트 노드에 값, 나머지 비움
                t_elems[0].text = val
                for t in t_elems[1:]:
                    t.text = " "


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
