"""IPIP-FFM 공개 데이터에서 한국·일본 응답자의 성격 점수 분포(기준값)를 만든다.

    python scripts/build_norms.py

데이터: Open Psychometrics IPIP-FFM (2016~2018, 약 101만 명, CC BY 4.0)
        Hugging Face 사본 Tetratics/2018-11-08-OpenPsychometrics-IPIP-FFM
결과: data/norms.json

우리 설문의 성격 항목 4개(먼저 다가가기, 친화성, 성실성, 정서 안정성)는
IPIP Big Five 50문항 중 2개씩을 한국어로 옮긴 것이다. 같은 2문항으로 이 데이터의
점수를 계산해야 비교가 성립하므로, 아래 ITEMS는 survey.py의 문항과 짝을 이룬다.
문항 번호와 채점 방향은 ipip.ori.org의 50문항 목록(Goldberg, 1992)을 따른다.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://datasets-server.huggingface.co/filter"
DATASET = "Tetratics/2018-11-08-OpenPsychometrics-IPIP-FFM"
SPLITS = ["train", "validation", "test"]
COUNTRIES = {"KR": "한국", "JP": "일본"}
PAGE = 100

# 우리 축 key: [(IPIP 열 이름, 역채점 여부), ...]
ITEMS = {
    "social_initiative": [("EXT5", False), ("EXT10", True)],
    "agreeableness": [("AGR4", False), ("AGR1", True)],
    "conscientiousness": [("CSN5", False), ("CSN8", True)],
    "stability": [("EST2", False), ("EST1", True)],
}
# 채점 방향을 데이터로 검증할 때 쓰는 요인별 전체 10문항의 방향 (+1/-1)
KEYS = {
    "EXT": [1, -1, 1, -1, 1, -1, 1, -1, 1, -1],
    "AGR": [-1, 1, -1, 1, -1, 1, -1, 1, 1, 1],
    "CSN": [1, -1, 1, -1, 1, -1, 1, -1, 1, 1],
    "EST": [-1, 1, -1, 1, -1, -1, -1, -1, -1, -1],
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "norms.json")


def fetch(split, country):
    where = f"\"country\"='{country}'"
    rows, offset = [], 0
    while True:
        query = urllib.parse.urlencode(
            {"dataset": DATASET, "config": "default", "split": split,
             "where": where, "offset": offset, "length": PAGE}
        )
        data = None
        for attempt in range(20):
            try:
                with urllib.request.urlopen(f"{API}?{query}", timeout=60) as response:
                    data = json.load(response)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
                data = {"error": str(error)}
            if "rows" in data:
                break
            time.sleep(15)  # 서버가 색인을 만드는 중이거나 일시적으로 응답하지 않음
        else:
            raise RuntimeError(data)
        rows += [item["row"] for item in data["rows"]]
        offset += PAGE
        if offset >= data["num_rows_total"]:
            return rows


def usable(row):
    """같은 IP에서 한 번만 낸 응답이고, 필요한 문항에 모두 답한 경우만 쓴다."""
    if row.get("IPC") != 1:
        return False
    for factor in KEYS:
        for i in range(1, 11):
            if row.get(f"{factor}{i}") not in (1, 2, 3, 4, 5):
                return False
    return True


def axis_score(row, items):
    values = [6 - row[col] if reverse else row[col] for col, reverse in items]
    return round((sum(values) / len(values) - 1) / 4 * 100)


def check_keys(rows):
    """방향이 같은 문항끼리는 양의 상관, 반대인 문항끼리는 음의 상관이어야 한다."""
    def corr(a, b):
        n = len(a); ma, mb = sum(a) / n, sum(b) / n
        cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
        va = sum((x - ma) ** 2 for x in a) ** 0.5
        vb = sum((y - mb) ** 2 for y in b) ** 0.5
        return cov / (va * vb)

    for factor, keys in KEYS.items():
        first = [row[f"{factor}1"] for row in rows]
        for i in range(2, 11):
            r = corr(first, [row[f"{factor}{i}"] for row in rows])
            expected = keys[0] * keys[i - 1]
            if r * expected <= 0:
                raise SystemExit(f"{factor}{i}의 채점 방향이 예상과 다릅니다 (r={r:.2f})")
    print("채점 방향 검증 통과: 4개 요인 x 10문항")


def distribution(scores):
    """가능한 점수(0~100)마다 '이 점수보다 낮은 사람 비율 + 같은 점수의 절반'을 백분위로 쓴다."""
    n = len(scores)
    levels = sorted(set(round((v - 1) / 4 * 100) for v in (1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5)))
    table = {}
    for level in levels:
        below = sum(1 for s in scores if s < level)
        same = sum(1 for s in scores if s == level)
        table[str(level)] = round((below + same / 2) / n * 100)
    return table


def main():
    result = {
        "source": "Open Psychometrics IPIP-FFM (2016-2018), Hugging Face: " + DATASET,
        "license": "CC BY 4.0",
        "items": {axis: [col for col, _ in items] for axis, items in ITEMS.items()},
        "countries": {},
    }
    all_rows = []
    for code, name in COUNTRIES.items():
        rows = []
        for split in SPLITS:
            fetched = fetch(split, code)
            print(f"{code} {split}: {len(fetched)}개", flush=True)
            rows += fetched
        rows = [row for row in rows if usable(row)]
        all_rows += rows
        print(f"{code}: 사용 가능한 응답 {len(rows)}개")
        entry = {"name": name, "n": len(rows), "axes": {}}
        for axis, items in ITEMS.items():
            scores = [axis_score(row, items) for row in rows]
            entry["axes"][axis] = {
                "mean": round(sum(scores) / len(scores), 1),
                "percentile": distribution(scores),
            }
        result["countries"][code] = entry

    check_keys(all_rows)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)
    print(f"저장했습니다: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
