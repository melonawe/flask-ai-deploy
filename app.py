from flask import Flask, render_template, request

app = Flask(__name__)

positive_words = {"good", "great", "excellent", "amazing", "love"}
negative_words = {"bad", "terrible", "awful", "hate", "sad"}


@app.route("/", methods=["GET", "POST"])
def index():
    text = ""
    result = None
    positive_count = 0
    negative_count = 0

    if request.method == "POST":
        text = request.form.get("review", "").strip()

        if text:
            words = {word.strip(".,!?:;").lower() for word in text.split()}
            positive_count = len(words & positive_words)
            negative_count = len(words & negative_words)

            if positive_count > negative_count:
                result = "POSITIVE"
            elif negative_count > positive_count:
                result = "NEGATIVE"
            else:
                result = "NEUTRAL / UNKNOWN"

    return render_template(
        "index.html",
        text=text,
        result=result,
        positive_count=positive_count,
        negative_count=negative_count,
    )


if __name__ == "__main__":
    app.run(debug=True)
