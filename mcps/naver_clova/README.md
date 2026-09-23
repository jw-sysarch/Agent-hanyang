# CLOVA Speech Lecture MCP Server

강의 녹음 STT 및 요약을 위한 MCP 서버입니다.  
Google ADK 에이전트에서 네이버 CLOVA Speech / CLOVA Studio API를 호출합니다.

---

## 제공 툴

| 툴 이름 | 설명 | 적합한 상황 |
|--------|------|------------|
| `transcribe_short` | 동기 STT (60초 이하) | 짧은 클립, 테스트 |
| `transcribe_lecture_submit` | 비동기 STT 제출 (강의 전체) | 수십 분~수 시간 강의 |
| `get_transcription_result` | 비동기 STT 결과 조회 | submit 후 폴링 |
| `summarize_lecture` | 강의 전사본 요약 | 전사 완료 후 |

---

## 시작하기

### 1. API 키 발급

**CLOVA Speech (STT)**
1. [네이버 클라우드 플랫폼](https://www.ncloud.com) 로그인
2. AI Services → CLOVA Speech → 이용 신청
3. 서비스 생성 후 Secret Key 복사

**CLOVA Studio (요약)**
1. AI Services → CLOVA Studio → 이용 신청
2. Playground에서 앱 생성
3. API 키 및 앱 ID 복사

### 2. .env 설정

```bash
cp .env.naver_clova.example .env.naver_clova
```

```.env
CLOVA_SPEECH_INVOKE_URL=실제_Invoke_URL
CLOVA_SPEECH_API_KEY=실제_키_입력
CLOVA_STUDIO_API_KEY=실제_API_키_입력
```

### 3. 실행

```bash
# Docker
cd ../..
docker compose up -d mcp-naver-clova

# 로컬 실행
pip install -r requirements.txt
python app.py
```

### 4. ADK 에이전트 연결

```python
# agent.py 예시
tools = [
    MCPToolset(
        connection_params=SseServerParams(url="http://localhost:8005/sse")
    )
]
```

---

## 강의 처리 플로우

```
[강의 오디오 파일]
       ↓
transcribe_lecture_submit(file_path, enable_diarization=True)
       ↓ (task_id 반환)
get_transcription_result(task_id)   ← 완료까지 자동 폴링
       ↓ (full_text 반환)
summarize_lecture(text)
       ↓
[요약문 + 키워드]
```

---

## 지원 오디오 형식

`.wav` `.mp3` `.flac` `.m4a` `.aac` `.ogg`

## 지원 언어

| 코드 (단문) | 코드 (장문) | 언어 |
|------------|------------|------|
| `Kor` | `ko-KR` | 한국어 |
| `Eng` | `en-US` | 영어 |
| `Jpn` | `ja-JP` | 일본어 |
