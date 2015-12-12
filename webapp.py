#!/usr/bin/env python3
from flask import Flask, render_template, jsonify, url_for
import tasks
import config

app = Flask(__name__)
config.configure(app)


@app.route('/ripdisk')
def rip_disk():
    """Initializes the ripping of a disk"""
    task = tasks.rip_disk.apply_async()
    url = url_for('taskstatus', task_id=task.id)
    return "<a href=\"%s\">%s</a>" % (url, url)


@app.route('/status/<task_id>')
def taskstatus(task_id):
    """Shows info about the status of an on-going disk ripping"""
    task = tasks.rip_disk.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'current': 0,
            'total': 1,
            'status': 'Pending...'
        }
    elif task.state != 'FAILURE':
        response = {
            'state': task.state,
            'info': task.info
        }
        if 'result' in task.info:
            response['result'] = task.info['result']
    else:
        # something went wrong in the background job
        response = {
            'state': task.state,
            'current': 1,
            'total': 1,
            'status': str(task.info),  # this is the exception raised
        }
    return jsonify(response)


@app.route("/")
def hello():
    """Displays the main page"""
    return render_template("index.html")


@app.route("/changer_status")
def get_status():
    """Doesn't do anything right now"""
    # return jsonify({ripper.get_status()})
    return "nope"

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')
