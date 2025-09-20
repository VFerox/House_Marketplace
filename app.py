from flask import Flask

app = Flask(__name__)

@app.route("/")
def index():
    return "hei"

@app.route("/Page1")
def page1():
    return "First Page"

@app.route("/Page2")
def page2():
    return "Second Page"






if __name__ == "__main__":
    app.run(debug=True)