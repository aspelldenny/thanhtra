import os
from flask import Flask, request

app = Flask(__name__)


@app.post("/resize")
def resize_image():
    filename = request.form["filename"]
    os.system(f"convert {filename} /tmp/output.png")
    return {"ok": True}
