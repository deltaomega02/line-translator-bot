import os
import functions_framework
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

from google import genai
from google.genai import types

# ==========================================
# 설정
# ==========================================
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

USER_ID_SIWOO = os.environ.get("USER_ID_SIWOO", "" )
USER_ID_ERIKO = os.environ.get("USER_ID_ERIKO", "")

# Gemini 3.5 Flash (2026-05-19 GA). 1M 컨텍스트, 3.1 Pro급 성능.
MODEL_ID = "gemini-3.5-flash"

# ==========================================
# 초기화
# ==========================================
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
# 타임아웃(ms): Gemini 호출이 멈추면 빨리 실패시켜 LINE reply 토큰 만료를 방지
client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options=types.HttpOptions(timeout=15000),
)

# 번역/피드백: 짧은 LINE 메시지라 추론 불필요 → 사고 예산 0으로 지연/비용 최소화
# (주의: google-genai SDK는 아직 thinking_level 필드 미지원. thinking_budget 사용.)
THINKING_FAST = types.ThinkingConfig(thinking_budget=0)
# 검색은 기본값(medium) 사용 — 검색 결과 정리에 추론 필요

# ==========================================
# 프롬프트 정의
# ==========================================
PROMPT_KO_TO_JP = """韓国語を日本語に翻訳する通訳者です。

## ルール
- 意味を正確に伝えることが最優先
- カジュアルなタメ口で翻訳（LINEのメッセージなので）
- ㅋㅋㅋ/ㅎㅎ → w や 笑、ㅜㅜ/ㅠㅠ → 適切な表現に変換
- 翻訳文のみ出力。説明不要。"""

PROMPT_JP_TO_KO = """일본어를 한국어로 번역하는 통역사입니다.

## 규칙
- 의미를 정확하게 전달하는 것이 최우선
- 반말로 번역 (라인 메시지이므로)
- www/笑 → ㅋㅋㅋ, 泣 → ㅜㅜ 등 적절히 변환
- 번역문만 출력. 설명 불필요."""

PROMPT_ERIKO_KOREAN_FEEDBACK = """일본인이 한국어로 보낸 메시지를 확인하는 역할입니다.

## 규칙
- 의미가 통하고 자연스러우면 그냥 "👍" 하나만 출력
- 문법적으로 명확히 틀렸거나 의미 전달이 안 되는 경우에만 피드백:

✨ 이렇게 쓰면 더 자연스러워:
"(수정된 표현)"

- 사소한 어색함은 무시. 소통에 문제가 있는 경우만 지적."""


def detect_language(text: str) -> str:
    """언어 감지: ja(일본어), ko(한국어), unknown(판별 불가)"""
    has_ja = False
    has_ko = False
    has_cjk = False
    for ch in text:
        # 히라가나 / 가타카나
        if ('\u3040' <= ch <= '\u309F') or ('\u30A0' <= ch <= '\u30FF'):
            has_ja = True
        # 한글
        elif ('\uAC00' <= ch <= '\uD7A3') or ('\u3131' <= ch <= '\u3163'):
            has_ko = True
        # 한자 (CJK Unified Ideographs)
        elif '\u4E00' <= ch <= '\u9FFF':
            has_cjk = True
    if has_ja:
        return "ja"
    if has_ko:
        return "ko"
    if has_cjk:
        return "ja"  # 에리코 전용 봇이므로 한자만 있으면 일본어로 판정
    return "unknown"


def get_prompt_and_label(sender_id: str, user_msg: str) -> tuple[str, str]:
    """발신자와 메시지 내용에 따라 적절한 프롬프트와 이름 라벨 반환"""
    if sender_id == USER_ID_SIWOO:
        lang = detect_language(user_msg)
        if lang == "unknown":
            return "", ""
        return PROMPT_KO_TO_JP, "👦 시우"

    if sender_id == USER_ID_ERIKO:
        lang = detect_language(user_msg)
        if lang == "ja":
            return PROMPT_JP_TO_KO, "👩 에리"
        elif lang == "ko":
            return PROMPT_ERIKO_KOREAN_FEEDBACK, "👩 에리"
        return "", ""

    return "", ""


# ==========================================
# 웹훅 엔드포인트
# ==========================================
@functions_framework.http
def line_webhook(request):
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400

    return "OK"


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()
    sender_id = event.source.user_id

    # 디버그 커맨드
    if user_msg == "!내아이디":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"ID: {sender_id}"),
        )
        return

    # 미등록 사용자 무시
    if sender_id not in (USER_ID_SIWOO, USER_ID_ERIKO):
        return

    # =========================================================
    # !질문 / !質問 / !q : Google Search Grounding 검색 답변
    # =========================================================
    search_prefix = None
    for prefix in ("!질문", "!質問", "!q"):
        if user_msg.startswith(prefix):
            search_prefix = prefix
            break

    if search_prefix:
        query = user_msg[len(search_prefix):].strip()
        if not query:
            hint = "🔍 질문 내용을 입력해줘!\n예: !질문 오늘 서울 날씨" if sender_id == USER_ID_SIWOO \
                else "🔍 質問を入力してね!\n例: !질문 今日の東京の天気"
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=hint),
            )
            return

        search_instruction = "질문에 대해 검색 결과를 바탕으로 간결하고 정확하게 답변해. 한국어로 답변." \
            if sender_id == USER_ID_SIWOO \
            else "質問に対して検索結果をもとに簡潔かつ正確に答えてください。日本語で回答。"

        try:
            search_response = client.models.generate_content(
                model=MODEL_ID,
                contents=query,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    system_instruction=search_instruction,
                    # Gemini 3 권장: temperature/top_p/top_k 제거
                    # thinking_level은 기본 medium 사용
                ),
            )
            answer = (search_response.text or "").strip()
            if not answer:
                raise ValueError("empty search response")
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"🔍 검색 결과\n\n{answer}"),
            )
        except Exception as e:
            print(f"[ERROR] search, sender={sender_id}, query={query[:50]}, err={e}")
            err_msg = "검색 중 오류가 발생했어 😢" if sender_id == USER_ID_SIWOO \
                else "検索中にエラーが発生しました 😢"
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=err_msg),
            )
        return

    # =========================================================
    # 번역 / 한국어 피드백
    # =========================================================
    system_prompt, name_label = get_prompt_and_label(sender_id, user_msg)
    if not system_prompt:
        return

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=user_msg,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                thinking_config=THINKING_FAST,
                # Gemini 3 권장: temperature 제거 (기본값에 최적화됨)
            ),
        )

        bot_reply = (response.text or "").strip()
        if not bot_reply:
            raise ValueError("empty translation response")
        final_msg = f"{name_label}\n\n{bot_reply}"

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=final_msg),
        )
    except Exception as e:
        print(f"[ERROR] sender={sender_id}, msg={user_msg[:50]}, err={e}")
        err_msg = "번역 오류가 발생했어 😢" if sender_id == USER_ID_SIWOO \
            else "翻訳エラーが発生しました 😢"
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=err_msg),
            )
        except Exception:
            pass
