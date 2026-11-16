"""일본 생활 적합도 설문: 문항 정의와 점수 계산.

각 축은 5점 척도 문항 2개로 이루어진다. reverse=True 문항은 역채점한다.
축 점수는 0~100이며, 높을수록 그 특징을 편하게 느낀다는 뜻이다.

종합 점수는 두 가지 방식 중 하나로 계산한다.
- model.json이 있으면: train.py가 실제 응답으로 학습한 회귀 모델
- 없으면: 연구 결과를 참고해 정한 가중 평균 (WEIGHTS)
"""

import json
import os

SCALE = [
    (1, "전혀 아니다"),
    (2, "아니다"),
    (3, "보통"),
    (4, "그렇다"),
    (5, "매우 그렇다"),
]

COMFORT_THRESHOLD = 65
HARD_THRESHOLD = 40

AXES = [
    {
        "key": "distance",
        "group": "culture",
        "name": "사생활과 거리감",
        "items": [
            ("처음 만난 사람이 나이, 연애, 직업을 묻지 않아도 서운하지 않다.", False),
            ("친해지려면 서로 사적인 이야기를 빨리 터놓아야 한다고 생각한다.", True),
        ],
        "high": "서로 선을 지키는 관계가 편한 편이라, 초면에 사적인 질문을 삼가는 분위기와 잘 맞습니다.",
        "low": "친해지는 속도가 느리게 느껴질 수 있습니다. 사적인 질문은 상대가 먼저 꺼낼 때까지 기다리는 편이 안전합니다.",
    },
    {
        "key": "indirect",
        "group": "culture",
        "name": "혼네와 다테마에",
        "items": [
            ("상대가 속마음을 그대로 말하지 않고 예의상 좋게 말해도 괜찮다.", False),
            ("불만이 있으면 그 자리에서 직접 말해야 직성이 풀린다.", True),
        ],
        "high": "겉으로 하는 말과 속마음을 구분하는 방식을 배려로 받아들일 수 있습니다.",
        "low": "예의상 하는 말이 솔직하지 않다고 느껴져 답답할 수 있습니다. 직설적인 표현은 수위를 낮추는 연습이 도움이 됩니다.",
    },
    {
        "key": "refusal",
        "group": "culture",
        "name": "완곡한 거절 읽기",
        "items": [
            ("'검토해 보겠습니다' 같은 말에서 거절의 뜻을 눈치채는 편이다.", False),
            ("된다, 안 된다를 분명히 말해주지 않으면 답답하다.", True),
        ],
        "high": "돌려 말하는 거절을 알아듣는 편이라 오해가 적을 것입니다.",
        "low": "'좀 어렵겠네요', '검토해 보겠습니다'는 거절인 경우가 많습니다. 긍정으로 받아들여 기다리는 일이 생길 수 있습니다.",
    },
    {
        "key": "meiwaku",
        "group": "culture",
        "name": "폐 끼치지 않기 (메이와쿠)",
        "items": [
            ("지하철이나 식당 같은 공공장소에서 목소리와 행동을 조심하는 편이다.", False),
            ("규칙이 조금 불합리해 보여도 일단 지키는 편이다.", False),
        ],
        "high": "공공장소 예절과 규칙 준수에 익숙해 일상에서 부딪힐 일이 적습니다.",
        "low": "전철 안 통화, 쓰레기 분리 같은 세세한 규칙이 부담스러울 수 있습니다.",
    },
    {
        "key": "planning",
        "group": "culture",
        "name": "약속과 계획",
        "items": [
            ("약속은 며칠 전에 미리 잡는 것이 편하다.", False),
            ("'지금 나올래?' 같은 즉흥적인 만남을 더 좋아한다.", True),
        ],
        "high": "미리 일정을 잡는 방식이 편해, 약속 문화에 쉽게 적응할 수 있습니다.",
        "low": "즉흥적인 만남이 잘 성사되지 않아 아쉬울 수 있습니다. 며칠 앞서 약속을 잡는 습관이 필요합니다.",
    },
    {
        "key": "reply",
        "group": "culture",
        "name": "연락 속도",
        "items": [
            ("메시지 답장이 하루 넘게 걸려도 크게 신경 쓰이지 않는다.", False),
            ("답장이 늦으면 상대가 나를 멀리한다고 느낀다.", True),
        ],
        "high": "답장이 느려도 여유 있게 기다릴 수 있습니다.",
        "low": "답장이 몇 시간에서 며칠씩 걸리는 일이 흔합니다. 관계가 식었다는 신호가 아닌 경우가 많습니다.",
    },
    {
        "key": "warikan",
        "group": "culture",
        "name": "각자 계산 (와리캉)",
        "items": [
            ("친구와 식사한 뒤 1엔 단위까지 나눠 계산해도 정 없다고 느끼지 않는다.", False),
            ("가까운 사이라면 번갈아 사는 것이 자연스럽다고 생각한다.", True),
        ],
        "high": "정확히 나눠 내는 계산을 깔끔하다고 느끼는 편입니다.",
        "low": "친구 사이의 각자 계산이 차갑게 느껴질 수 있습니다. 일본에서는 서로 부담을 주지 않으려는 방식입니다.",
    },
    {
        "key": "context",
        "group": "culture",
        "name": "분위기 읽기",
        "items": [
            ("대화 중 침묵이 흘러도 불편하지 않다.", False),
            ("말하지 않아도 분위기를 보고 상대가 원하는 것을 알아차리는 편이다.", False),
        ],
        "high": "말보다 분위기로 전달되는 뜻을 잘 읽는 편입니다.",
        "low": "말로 하지 않는 기대를 놓치기 쉽습니다. 헷갈릴 때는 정중하게 되물어 확인하는 편이 좋습니다.",
    },
    {
        "key": "agreeableness",
        "group": "personality",
        "name": "친화성",
        "items": [
            ("다른 사람의 입장을 먼저 생각하고 맞춰주는 편이다.", False),
            ("의견이 다르면 양보하기보다 내 주장을 끝까지 밀어붙인다.", True),
        ],
        "high": "상대에게 맞추는 성향은 일본 거주 외국인의 적응과 관련이 있다고 보고된 특성입니다.",
        "low": "주장을 강하게 밀어붙이면 조화를 중시하는 자리에서 마찰이 생길 수 있습니다.",
    },
    {
        "key": "conscientiousness",
        "group": "personality",
        "name": "성실성",
        "items": [
            ("맡은 일은 세부적인 부분까지 꼼꼼하게 마무리한다.", False),
            ("계획을 세워도 자주 미루는 편이다.", True),
        ],
        "high": "꼼꼼함과 시간 엄수는 직장과 행정 절차에서 강점이 됩니다.",
        "low": "마감과 서류 절차가 엄격해, 미루는 습관이 있으면 부담이 커질 수 있습니다.",
    },
    {
        "key": "stability",
        "group": "personality",
        "name": "정서 안정성",
        "items": [
            ("낯선 환경에서도 비교적 마음이 편안하다.", False),
            ("작은 일에도 걱정이 많고 쉽게 불안해진다.", True),
        ],
        "high": "낯선 환경에서도 스트레스를 덜 받는 편입니다.",
        "low": "해외 생활 초반의 외로움과 불안이 크게 느껴질 수 있습니다. 한국어로 기댈 수 있는 관계를 미리 마련해 두세요.",
    },
    {
        "key": "cultural_empathy",
        "group": "personality",
        "name": "문화적 공감",
        "items": [
            ("다른 문화권 사람의 행동을 보면 그 이유를 이해해 보려고 한다.", False),
            ("나와 다른 방식으로 행동하는 사람을 보면 이해하기보다 답답함이 앞선다.", True),
        ],
        "high": "다른 문화의 행동 이유를 헤아리는 성향은 해외 적응 연구에서 예측력이 가장 큰 요인 중 하나입니다.",
        "low": "낯선 행동을 '틀렸다'가 아니라 '다르다'로 보는 연습이 적응에 가장 큰 도움이 됩니다.",
    },
    {
        "key": "motivation",
        "group": "personality",
        "name": "낯선 문화에 대한 흥미와 자신감",
        "items": [
            ("낯선 문화 속에서 지내는 것 자체가 즐겁다.", False),
            ("익숙하지 않은 문화의 생활 방식에도 적응할 자신이 있다.", False),
        ],
        "high": "낯선 문화를 즐기고 적응할 수 있다고 믿는 마음은 연구에서 적응을 가장 잘 설명한 요인입니다.",
        "low": "일본 생활 자체에 대한 흥미나 자신감이 낮은 편입니다. 단기 체류로 먼저 경험해 보는 것이 좋습니다.",
    },
    {
        "key": "social_initiative",
        "group": "personality",
        "name": "먼저 다가가기",
        "items": [
            ("새로운 모임에서 먼저 말을 거는 편이다.", False),
            ("모르는 사람들 사이에 있으면 조용히 있는 편이다.", True),
        ],
        "high": "먼저 다가가는 성향은 현지에서 관계를 만드는 데 유리합니다.",
        "low": "일본에서는 상대가 먼저 다가오는 일이 드뭅니다. 동아리나 모임처럼 정해진 틀이 있는 자리를 활용해 보세요.",
    },
    {
        "key": "openness",
        "group": "personality",
        "name": "새로운 경험에 대한 개방성",
        "items": [
            ("처음 보는 음식이나 방식을 일단 시도해 보는 편이다.", False),
            ("익숙한 방식이 바뀌면 불편해서 원래대로 하고 싶어진다.", True),
        ],
        "high": "새로운 방식을 시도해 보는 성향은 생활 전반의 적응에 도움이 됩니다.",
        "low": "생활 방식이 한꺼번에 바뀌는 것이 부담일 수 있습니다. 익숙한 음식과 습관을 일부 유지하는 것이 도움이 됩니다.",
    },
    {
        "key": "japanese",
        "group": "personality",
        "name": "일본어",
        "items": [
            ("일본어로 일상 대화를 할 수 있다.", False),
            ("일본어로 관공서나 병원 업무를 볼 수 있다.", False),
        ],
        "high": "언어 능력은 현지 적응과 꾸준히 관련이 확인된 요인입니다.",
        "low": "언어는 연습으로 바꿀 수 있는 요인입니다. 출국 전에 생활 회화와 행정 용어를 익혀 두면 적응이 크게 수월해집니다.",
    },
]

# 종합 점수에서 각 축이 차지하는 비중.
# 메타분석(Han 외 2022, Wilson 외 2013)에 보고된 효과 크기의 대략적인 순서를 따른 것이며,
# 논문의 계수를 그대로 옮긴 값은 아니다.
#   1.5  : 효과가 크다고 보고된 문화 관련 특성 (문화적 공감, 동기)
#   1.25 : 중간 크기 (외향성 계열, 개방성, 언어 능력)
#   1.0  : 작거나 중간 크기 (친화성, 성실성, 정서 안정성)
#   0.75 : 일본 문화 특징에 대한 선호. 수치로 검증한 연구를 찾지 못해 가장 낮게 둔다.
WEIGHTS = {
    "cultural_empathy": 1.5,
    "motivation": 1.5,
    "social_initiative": 1.25,
    "openness": 1.25,
    "japanese": 1.25,
    "agreeableness": 1.0,
    "conscientiousness": 1.0,
    "stability": 1.0,
}
DEFAULT_WEIGHT = 0.75

MODEL_PATH = os.environ.get(
    "MODEL_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.json"),
)

MID_TEXT ="크게 편하지도 불편하지도 않은 수준입니다. 상황에 따라 다르게 느낄 수 있습니다."


def build_questions():
    """폼에 그릴 문항 목록. 축이 한데 몰리지 않도록 첫 문항들, 둘째 문항들 순서로 섞는다."""
    questions = []
    for index in (0, 1):
        for axis in AXES:
            text, _ = axis["items"][index]
            questions.append({"id": f"{axis['key']}_{index}", "text": text})
    return questions


def parse_answers(form):
    """폼에서 1~5 사이의 응답만 골라 {문항 id: 점수}로 돌려준다."""
    answers = {}
    for question in build_questions():
        raw = form.get(question["id"], "")
        if raw in {"1", "2", "3", "4", "5"}:
            answers[question["id"]] = int(raw)
    return answers


def level_of(score):
    if score >= COMFORT_THRESHOLD:
        return "comfort"
    if score < HARD_THRESHOLD:
        return "hard"
    return "mid"


def axis_scores(answers):
    """축별 점수(0~100)를 {축 key: 점수}로 돌려준다."""
    scores = {}
    for axis in AXES:
        values = []
        for index, (_, reverse) in enumerate(axis["items"]):
            value = answers[f"{axis['key']}_{index}"]
            values.append(6 - value if reverse else value)
        mean = sum(values) / len(values)
        scores[axis["key"]] = round((mean - 1) / 4 * 100)
    return scores


def load_model(path=None):
    """학습된 모델 파일을 읽는다. 없거나 현재 문항 구성과 맞지 않으면 None."""
    try:
        with open(path or MODEL_PATH, encoding="utf-8") as file:
            model = json.load(file)
        if set(model["coef"]) != {axis["key"] for axis in AXES}:
            return None
        float(model["intercept"])
        return model
    except (OSError, ValueError, KeyError, TypeError):
        return None


MODEL = load_model()


def weighted_total(scores):
    weights = {key: WEIGHTS.get(key, DEFAULT_WEIGHT) for key in scores}
    return round(sum(scores[key] * weights[key] for key in scores) / sum(weights.values()))


def model_total(scores, model):
    """모델이 예측한 만족도(1~5)를 0~100으로 바꾼다."""
    predicted = model["intercept"] + sum(
        model["coef"][key] * scores[key] / 100 for key in scores
    )
    return round(min(100, max(0, (predicted - 1) / 4 * 100)))


def score(answers):
    """모든 문항에 응답한 answers를 받아 축별 점수와 종합 점수를 계산한다."""
    scores = axis_scores(answers)
    axes = []
    for axis in AXES:
        axis_score = scores[axis["key"]]
        level = level_of(axis_score)
        comment = {"comfort": axis["high"], "hard": axis["low"], "mid": MID_TEXT}[level]
        axes.append(
            {
                "key": axis["key"],
                "group": axis["group"],
                "name": axis["name"],
                "score": axis_score,
                "level": level,
                "comment": comment,
            }
        )

    if MODEL:
        total = model_total(scores, MODEL)
    else:
        total = weighted_total(scores)
    return {
        "total": total,
        "method": "model" if MODEL else "weights",
        "model_samples": MODEL.get("n") if MODEL else None,
        "level": level_of(total),
        "culture": [a for a in axes if a["group"] == "culture"],
        "personality": [a for a in axes if a["group"] == "personality"],
        "comfort": [a for a in axes if a["level"] == "comfort"],
        "hard": [a for a in axes if a["level"] == "hard"],
    }
