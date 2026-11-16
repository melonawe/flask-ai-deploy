"""지금 드는 감정: 선택한 감정 칩과 자유롭게 적은 글에서 감정을 찾는다.

글 분석은 단어가 들어 있는지만 보는 단순한 방식이다. 문맥이나 부정 표현은 이해하지 못한다.
"""

MAX_TEXT_LENGTH = 1000

MOODS = [
    {
        "key": "excited",
        "label": "기대돼요",
        "emoji": "✨",
        "keywords": ["기대", "설레", "설렘", "신나", "즐거", "행복", "두근"],
        "message": "기대하는 마음은 낯선 환경을 탐색하게 해주는 힘입니다. 아래 결과에서 점수가 낮은 항목만 미리 알아두면 실망할 일이 줄어듭니다.",
    },
    {
        "key": "anxious",
        "label": "걱정돼요",
        "emoji": "😟",
        "keywords": ["걱정", "불안", "무서", "두려", "긴장", "겁나", "겁이"],
        "message": "걱정은 대부분 '모르는 것'에서 옵니다. 아래 결과에서 힘들 수 있는 부분을 구체적으로 확인하면 막연한 불안이 줄어듭니다.",
    },
    {
        "key": "lonely",
        "label": "외로울 것 같아요",
        "emoji": "🌙",
        "keywords": ["외로", "쓸쓸", "혼자", "그리울", "그리워", "보고 싶", "향수"],
        "message": "일본에서는 친해지는 데 시간이 걸리는 편입니다. 취미 모임이나 한국인 커뮤니티를 먼저 찾아두면 초반의 외로움을 덜 수 있습니다.",
    },
    {
        "key": "confident",
        "label": "자신 있어요",
        "emoji": "💪",
        "keywords": ["자신 있", "자신있", "자신감", "잘할 수", "할 수 있"],
        "message": "자신감은 적응에 도움이 됩니다. 다만 직설적인 표현은 강하게 들릴 수 있으니, 아래 소통 관련 항목을 함께 확인해 보세요.",
    },
    {
        "key": "tired",
        "label": "지쳐 있어요",
        "emoji": "😮‍💨",
        "keywords": ["지쳐", "지친", "지쳤", "힘들", "피곤", "스트레스", "답답"],
        "message": "지친 상태에서는 작은 문화 차이도 크게 느껴집니다. 큰 결정은 조금 쉬고 난 뒤에 다시 살펴보는 것도 방법입니다.",
    },
    {
        "key": "unsure",
        "label": "잘 모르겠어요",
        "emoji": "🤔",
        "keywords": ["모르겠", "고민", "막막", "망설", "헷갈"],
        "message": "아직 마음이 정해지지 않았다면, 아래 항목별 결과를 판단 재료로 써 보세요. 편한 부분과 힘든 부분을 나눠 보는 것만으로도 정리가 됩니다.",
    },
]

MOOD_KEYS = {mood["key"] for mood in MOODS}


def clean_text(raw):
    return (raw or "").strip()[:MAX_TEXT_LENGTH]


def clean_selected(keys):
    return [mood["key"] for mood in MOODS if mood["key"] in set(keys)]


def analyze(selected, text):
    """선택한 감정과 글에서 찾은 감정을 합쳐 돌려준다."""
    found = []
    for mood in MOODS:
        chosen = mood["key"] in selected
        written = any(keyword in text for keyword in mood["keywords"])
        if chosen or written:
            found.append(
                {
                    "key": mood["key"],
                    "label": mood["label"],
                    "emoji": mood["emoji"],
                    "message": mood["message"],
                    "from_text": written and not chosen,
                }
            )
    return found
