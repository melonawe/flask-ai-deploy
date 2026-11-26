"""저장된 실제 응답으로 종합 점수 모델을 학습한다.

    pip install -r requirements-train.txt
    python train.py

일본에 살아 본 응답자의 축별 점수(입력)로 생활 만족도 1~5(정답)를 예측하는
릿지 회귀를 학습하고, 계수를 model.json에 저장한다. 앱은 이 파일이 있으면
가중 평균 대신 모델로 종합 점수를 계산한다. 서버에는 scikit-learn이 필요 없다.

데이터가 부족하거나 교차 검증 성능이 기준에 못 미치면 모델을 저장하지 않는다.
"""

import json
import sys
from datetime import datetime, timezone

import storage
import survey

MIN_SAMPLES = 100
MIN_R2 = 0.05
FOLDS = 5


def collect():
    """학습에 쓸 수 있는 응답만 골라 (입력 행렬, 정답 목록)으로 돌려준다."""
    question_ids = survey.question_ids()
    keys = survey.ALL_AXIS_KEYS
    features, targets = [], []
    for row in storage.load_responses():
        if row["lived"] not in ("under1", "over1") or row["satisfaction"] is None:
            continue
        if row["version"] != survey.SURVEY_VERSION or set(row["answers"]) != question_ids:
            continue  # 문항 문구나 구성이 달랐던 예전 응답
        scores = survey.axis_scores(row["answers"])
        features.append([scores[key] / 100 for key in keys])
        targets.append(row["satisfaction"])
    return keys, features, targets


def main():
    keys, features, targets = collect()
    count = len(targets)
    print(f"학습에 쓸 수 있는 응답: {count}개 (거주 경험과 만족도를 적은 응답)")
    if count < MIN_SAMPLES:
        print(f"최소 {MIN_SAMPLES}개가 필요합니다. 모델을 만들지 않았습니다.")
        return 1

    from sklearn.linear_model import RidgeCV
    from sklearn.model_selection import KFold, cross_val_score

    model = RidgeCV(alphas=[0.1, 1.0, 10.0, 100.0])
    folds = KFold(n_splits=FOLDS, shuffle=True, random_state=0)
    r2 = cross_val_score(model, features, targets, cv=folds, scoring="r2").mean()
    print(f"교차 검증 R²: {r2:.3f} (0이면 평균만 찍는 것과 같음)")
    if r2 < MIN_R2:
        print(f"R²가 {MIN_R2} 미만이라 가중 평균보다 낫다고 볼 수 없습니다. 모델을 만들지 않았습니다.")
        return 1

    model.fit(features, targets)
    payload = {
        "intercept": float(model.intercept_),
        "coef": {key: float(value) for key, value in zip(keys, model.coef_)},
        "n": count,
        "cv_r2": round(float(r2), 3),
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with open(survey.MODEL_PATH, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    print(f"모델을 저장했습니다: {survey.MODEL_PATH}")
    for key, value in sorted(payload["coef"].items(), key=lambda item: -abs(item[1])):
        print(f"  {key:20s} {value:+.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
