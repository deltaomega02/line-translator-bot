# LINE 한↔일 실시간 번역 + 한국어 튜터 봇

LINE 대화방의 한국어↔일본어 메시지를 실시간 상호 번역하고,
한국어 학습자에게 문장 교정 피드백을 제공하는 봇. **GCP Cloud Functions 서버리스로 운영 중.**

## 특징
- 한↔일 자동 감지 번역 — ㅋㅋㅋ↔www 같은 문화적 표현까지 변환하는 프롬프트 설계
- 한국어 튜터 모드 — 학습자가 쓴 한국어 문장의 자연스러움을 점수화하고 교정 제안
- **서버리스 설계** — 상주 서버 없이 webhook 기반, 운영 비용 최소화
- **지연·비용 최적화** — 짧은 메시지 번역에 추론이 불필요하다고 판단, Gemini thinking budget을 0으로 설정
- LINE reply 토큰 만료를 고려한 짧은 API 타임아웃 + 빠른 폴백

## 스택
Python · GCP Cloud Functions · LINE Messaging API · Google Gemini

## 환경 변수
| 변수 | 설명 |
|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE 채널 액세스 토큰 |
| `LINE_CHANNEL_SECRET` | LINE 채널 시크릿 |
| `GEMINI_API_KEY` | Google Gemini API 키 |
| `USER_ID_SIWOO` / `USER_ID_ERIKO` | 대화 상대 LINE 사용자 ID |
