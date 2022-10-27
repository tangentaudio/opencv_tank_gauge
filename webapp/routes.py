#!/usr/bin/python3

from flask import Flask, render_template, jsonify, request, redirect, url_for, Response, g
from flask import current_app as app
from random import uniform
from .models import db, Config
import redis


def set_redis_value(key, value):
    rd = redis.Redis(host='localhost', db=0)
    rd.set(key, value)

def get_redis_value(key):
    rd = redis.Redis(host='localhost', db=0)
    return rd.get(key)

def get_config_val(key):
    v = Config.query.filter(Config.key == key).first()

    print(v)
    if v is not None:
        return v
    return None

def get_config_int(key, default=0):
    v = get_config_val(key)
    if v is not None:
        return int(v.value)
    return default

def set_config_val(key, value):
    c = Config.query.filter(Config.key == key).first()
    c.value = value
    db.session.commit()

def copy_config_to_redis():
    rows = Config.query.all()

    for row in rows:
        set_redis_value('_config_' + row.key, row.value)
        
    
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
    }}'''.format(min=cfg.min, max=cfg.max, value=cfg.value, step=step, id=id)


def gen_frames():
    streaming = True
    while streaming:
        try:
            frame = get_redis_value('encoded_preview')
                
            if frame is not None:
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

    set_redis_value('_config_' + id, value)
        
    return value

@app.route('/')
def current_level():
    avg = float(get_redis_value('avg_level').decode('utf-8'))
    update_time = get_redis_value('avg_update_time').decode('utf-8')

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
    app.run(debug=False, host='0.0.0.0', port=8080)

    

