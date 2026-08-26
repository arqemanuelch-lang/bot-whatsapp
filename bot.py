import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "¡El Bot está activo!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)