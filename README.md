# LINE 한↔일 실시간 번역 + 한국어 튜터 봇

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white) ![Google Cloud](https://img.shields.io/badge/Google_Cloud-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white) ![LINE](https://img.shields.io/badge/LINE-00C300?style=for-the-badge&logo=line&logoColor=white) ![Google Gemini](https://img.shields.io/badge/Google_Gemini-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white)

LINE 대화방의 한국어↔일본어 메시지를 실시간으로 상호 번역하고, 한국어 학습자에게 교정 피드백을 주는 봇.
일본인 파트너와의 대화라는 실제 문제를 해결하기 위해 만들었고, **GCP Cloud Functions 서버리스로 매일 운영 중**이다.
Discord 상주 봇(WebSocket Gateway)으로 시작해 LINE으로 옮기며 서버리스로 재설계했다.

- 모델: `gemini-3.5-flash` (`main.py:21`)

## 기술 스택

| 영역 | 기술 | 용도 |
|---|---|---|
| 런타임 | GCP Cloud Functions (Python) | webhook 기반 서버리스 — 상주 서버 0원 |
| 메신저 | LINE Messaging API (line-bot-sdk) | webhook 수신, reply 전송 |
| AI | Google Gemini (google-genai SDK) | 번역·교정·검색 답변 |

## 동작 방식

```
[LINE 서버] 메시지 발생 → webhook POST
   ↓ (서명 검증: X-Line-Signature)
[Cloud Functions main.py]
   ├─ 한국어 메시지 → 일본어 번역 프롬프트
   ├─ 일본어 메시지 → 한국어 번역 프롬프트
   ├─ 학습자의 한국어 → 자연스러움 점수 + 교정 피드백 프롬프트
   └─ 검색 질의 → Gemini 검색 grounding
   ↓
[LINE reply API] 번역/피드백 전송
```

### 설계 포인트

- **왜 서버리스인가**: Discord 봇은 Gateway에 WebSocket 상시 연결이 필요해 상주 프로세스가 강제된다. LINE은 webhook push 방식이라 메시지가 올 때만 함수가 깨어나면 된다 — 개인 대화방 트래픽(하루 수십 건)에는 이벤트 단위 과금이 구조적으로 맞다.
- **추론 예산 튜닝**: 짧은 메시지 번역에 reasoning은 불필요 — `thinking_budget=0`으로 설정해 응답 지연과 비용을 동시에 절감. 단, 검색이 필요한 질의는 추론을 기본값으로 유지 — 작업 특성별로 모델 설정을 분리.
- **시간 제약 대응**: LINE reply 토큰은 유효 시간이 짧다 — Gemini 호출에 15초 타임아웃을 걸어, 늦은 성공 대신 빠른 실패를 택했다.
- **프롬프트의 문화 변환 규칙**: ㅋㅋㅋ↔w(笑), ㅜㅜ↔泣 같은 표현까지 메신저 톤에 맞게 변환. 실사용자(파트너) 피드백으로 계속 교정.

## 환경 변수

| 변수 | 설명 |
|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` / `LINE_CHANNEL_SECRET` | LINE 채널 인증 |
| `GEMINI_API_KEY` | Gemini API 키 |
| `USER_ID_SELF` / `USER_ID_PARTNER` | 대화 참여자 LINE 사용자 ID |

## 배포

배포에 필요한 의존성은 `requirements.txt` 에 있다(Cloud Functions 가 이 파일을 보고 설치한다).

```bash
gcloud functions deploy line-translator \
  --runtime python312 --trigger-http --entry-point callback \
  --set-env-vars LINE_CHANNEL_ACCESS_TOKEN=...,LINE_CHANNEL_SECRET=...,GEMINI_API_KEY=...
# 배포된 URL을 LINE Developers 콘솔의 Webhook URL로 등록
```
