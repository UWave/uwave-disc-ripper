#!/usr/bin/env python3
from flask import Flask, render_template, jsonify
import fakemtx as mtx
app = Flask(__name__)

changer = mtx.Changer('/dev/sg4', True)


@app.route("/")
def hello():
    return render_template("index.html")


@app.route("/changer_status")
def get_status():
    return jsonify(changer.get_status())

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')
