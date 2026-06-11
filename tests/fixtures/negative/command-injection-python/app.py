import subprocess
from flask import Flask, request

app = Flask(__name__)


@app.post("/resize")
def resize_image():
    filename = request.form["filename"]
    subprocess.run(["convert", filename, "/tmp/output.png"], check=True)
    return {"ok": True}
