# 주일 일지 자동 생성 강화 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 폰 앱에서 주보 PDF + 카톡 학습 보고를 입력하고 버튼 하나로 맥북에서 HWP 서식 그대로의 DOCX 일지를 자동 생성

**Architecture:**
- 폰 앱(HTML): 주보 PDF 추출(기존) + 카톡 메시지/이미지 파싱(신규) → Firebase에 일지 데이터 저장
- 맥북 로컬 서버(Python): Firebase 감시 → python-docx-template로 DOCX 생성 → 파일 저장
- 폰에서 "일지 생성" 버튼 → Firebase에 생성 요청 플래그 → 맥북 서버가 감지하여 자동 생성

**Tech Stack:** HTML/JS (기존 앱), Firebase REST API, Claude API (텍스트+이미지 파싱), Python (Flask + python-docx-template), LaunchAgent (Mac 자동시작)

---

## File Structure

### 폰 앱 (기존 파일 수정)
- **Modify:** `주일출석부_v2.html` — 일지 탭에 카톡 입력 UI + Firebase 일지 저장 + 생성 요청 로직 추가

### 맥북 서버 (신규)
- **Create:** `journal_server/server.py` — Flask 서버, Firebase 폴링, DOCX 생성 트리거
- **Create:** `journal_server/generate_docx.py` — python-docx-template로 DOCX 생성
- **Create:** `journal_server/template.docx` — HWP 서식 기반 DOCX 템플릿 (Jinja2 태그 포함)
- **Create:** `journal_server/requirements.txt` — 의존성
- **Create:** `journal_server/install.sh` — 설치 + LaunchAgent 등록 스크립트

---

## Chunk 1: 폰 앱 — 카톡 메시지 입력 UI 추가

### Task 1: 일지 탭에 카톡 입력 영역 추가

**Files:**
- Modify: `주일출석부_v2.html:408-414` (학습/기타 모임 카드)

- [ ] **Step 1: 기존 학습 카드를 카톡 입력 UI로 교체**

`j_study` textarea 영역을 다음으로 교체:
- 카톡 메시지 붙여넣기용 textarea
- 카톡 스크린샷 이미지 업로드 버튼
- "AI 자동 파싱" 버튼
- 파싱 결과 표시 영역 (부서별 테이블)

```html
<div class="settings-card">
  <div class="settings-label">학습 보고 (카톡)</div>
  <div class="settings-desc">SDG 교회학교 카톡방 메시지를 붙여넣거나 스크린샷을 올려주세요.</div>

  <!-- 텍스트 붙여넣기 -->
  <textarea id="j_kakao_text" class="custom-date-input"
    style="width:100%;background:#F7F4EF;min-height:120px;resize:vertical;font-family:inherit"
    placeholder="카톡 메시지 붙여넣기...&#10;&#10;예: * 26년 3월 22일 청년부 오전 모임&#10;- 출석 : 3명 (고수민, 박솔민, 허하민)&#10;- 내용 : 창세기 강설#95"></textarea>

  <!-- 이미지 업로드 -->
  <div style="display:flex;gap:8px;margin-top:8px">
    <input type="file" id="kakaoImgInput" accept="image/*" style="display:none" onchange="handleKakaoImg(this)" />
    <button class="sync-btn" style="background:#C8A45A;flex:1" onclick="document.getElementById('kakaoImgInput').click()">📷 스크린샷 업로드</button>
    <button class="sync-btn" style="background:#4A6741;flex:1" onclick="parseKakaoReport()">🔍 AI 자동 파싱</button>
  </div>
  <div id="kakaoImgName" style="font-size:12px;color:#4A6741;margin-top:6px"></div>
  <div id="kakaoParseStatus" style="font-size:12px;margin-top:6px;color:#4A6741"></div>

  <!-- 파싱 결과 -->
  <div id="kakaoResult" style="display:none;margin-top:12px">
    <div style="font-size:13px;font-weight:700;margin-bottom:8px">파싱 결과</div>
    <div id="kakaoResultContent"></div>
  </div>
</div>
```

- [ ] **Step 2: 확인**

브라우저에서 일지 탭 열어 카톡 입력 영역이 정상 표시되는지 확인

- [ ] **Step 3: Commit**

```bash
git add 주일출석부_v2.html
git commit -m "feat: 일지 탭에 카톡 학습 보고 입력 UI 추가"
```

---

### Task 2: 카톡 메시지 파싱 (텍스트 + 이미지)

**Files:**
- Modify: `주일출석부_v2.html` (script 영역)

- [ ] **Step 1: 이미지 핸들러 추가**

```javascript
let kakaoImgBase64 = null;

function handleKakaoImg(input) {
  const file = input.files[0];
  if (!file) return;
  document.getElementById('kakaoImgName').textContent = '📷 ' + file.name;
  const reader = new FileReader();
  reader.onload = function(e) {
    kakaoImgBase64 = e.target.result.split(',')[1];
  };
  reader.readAsDataURL(file);
}
```

- [ ] **Step 2: Claude API 파싱 함수 추가**

텍스트와 이미지 모두 지원. 텍스트가 있으면 텍스트 우선, 이미지만 있으면 이미지 분석.

```javascript
async function parseKakaoReport() {
  const text = document.getElementById('j_kakao_text').value.trim();
  const statusEl = document.getElementById('kakaoParseStatus');
  const apiKey = localStorage.getItem('claudeApiKey');

  if (!apiKey) { statusEl.textContent = '⚠️ 설정탭에서 API 키를 먼저 입력해주세요.'; return; }
  if (!text && !kakaoImgBase64) { statusEl.textContent = '⚠️ 카톡 메시지를 붙여넣거나 스크린샷을 올려주세요.'; return; }

  statusEl.textContent = '🔄 Claude가 학습 보고를 분석 중...';

  const content = [];
  if (kakaoImgBase64) {
    content.push({ type: "image", source: { type: "base64", media_type: "image/png", data: kakaoImgBase64 } });
  }
  if (text) {
    content.push({ type: "text", text: text });
  }
  content.push({ type: "text", text: KAKAO_PARSE_PROMPT });

  try {
    const response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
        "anthropic-dangerous-direct-browser-access": "true"
      },
      body: JSON.stringify({
        model: "claude-sonnet-4-20250514",
        max_tokens: 3000,
        messages: [{ role: "user", content }]
      })
    });
    const data = await response.json();
    if (data.error) throw new Error(data.error.message);
    const resultText = data.content.map(c => c.text || '').join('');
    const parsed = JSON.parse(resultText.replace(/```json|```/g, '').trim());
    kakaoStudyData = parsed;
    displayKakaoResult(parsed);
    statusEl.textContent = '✓ 파싱 완료!';
  } catch(e) {
    statusEl.textContent = '⚠️ 오류: ' + e.message;
  }
}
```

- [ ] **Step 3: 파싱 프롬프트 상수 추가**

```javascript
const KAKAO_PARSE_PROMPT = `이 카카오톡 메시지는 교회 학습/모임 보고입니다. 아래 JSON 형식으로만 응답하세요. 마크다운 없이 순수 JSON만.

각 부서별로 하나의 객체를 만들어주세요:
- department: 부서명 (예: "청년부 오전", "청년부 오후", "초등 2부", "청소년 2부")
- date: 날짜 (YYYY-MM-DD)
- time: 시간 (가능하면)
- teacher: 교사 (보고자 이름으로 추정)
- attendees: 출석 명단 (배열)
- attendance_count: 출석 인원수
- absentees: 결석 명단 (배열)
- absent_count: 결석 인원수
- content: 내용/진도
- material: 교재 (가능하면)
- note: 비고/특이사항

응답 형식:
{"classes": [{ department, date, time, teacher, attendees, attendance_count, absentees, absent_count, content, material, note }, ...]}`;
```

- [ ] **Step 4: 결과 표시 함수 추가**

```javascript
let kakaoStudyData = null;

function displayKakaoResult(data) {
  const container = document.getElementById('kakaoResultContent');
  const wrapper = document.getElementById('kakaoResult');
  wrapper.style.display = 'block';

  if (!data.classes || !data.classes.length) {
    container.innerHTML = '<div style="color:#C0392B">파싱된 데이터가 없습니다.</div>';
    return;
  }

  let html = '';
  data.classes.forEach((cls, i) => {
    html += `<div style="background:#F7F4EF;border-radius:10px;padding:12px;margin-bottom:8px">
      <div style="font-weight:700;color:#4A6741;margin-bottom:6px">${cls.department || '부서'}</div>
      <div style="font-size:12px;color:#555">
        <div>출석: ${cls.attendance_count}명 — ${(cls.attendees||[]).join(', ')}</div>
        ${cls.absent_count > 0 ? `<div style="color:#C0392B">결석: ${cls.absent_count}명 — ${(cls.absentees||[]).join(', ')}</div>` : ''}
        <div>내용: ${cls.content || '-'}</div>
        ${cls.note && cls.note !== '없음' ? `<div>비고: ${cls.note}</div>` : ''}
      </div>
    </div>`;
  });
  container.innerHTML = html;
}
```

- [ ] **Step 5: 확인**

카톡 메시지 샘플 붙여넣고 AI 파싱 버튼 눌러 결과 표시 확인

- [ ] **Step 6: Commit**

```bash
git add 주일출석부_v2.html
git commit -m "feat: 카톡 학습 보고 AI 파싱 기능 (텍스트+이미지)"
```

---

### Task 3: Firebase에 일지 데이터 저장 + 생성 요청

**Files:**
- Modify: `주일출석부_v2.html` (script 영역)

- [ ] **Step 1: 일지 데이터 Firebase 저장 함수**

기존 `getJournalData()` 결과 + 카톡 파싱 결과를 Firebase에 저장

```javascript
function saveJournalToFirebase(triggerGenerate = false) {
  const data = getJournalData();
  if (!data.date) { alert('날짜를 먼저 선택해주세요.'); return; }

  const journalData = {
    ...data,
    study_classes: kakaoStudyData ? kakaoStudyData.classes : [],
    kakao_raw: document.getElementById('j_kakao_text').value,
    generate_requested: triggerGenerate,
    generated: false,
    updated_at: new Date().toISOString()
  };

  const FB_URL = "https://sdgc-ae7f9-default-rtdb.asia-southeast1.firebasedatabase.app";
  fetch(`${FB_URL}/journal/${data.date}.json`, {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(journalData)
  }).then(r => {
    if (r.ok) {
      showSaveBadge(triggerGenerate ? '일지 생성 요청됨!' : '일지 저장됨');
    }
  }).catch(e => alert('저장 오류: ' + e.message));
}
```

- [ ] **Step 2: "일지 생성" 버튼 추가**

기존 PDF/Word 버튼 영역에 추가:

```html
<div style="display:flex;gap:10px;margin-bottom:10px">
  <button class="sync-btn" style="background:#2E7D32;flex:1;padding:14px;font-size:15px"
    onclick="saveJournalToFirebase(true)">📋 일지 생성 요청 (맥북)</button>
</div>
<div style="display:flex;gap:10px;margin-bottom:10px">
  <button class="sync-btn" style="background:#888;flex:1;font-size:12px"
    onclick="saveJournalToFirebase(false)">💾 임시 저장</button>
</div>
```

- [ ] **Step 3: Commit**

```bash
git add 주일출석부_v2.html
git commit -m "feat: 일지 데이터 Firebase 저장 + 맥북 생성 요청"
```

---

## Chunk 2: 맥북 서버 — DOCX 템플릿 + 생성 서버

### Task 4: DOCX 템플릿 생성

**Files:**
- Create: `journal_server/create_template.py` — 템플릿 생성 스크립트 (1회 실행)
- Create: `journal_server/template.docx` — 생성된 템플릿

- [ ] **Step 1: python-docx로 HWP 레이아웃 재현 템플릿 생성**

HWP에서 추출한 레이아웃 기반으로 Jinja2 태그가 포함된 DOCX 템플릿을 생성하는 스크립트.

```python
"""DOCX 템플릿 생성 (1회 실행)
HWP 서식과 동일한 레이아웃으로 Jinja2 태그 포함 DOCX 생성
"""
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

doc = Document()

# 페이지 설정 (A4, 여백 1.8cm)
section = doc.sections[0]
section.page_width = Cm(21)
section.page_height = Cm(29.7)
section.top_margin = Cm(1.8)
section.bottom_margin = Cm(1.5)
section.left_margin = Cm(1.8)
section.right_margin = Cm(1.8)

# 기본 폰트: 맑은 고딕
style = doc.styles['Normal']
style.font.name = '맑은 고딕'
style.font.size = Pt(9)

# === 제목 ===
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = title.add_run('솔리데오글로리아교회 일지')
run.bold = True
run.font.size = Pt(19)

# 날짜 + 작성자
date_p = doc.add_paragraph()
date_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
date_p.add_run('{{ date_str }}').font.size = Pt(9)

author_p = doc.add_paragraph()
author_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
author_p.add_run('작성자 : {{ author }}          담임목사').font.size = Pt(9)

# === 오전 예배 테이블 ===
# ... (테이블 구성은 generate_docx.py에서 동적으로 생성)

doc.save('template.docx')
```

실제로는 python-docx-template의 Jinja2 문법을 사용하되, 복잡한 표 구조는 코드로 동적 생성하는 하이브리드 방식이 최적.

- [ ] **Step 2: 확인 — 템플릿 파일 생성 후 Word에서 열어 레이아웃 확인**

- [ ] **Step 3: Commit**

```bash
git add journal_server/
git commit -m "feat: DOCX 일지 템플릿 생성 스크립트"
```

---

### Task 5: DOCX 생성 엔진

**Files:**
- Create: `journal_server/generate_docx.py`

- [ ] **Step 1: DOCX 생성 모듈 작성**

Firebase에서 받은 일지 데이터를 HWP 서식 그대로의 DOCX로 변환.
헤더, 오전 예배, 오후 예배, 학습 표, 방문/결석, 공지 순서.

핵심 구조:
```python
"""일지 DOCX 생성 모듈"""
from docx import Document
from docx.shared import Cm, Pt, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml

FONT = '맑은 고딕'
GRAY = 'EFEFEF'

def set_cell_shading(cell, color):
    """셀 배경색 설정"""
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color}"/>')
    cell._tc.get_or_add_tcPr().append(shading)

def add_label_cell(row, idx, text, width=None):
    """라벨 셀 (회색 배경, 볼드, 가운데 정렬)"""
    cell = row.cells[idx]
    cell.text = ''
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(8.5)
    run.font.name = FONT
    set_cell_shading(cell, GRAY)

def add_value_cell(row, idx, text):
    """값 셀"""
    cell = row.cells[idx]
    cell.text = ''
    run = cell.paragraphs[0].add_run(text or '-')
    run.font.size = Pt(8.5)
    run.font.name = FONT

def add_section_heading(doc, text):
    """섹션 헤딩 (밑줄)"""
    p = doc.add_paragraph()
    p.space_before = Pt(6)
    p.space_after = Pt(2)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(10.5)
    run.font.name = FONT
    # 하단 테두리
    pPr = p._p.get_or_add_pPr()
    pBdr = parse_xml(
        f'<w:pBdr {nsdecls("w")}>'
        '<w:bottom w:val="single" w:sz="12" w:space="1" w:color="000000"/>'
        '</w:pBdr>'
    )
    pPr.append(pBdr)

def generate_journal_docx(data, output_path):
    """
    일지 DOCX 생성

    data: Firebase에서 받은 일지 데이터 dict
    output_path: 저장 경로
    """
    doc = Document()

    # 페이지 설정
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(1.8)
    section.bottom_margin = Cm(1.5)
    section.left_margin = Cm(1.8)
    section.right_margin = Cm(1.8)

    # 기본 스타일
    style = doc.styles['Normal']
    style.font.name = FONT
    style.font.size = Pt(9)

    # 제목
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run('솔리데오글로리아교회 일지')
    run.bold = True
    run.font.size = Pt(19)
    run.font.name = FONT

    # 날짜
    date_p = doc.add_paragraph()
    date_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = date_p.add_run(data.get('dateStr', ''))
    run.font.size = Pt(9)
    run.font.name = FONT

    # 작성자
    author_p = doc.add_paragraph()
    author_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = author_p.add_run(f"작성자 : {data.get('author', '')}          담임목사")
    run.font.size = Pt(9)
    run.font.name = FONT

    # === 오전 예배 ===
    add_section_heading(doc, '예배')

    tbl = doc.add_table(rows=6, cols=4)
    tbl.style = 'Table Grid'

    # Row 0: 장소 | 값 | 설교자 | 값
    add_label_cell(tbl.rows[0], 0, '장소')
    add_value_cell(tbl.rows[0], 1, '솔리데오글로리아 예배당/유튜브 채널')
    add_label_cell(tbl.rows[0], 2, '설교자')
    add_value_cell(tbl.rows[0], 3, data.get('am_preacher'))

    # Row 1: 시간 | 값 | 제목 | 값
    add_label_cell(tbl.rows[1], 0, '시간')
    add_value_cell(tbl.rows[1], 1, data.get('am_time'))
    add_label_cell(tbl.rows[1], 2, '제목')
    add_value_cell(tbl.rows[1], 3, data.get('am_title'))

    # Row 2: 예배전 순서 (병합)
    add_label_cell(tbl.rows[2], 0, '예배전\n순서')
    # 셀 병합: 1-3
    tbl.rows[2].cells[1].merge(tbl.rows[2].cells[3])
    add_value_cell(tbl.rows[2], 1, data.get('am_pre'))

    # Row 3: 찬송 | 값 | 성례 | 값
    add_label_cell(tbl.rows[3], 0, '찬송')
    hymns = data.get('am_hymns', '-')
    add_value_cell(tbl.rows[3], 1, hymns)
    add_label_cell(tbl.rows[3], 2, '성례')
    add_value_cell(tbl.rows[3], 3, data.get('am_sacrament'))

    # Row 4: 신앙고백 | 값 | 본문 | 값
    add_label_cell(tbl.rows[4], 0, '신앙고백')
    add_value_cell(tbl.rows[4], 1, data.get('am_creed'))
    add_label_cell(tbl.rows[4], 2, '본문')
    add_value_cell(tbl.rows[4], 3, data.get('am_scripture'))

    # Row 5: 참석인원
    tbl.rows[5].cells[0].merge(tbl.rows[5].cells[1])
    tbl.rows[5].cells[2].merge(tbl.rows[5].cells[3])
    p = tbl.rows[5].cells[2].paragraphs[0]
    p.add_run('참석인원').bold = True
    # 남/여/계 서브 테이블은 텍스트로 대체
    att_text = f"\n남: {data.get('am_male', 0)}  여: {data.get('am_female', 0)}  계: {data.get('am_total', 0)}"
    p.add_run(att_text).font.size = Pt(9)

    # === 오후 예배 ===
    add_section_heading(doc, '오후 기도 순서')

    # 오후 기도 인도자
    prayer_tbl = doc.add_table(rows=1, cols=1)
    prayer_tbl.style = 'Table Grid'
    add_value_cell(prayer_tbl.rows[0], 0, data.get('pm_prayer'))

    pm_tbl = doc.add_table(rows=4, cols=4)
    pm_tbl.style = 'Table Grid'

    add_label_cell(pm_tbl.rows[0], 0, '장소')
    add_value_cell(pm_tbl.rows[0], 1, '솔리데오글로리아 예배당/유튜브 채널')
    add_label_cell(pm_tbl.rows[0], 2, '인도자')
    add_value_cell(pm_tbl.rows[0], 3, data.get('pm_leader'))

    add_label_cell(pm_tbl.rows[1], 0, '시간')
    add_value_cell(pm_tbl.rows[1], 1, data.get('pm_time'))
    add_label_cell(pm_tbl.rows[1], 2, '제목')
    add_value_cell(pm_tbl.rows[1], 3, data.get('pm_title'))

    add_label_cell(pm_tbl.rows[2], 0, '찬송')
    add_value_cell(pm_tbl.rows[2], 1, data.get('pm_hymns'))
    add_label_cell(pm_tbl.rows[2], 2, '본문')
    add_value_cell(pm_tbl.rows[2], 3, data.get('pm_scripture'))

    add_label_cell(pm_tbl.rows[3], 0, '신앙고백')
    add_value_cell(pm_tbl.rows[3], 1, data.get('pm_creed'))
    pm_tbl.rows[3].cells[2].merge(pm_tbl.rows[3].cells[3])
    p = pm_tbl.rows[3].cells[2].paragraphs[0]
    p.add_run('참석인원').bold = True
    att_text = f"\n남: {data.get('pm_male', 0)}  여: {data.get('pm_female', 0)}  계: {data.get('pm_total', 0)}"
    p.add_run(att_text).font.size = Pt(9)

    # === 학습 표 ===
    classes = data.get('study_classes', [])
    if classes:
        add_section_heading(doc, '학습')

        # 학습 테이블: 부서별로
        cols = len(classes) + 1  # 항목열 + 부서 수
        study_tbl = doc.add_table(rows=8, cols=cols)
        study_tbl.style = 'Table Grid'

        # 헤더 행
        labels = ['', '시간', '학생', '교사', '교재', '진도', '비고', '참석인원']
        for i, label in enumerate(labels):
            add_label_cell(study_tbl.rows[i], 0, label)

        # 부서별 데이터
        for j, cls in enumerate(classes):
            col = j + 1
            add_label_cell(study_tbl.rows[0], col, cls.get('department', ''))
            add_value_cell(study_tbl.rows[1], col, cls.get('time', '-'))
            add_value_cell(study_tbl.rows[2], col, ', '.join(cls.get('attendees', [])))
            add_value_cell(study_tbl.rows[3], col, cls.get('teacher', '-'))
            add_value_cell(study_tbl.rows[4], col, cls.get('material', '-'))
            add_value_cell(study_tbl.rows[5], col, cls.get('content', '-'))
            note = cls.get('note', '-')
            absent_text = ''
            if cls.get('absentees'):
                absent_text = f"결석: {', '.join(cls['absentees'])}"
            add_value_cell(study_tbl.rows[6], col, f"{note}\n{absent_text}".strip() or '-')
            add_value_cell(study_tbl.rows[7], col, str(cls.get('attendance_count', 0)) + '명')

    # === 방문 및 결석 ===
    add_section_heading(doc, '방문 및 결석')

    va_tbl = doc.add_table(rows=2, cols=2)
    va_tbl.style = 'Table Grid'
    add_label_cell(va_tbl.rows[0], 0, '방문교인')
    add_value_cell(va_tbl.rows[0], 1, data.get('visitors'))
    add_label_cell(va_tbl.rows[1], 0, '결석교인')
    add_value_cell(va_tbl.rows[1], 1, data.get('absences'))

    # === 공지사항 ===
    announcements = data.get('announcements')
    if announcements:
        add_section_heading(doc, '공지 및 토의')
        ann_tbl = doc.add_table(rows=1, cols=2)
        ann_tbl.style = 'Table Grid'
        add_label_cell(ann_tbl.rows[0], 0, '공지사항')
        add_value_cell(ann_tbl.rows[0], 1, announcements)

    # 푸터
    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.space_before = Pt(18)
    run = footer.add_run('솔리데오글로리아교인')
    run.font.size = Pt(9)
    run.font.name = FONT

    doc.save(output_path)
    return output_path
```

- [ ] **Step 2: 단독 테스트 — 더미 데이터로 DOCX 생성 확인**

```bash
cd journal_server
python -c "
from generate_docx import generate_journal_docx
data = {
    'dateStr': '2026. 03. 22', 'author': '문지영',
    'am_preacher': '김병혁 목사', 'am_time': '10:45 ~ 13:00',
    'am_title': '테스트 설교', 'am_scripture': '창 1:1',
    'am_pre': '시편 해설', 'am_hymns': '283장\n5장',
    'am_creed': '사도신경', 'am_sacrament': '-',
    'am_male': '34', 'am_female': '41', 'am_total': '75',
    'pm_prayer': '안 식 집사', 'pm_leader': '공정윤 강도사',
    'pm_time': '14:45 ~ 16:30', 'pm_title': '사사기 해설',
    'pm_scripture': '-', 'pm_hymns': '193(99편), 92(45편)',
    'pm_creed': '-', 'pm_male': '32', 'pm_female': '40', 'pm_total': '72',
    'visitors': '-', 'absences': '오전·오후: 이종민(독일)',
    'announcements': '테스트 공지',
    'study_classes': [
        {'department': '청년부 오전', 'time': '10:20-10:45', 'attendees': ['고수민','박솔민','허하민'],
         'attendance_count': 3, 'teacher': '정진수', 'content': '창세기 강설#95', 'material': '-',
         'absentees': [], 'absent_count': 0, 'note': '-'},
        {'department': '청소년 2부', 'time': '-', 'attendees': ['이서연','송예원','이수아'],
         'attendance_count': 3, 'teacher': '공정윤', 'content': '인간론 은혜언약', 'material': '-',
         'absentees': [], 'absent_count': 0, 'note': '-'}
    ]
}
generate_journal_docx(data, 'test_output.docx')
print('생성 완료: test_output.docx')
"
```

- [ ] **Step 3: Commit**

```bash
git add journal_server/generate_docx.py
git commit -m "feat: DOCX 일지 생성 엔진 (HWP 레이아웃 재현)"
```

---

### Task 6: Flask 서버 (Firebase 감시 + DOCX 생성)

**Files:**
- Create: `journal_server/server.py`
- Create: `journal_server/requirements.txt`

- [ ] **Step 1: requirements.txt 작성**

```
flask==3.1.0
python-docx==1.1.2
requests==2.32.3
```

- [ ] **Step 2: Flask 서버 작성**

Firebase를 10초마다 폴링하여 `generate_requested: true`인 일지 데이터를 감지하면 DOCX 생성.

```python
#!/usr/bin/env python3
"""
교회 일지 DOCX 생성 서버

Firebase에서 일지 생성 요청을 감시하고 DOCX 파일을 자동 생성합니다.
"""
import json
import logging
import os
import subprocess
import threading
import time
from datetime import datetime
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
OUTPUT_DIR = Path.home() / "Desktop"  # 기본 저장 위치: 바탕화면


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
            if data and data.get('generate_requested') and not data.get('generated'):
                log.info(f"일지 생성 요청 감지: {date_key}")

                # DOCX 생성
                filename = f"SDG일지_{date_key}.docx"
                output_path = OUTPUT_DIR / filename
                generate_journal_docx(data, str(output_path))

                # 생성 완료 플래그
                requests.patch(
                    f"{FB_URL}/journal/{date_key}.json",
                    json={"generated": True, "generate_requested": False},
                    timeout=10
                )

                log.info(f"일지 생성 완료: {output_path}")

                # macOS 알림
                subprocess.run([
                    "osascript", "-e",
                    f'display notification "일지가 바탕화면에 저장되었습니다." with title "교회 일지 생성 완료" sound name "Glass"'
                ], check=False)

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
    """수동 생성 엔드포인트 (디버깅용)"""
    data = request.json
    if not data or not data.get("date"):
        return jsonify({"error": "date required"}), 400

    filename = f"SDG일지_{data['date']}.docx"
    output_path = OUTPUT_DIR / filename
    generate_journal_docx(data, str(output_path))
    return jsonify({"status": "ok", "path": str(output_path)})


def main():
    log.info(f"교회 일지 서버 시작 (저장 위치: {OUTPUT_DIR})")

    # Firebase 폴링 스레드
    t = threading.Thread(target=polling_loop, daemon=True)
    t.start()

    # Flask 서버 (포트 5050)
    app.run(host="0.0.0.0", port=5050, debug=False)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 테스트 — 서버 실행 후 Firebase에 테스트 데이터 넣어서 DOCX 생성 확인**

```bash
cd journal_server
pip install -r requirements.txt
python server.py
```

별도 터미널에서:
```bash
curl -X PUT "https://sdgc-ae7f9-default-rtdb.asia-southeast1.firebasedatabase.app/journal/test.json" \
  -H "Content-Type: application/json" \
  -d '{"generate_requested":true,"generated":false,"dateStr":"2026.03.22","author":"문지영","am_preacher":"김병혁 목사"}'
```

바탕화면에 DOCX 생성되고 macOS 알림 뜨는지 확인

- [ ] **Step 4: Commit**

```bash
git add journal_server/
git commit -m "feat: Flask 서버 — Firebase 감시 + DOCX 자동 생성"
```

---

### Task 7: Mac 자동 시작 설정

**Files:**
- Create: `journal_server/install.sh`

- [ ] **Step 1: 설치 + LaunchAgent 스크립트**

```bash
#!/bin/bash
# 교회 일지 서버 설치 스크립트

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_PATH="$HOME/Library/LaunchAgents/com.sdg.journal-server.plist"
VENV_DIR="$SCRIPT_DIR/venv"

echo "=== 교회 일지 서버 설치 ==="

# 가상환경 생성
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"

# LaunchAgent plist 생성
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

echo "✅ 설치 완료!"
echo "- 서버가 자동으로 시작되었습니다"
echo "- Mac 재부팅 후에도 자동 실행됩니다"
echo "- 일지는 바탕화면에 저장됩니다"
echo ""
echo "상태 확인: curl http://localhost:5050/health"
echo "중지: launchctl unload $PLIST_PATH"
```

- [ ] **Step 2: 실행 권한 부여 및 설치 테스트**

```bash
chmod +x journal_server/install.sh
./journal_server/install.sh
curl http://localhost:5050/health
```

- [ ] **Step 3: Commit**

```bash
git add journal_server/install.sh
git commit -m "feat: Mac 자동 시작 설치 스크립트 (LaunchAgent)"
```

---

## Chunk 3: 통합 테스트

### Task 8: 전체 플로우 통합 테스트

- [ ] **Step 1: 폰 앱에서 주보 PDF 업로드 + 추출 확인**
- [ ] **Step 2: 카톡 메시지 붙여넣기 + AI 파싱 확인**
- [ ] **Step 3: "일지 생성 요청" 버튼 → Firebase 저장 확인**
- [ ] **Step 4: 맥북 서버가 감지 → DOCX 생성 → macOS 알림 확인**
- [ ] **Step 5: 생성된 DOCX를 Word/Pages에서 열어 레이아웃 확인**
- [ ] **Step 6: HWP 서식과 비교하여 레이아웃 일치 여부 확인**

### Task 9: GitHub Push + 배포

- [ ] **Step 1: 전체 변경사항 Push**

```bash
git push origin main
```

GitHub Pages 자동 배포 → 폰에서 접속하여 최종 확인

- [ ] **Step 2: 완료**
