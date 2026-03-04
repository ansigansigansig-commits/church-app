# 주일 출석부 앱 (솔리데오글로리아교회)

## 프로젝트 개요
- 단일 HTML 파일 앱 (`주일출석부_v2.html`)
- Netlify 배포: https://zippy-horse-27bf91.netlify.app
- Firebase Realtime DB 동기화 (출석 데이터만)

## Firebase
- 프로젝트: sdgc
- DB URL: https://sdgc-ae7f9-default-rtdb.asia-southeast1.firebasedatabase.app
- REST API 방식 사용 (CDN 없음)
- 5초마다 폴링으로 출석 데이터 동기화

## 주요 기능
- 출석 입력: 날짜/오전오후 세션별 출석 체크
- 일지: 주보 PDF 업로드 → Claude API로 자동 추출 → Word/PDF 생성
- 명단: 89명 교인 관리 (추가/삭제)
- 통계: 출석 현황 차트
- 설정: Apps Script URL, Claude API 키, 엑셀 다운로드

## 알려진 이슈 (전체 해결됨)
- 총 인원 집계 0 표시 → normalizeFirebaseData() + null 가드
- 미정의 함수 5개(handleJournalPdf, saveApiKey, jCalcTotal, setExcelRange, downloadExcel) → 구현 완료
- localStorage 키 불일치(sdgScriptUrl) → 통일
- 일지 세션키 불일치(_am/_pm → _오전/_오후) → 수정
- markAllPresent() Firebase 미동기화 → syncOne 추가
- showSaveBadge() 메시지 파라미터 무시 → 수정
- switchView() implicit event 의존 → querySelector 방식으로 변경

## 기술 스택
- 순수 HTML/CSS/JS (프레임워크 없음)
- Firebase REST API (출석 동기화)
- docx.js CDN (Word 파일 생성)
- Claude API (주보 PDF 추출)
- Google Apps Script (구글시트 백업, 선택사항)

## 배포
- Netlify 수동 드래그 앤 드롭
- index.html 단일 파일로 배포
