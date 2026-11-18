"""지금 드는 감정: 선택한 감정 칩과 자유롭게 적은 글에서 감정을 찾아 일본 생활 적응과 연결한다.

글 분석 방식은 두 가지다.
- KOTE 모델 (searle-j/kote_for_easygoing_people): 한국어 댓글 5만 개로 학습한 44개 감정 분류기.
  transformers와 torch가 설치되어 있고 EMOTION_MODEL이 "off"가 아니면 사용한다.
- 단어 찾기: 모델을 쓸 수 없을 때의 대체 방식. 문맥이나 부정 표현은 이해하지 못한다.

KOTE의 44개 감정 중 일본 생활 적응과 관련된 것만 아래 7가지 감정 묶음으로 모은다.
감정은 종합 점수에 반영하지 않는다. 감정과 적응의 관계를 수치로 확인한 근거가 없기 때문이다.
대신 각 감정 묶음과 관련된 설문 항목을 연결해, 그 항목 점수에 맞는 조언을 보여준다.
"""

import logging
import os
import threading

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 1000
MODEL_NAME = os.environ.get("EMOTION_MODEL_NAME", "searle-j/kote_for_easygoing_people")
# 0.3으로 시험했을 때 한 문장에서 감정이 4~5개씩 잡혀 0.5로 올렸다.
MODEL_THRESHOLD = 0.5

MOODS = [
    {
        "key": "excited",
        "label": "기대돼요",
        "emoji": "✨",
        "kote": ["기대감", "즐거움/신남", "신기함/관심", "행복", "기쁨"],
        "keywords": ["기대", "설레", "설렘", "신나", "즐거", "행복", "두근"],
        "axes": ["motivation", "openness"],
        "message": "기대하는 마음은 낯선 환경을 탐색하게 해주는 힘입니다.",
    },
    {
        "key": "anxious",
        "label": "걱정돼요",
        "emoji": "😟",
        "kote": ["불안/걱정", "공포/무서움", "부담/안_내킴"],
        "keywords": ["걱정", "불안", "무서", "두려", "긴장", "겁나", "겁이"],
        "axes": ["stability", "japanese"],
        "message": "걱정은 대부분 '모르는 것'에서 옵니다. 힘들 수 있는 부분을 구체적으로 알면 막연한 불안이 줄어듭니다.",
    },
    {
        "key": "lonely",
        "label": "외로울 것 같아요",
        "emoji": "🌙",
        "kote": ["서러움", "슬픔", "절망"],
        "keywords": ["외로", "쓸쓸", "혼자", "그리울", "그리워", "보고 싶", "향수"],
        "axes": ["social_initiative", "distance"],
        "message": "일본에서는 친해지는 데 시간이 걸리는 편이라, 처음 몇 달의 외로움은 흔한 일입니다.",
    },
    {
        "key": "frustrated",
        "label": "답답해요",
        "emoji": "😤",
        "kote": ["불평/불만", "화남/분노", "짜증", "어이없음", "의심/불신"],
        "keywords": ["답답", "짜증", "화나", "화가", "이해가 안", "이해 안"],
        "axes": ["indirect", "refusal"],
        "message": "일본에서 느끼는 답답함은 돌려 말하는 소통 방식에서 오는 경우가 많습니다.",
    },
    {
        "key": "confident",
        "label": "자신 있어요",
        "emoji": "💪",
        "kote": ["뿌듯함", "안심/신뢰", "비장함", "편안/쾌적"],
        "keywords": ["자신 있", "자신있", "자신감", "잘할 수", "할 수 있"],
        "axes": ["cultural_empathy", "indirect"],
        "message": "자신감은 적응에 도움이 됩니다. 다만 직설적인 표현은 일본에서 강하게 들릴 수 있습니다.",
    },
    {
        "key": "tired",
        "label": "지쳐 있어요",
        "emoji": "😮‍💨",
        "kote": ["힘듦/지침", "귀찮음", "지긋지긋", "패배/자기혐오"],
        "keywords": ["지쳐", "지친", "지쳤", "힘들", "피곤", "스트레스"],
        "axes": ["stability", "conscientiousness"],
        "message": "지친 상태에서는 작은 문화 차이도 크게 느껴집니다. 큰 결정은 조금 쉬고 난 뒤에 다시 살펴보는 것도 방법입니다.",
    },
    {
        "key": "unsure",
        "label": "잘 모르겠어요",
        "emoji": "🤔",
        "kote": ["당황/난처"],
        "keywords": ["모르겠", "고민", "막막", "망설", "헷갈"],
        "axes": ["motivation"],
        "message": "아직 마음이 정해지지 않았다면, 편한 부분과 힘든 부분을 나눠 보는 것만으로도 정리가 됩니다.",
    },
]

MOOD_KEYS = {mood["key"] for mood in MOODS}
POSITIVE = {"excited", "confident"}
NEGATIVE = {"anxious", "lonely", "frustrated", "tired"}

# 감정 묶음과 관련 항목의 점수가 낮을 때 덧붙이는 일본 생활 조언
AXIS_ADVICE = {
    "japanese": "일본어 점수가 낮게 나왔습니다. 걱정의 상당 부분이 언어에서 올 수 있으니, 관공서·병원·집 계약 같은 생활 일본어부터 준비해 두면 불안이 크게 줄어듭니다.",
    "stability": "낯선 환경에서 불안을 느끼기 쉬운 편으로 나왔습니다. 출국 전에 한국어로 이야기할 수 있는 사람과 연락 방법을 정해 두세요.",
    "social_initiative": "먼저 다가가는 편이 아닌 것으로 나왔습니다. 일본에서는 상대가 먼저 다가오는 일이 드무니, 동아리·취미 모임·직장 동기 모임처럼 정해진 틀이 있는 자리를 활용해 보세요.",
    "distance": "친해지는 속도가 느리게 느껴질 수 있는 성향입니다. 일본에서는 몇 번 만나도 거리를 두는 것이 보통이니, 거절로 받아들이지 않아도 됩니다.",
    "indirect": "직설적인 소통을 선호하는 편으로 나왔습니다. 일본에서는 불만을 바로 말하기보다 '조금 어려울 것 같은데요' 정도로 완곡하게 전하는 편이 관계에 유리합니다.",
    "refusal": "돌려 말하는 거절을 놓치기 쉬운 편입니다. '검토해 보겠습니다'는 거절인 경우가 많으니, 답이 애매하면 정중하게 되물어 확인하세요.",
    "motivation": "일본 생활 자체에 대한 흥미가 아직 크지 않은 편입니다. 장기 체류 전에 단기 방문이나 워킹홀리데이로 먼저 경험해 보는 것을 권합니다.",
    "openness": "익숙한 방식이 바뀌는 것이 부담일 수 있습니다. 익숙한 음식과 습관을 일부 유지하면 기대가 실망으로 바뀌는 것을 막을 수 있습니다.",
    "cultural_empathy": "다른 문화의 행동을 이해하기보다 답답함이 먼저 드는 편입니다. 낯선 행동을 '틀렸다'가 아니라 '다르다'로 보는 연습이 적응에 가장 큰 도움이 됩니다.",
    "conscientiousness": "일을 미루는 편으로 나왔습니다. 일본은 서류 마감과 절차가 엄격해서, 지친 상태에서 일이 밀리면 부담이 커질 수 있습니다.",
}
HARD_THRESHOLD = 40


class _KoteModel:
    """KOTE 모델을 처음 쓸 때 한 번만 불러온다. 불러오지 못하면 None을 돌려준다."""

    def __init__(self):
        self._lock = threading.Lock()
        self._pipe = None
        self._failed = False

    def enabled(self):
        return os.environ.get("EMOTION_MODEL", "kote").lower() != "off" and not self._failed

    def get(self):
        if not self.enabled():
            return None
        with self._lock:
            if self._pipe is None and not self._failed:
                try:
                    from transformers import pipeline

                    self._pipe = pipeline(
                        "text-classification",
                        model=MODEL_NAME,
                        top_k=None,
                        function_to_apply="sigmoid",
                        truncation=True,
                        max_length=512,
                        device=-1,
                    )
                except Exception:  # 라이브러리 미설치, 다운로드 실패, 메모리 부족 등
                    logger.warning("KOTE 모델을 불러오지 못해 단어 찾기로 대신합니다.", exc_info=True)
                    self._failed = True
            return self._pipe

    def predict(self, text):
        """{KOTE 감정 이름: 확률}을 돌려준다. 모델을 쓸 수 없으면 None."""
        pipe = self.get()
        if pipe is None:
            return None
        try:
            output = pipe(text)
        except Exception:
            logger.warning("KOTE 모델 예측 실패", exc_info=True)
            return None
        if output and isinstance(output[0], list):
            output = output[0]
        return {item["label"]: float(item["score"]) for item in output}


KOTE = _KoteModel()


def warm_up():
    """서버 시작 직후 모델을 미리 불러와 첫 사용자가 오래 기다리지 않게 한다."""
    if KOTE.enabled():
        threading.Thread(target=KOTE.get, daemon=True).start()


def clean_text(raw):
    return (raw or "").strip()[:MAX_TEXT_LENGTH]


def clean_selected(keys):
    return [mood["key"] for mood in MOODS if mood["key"] in set(keys)]


def _from_text(text):
    """글에서 찾은 {감정 묶음 key: 확률}, 화면용 상위 감정, 사용한 방식, 저장용 감정 점수."""
    if not text:
        return {}, [], None, {}

    scores = KOTE.predict(text)
    if scores is not None:
        groups = {}
        for mood in MOODS:
            best = max((scores.get(label, 0.0) for label in mood["kote"]), default=0.0)
            if best >= MODEL_THRESHOLD:
                groups[mood["key"]] = best
        ranked = sorted(
            ((label, score) for label, score in scores.items() if label != "없음"),
            key=lambda item: -item[1],
        )
        # 화면에는 뚜렷한 감정 3개까지만, 저장(학습용)에는 10% 이상인 것을 모두 남긴다.
        top = [{"label": label, "percent": round(score * 100)} for label, score in ranked[:3] if score >= 0.5]
        kept = {label: round(score * 100) for label, score in ranked if score >= 0.1}
        return groups, top, "model", kept

    groups = {
        mood["key"]: 1.0
        for mood in MOODS
        if any(keyword in text for keyword in mood["keywords"])
    }
    return groups, [], "keywords", {}


def analyze(selected, text, result=None):
    """선택한 감정과 글에서 찾은 감정을 합쳐, 설문 결과와 연결한 조언을 붙여 돌려준다.

    result는 survey.score()의 결과. 주면 감정과 관련된 항목 중 점수가 낮은 것에 조언을 붙인다.
    """
    text_groups, top, method, kept = _from_text(text)
    axis_scores = {}
    axis_names = {}
    if result:
        for axis in result["culture"] + result["personality"]:
            axis_scores[axis["key"]] = axis["score"]
            axis_names[axis["key"]] = axis["name"]

    found = []
    for mood in MOODS:
        chosen = mood["key"] in selected
        written = mood["key"] in text_groups
        if not (chosen or written):
            continue
        advice = []
        for key in mood["axes"]:
            score = axis_scores.get(key)
            if score is not None and score < HARD_THRESHOLD:
                advice.append({"name": axis_names[key], "score": score, "text": AXIS_ADVICE[key]})
        found.append(
            {
                "key": mood["key"],
                "label": mood["label"],
                "emoji": mood["emoji"],
                "message": mood["message"],
                "from_text": written and not chosen,
                "percent": round(text_groups[mood["key"]] * 100) if written and method == "model" else None,
                "advice": advice,
            }
        )

    keys = {mood["key"] for mood in found}
    positive, negative = len(keys & POSITIVE), len(keys & NEGATIVE)
    if not keys:
        balance = None
    elif positive and not negative:
        balance = "기대가 앞서는 상태"
    elif negative and not positive:
        balance = "부담이 앞서는 상태"
    elif positive and negative:
        balance = "기대와 걱정이 섞인 상태"
    else:
        balance = "아직 마음을 정하는 중인 상태"

    return {
        "moods": found,
        "top": top,
        "method": method,
        "balance": balance,
        "emotions": kept,
    }
