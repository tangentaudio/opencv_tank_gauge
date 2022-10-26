#!/usr/bin/python3

import sqlite3
from flask import Flask, render_template, jsonify, request, redirect, url_for, Response, g
from gaugecv import GaugeCV
import picamera
import time
from random import uniform

app = Flask(__name__, static_url_path='', static_folder='static', template_folder='templates')

DATABASE = 'db/gauge.db'

cv = GaugeCV()
  
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def update_db(query, args=()):
    db = get_db()
    cur = db.cursor()
    rv = cur.execute(query, args)
    db.commit()
    cur.close()

def get_config_val(key):
    row = query_db("SELECT min,max,value FROM config WHERE key = ?", [str(key)], one=True)
    if row is not None:
        return row
    return None

def get_config_int(key, default=0):
    v = get_config_val(key)
    if v is not None:
        return int(v['value'])
    return default

def set_config_val(key, value):
    res = update_db("UPDATE config SET value = ? WHERE key = ?", [value, str(key)])

def get_config():
    rows = query_db("SELECT key,value FROM config")
    d = {}
    if rows is not None:
        for row in rows:
            d[row['key']] = row['value']
        
    return d
    
def template_slider(id, step=1.0):
    cfg = get_config_val(id)
    
    return '''{{
    min: {min},
    max: {max},
    value: {value},
    step: {step},
    animate: "slow",
    orientation: "horizontal",
    change: function(event, ui) {{ setconfig(event, ui, "{id}") }}
    }}'''.format(min=cfg['min'], max=cfg['max'], value=cfg['value'], step=step, id=id)


def gen_frames():
    streaming = True

    while streaming:
        try:
            frame = cv.get_encoded()
            if frame is None:
                frame = cv.get_error_image_encoded()
                
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

                    
        except GeneratorExit:
            streaming = False

    print("Done streaming.")

    
@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/setconfig')
def slide():
    id = request.args.get('id')
    value = request.args.get('value')
    set_config_val(id, value)

    with app.app_context():
        cv.set_config(get_config())
        
    return value

@app.route('/')
def current_level():
    avg, update_time = cv.get_avg()

    if avg is not None:
        return jsonify(level=round(avg, 1), update_time=update_time)
    
    return jsonify(error="No level reading available")

@app.route('/random_test')
def random_level():
    time.sleep(4)
    level=round(uniform(0.0, 100.0), 1)
    print("Returning random level {l}".format(l=level))
    return jsonify(level=level)
    
@app.route('/tune')
def index():
    return render_template('tune.html')


if __name__ == '__main__':
    app.jinja_env.globals.update(template_slider=template_slider)
    with app.app_context():
        cv.set_config(get_config())

    app.run(debug=False, host='0.0.0.0', port=8080)

    

