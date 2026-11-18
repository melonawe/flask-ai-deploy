import os
import sqlite3

from flask import Flask, render_template, request

import feelings
import storage
import survey

app = Flask(__name__)

# python app.py(디버그 모드)는 감시용 프로세스와 실제 서버 프로세스 두 개를 띄운다.
# 감시용 프로세스에서까지 모델을 불러오면 메모리를 두 배로 쓰므로 실제 서버에서만 불러온다.
if __name__ != "__main__" or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    feelings.warm_up()

LIVED_KEYS = {key for key, _ in storage.LIVED_CHOICES}


@app.route("/", methods=["GET", "POST"])
def index():
    questions = survey.build_questions()
    answers = {}
    result = None
    error = None
    saved = False
    consent = False
    lived = None
    satisfaction = None
    selected_moods = []
    feeling = ""
    mood_result = None

    if request.method == "POST":
        answers = survey.parse_answers(request.form)
        selected_moods = feelings.clean_selected(request.form.getlist("mood"))
        feeling = feelings.clean_text(request.form.get("feeling"))
        consent = request.form.get("consent") == "yes"
        lived = request.form.get("lived") if request.form.get("lived") in LIVED_KEYS else None
        raw_satisfaction = request.form.get("satisfaction", "")
        satisfaction = int(raw_satisfaction) if raw_satisfaction in {"1", "2", "3", "4", "5"} else None

        missing = len(questions) - len(answers)
        if missing:
            error = f"아직 답하지 않은 문항이 {missing}개 있습니다."
        else:
            result = survey.score(answers)
            mood_result = feelings.analyze(selected_moods, feeling, result)
            if consent:
                try:
                    storage.save_response(
                        answers,
                        result["total"],
                        lived,
                        satisfaction,
                        selected_moods,
                        feeling,
                        mood_result["emotions"],
                    )
                    saved = True
                except (sqlite3.Error, OSError):
                    app.logger.exception("응답 저장 실패")

    return render_template(
        "index.html",
        questions=questions,
        scale=survey.SCALE,
        moods=feelings.MOODS,
        max_text_length=feelings.MAX_TEXT_LENGTH,
        lived_choices=storage.LIVED_CHOICES,
        answers=answers,
        result=result,
        error=error,
        consent=consent,
        saved=saved,
        lived=lived,
        satisfaction=satisfaction,
        selected_moods=selected_moods,
        feeling=feeling,
        mood_result=mood_result,
    )


if __name__ == "__main__":
    app.run(debug=True)
