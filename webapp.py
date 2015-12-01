#!/usr/bin/env python3
from flask import Flask, render_template, jsonify
import fakemtx as mtx
from configparser import SafeConfigParser
import os

app = Flask(__name__)
config = SafeConfigParser()
config.read(['diskripper.conf', os.path.expanduser('~/.config/diskripper.conf')])

for key in config['flask']:
    app.config[key] = config['flask'][key]

for section in config:
    if section != 'flask':
        app.config[section] = {}
        for key in config[section]:
            app.config[section][key] = config[section][key]

app.logger.info("Examining the state of the changer...")
changer = mtx.Changer(app.config['ripper']['changer'], True)


@app.route("/")
def hello():
    return render_template("index.html")


@app.route("/changer_status")
def get_status():
    return jsonify(changer.get_status())

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')
