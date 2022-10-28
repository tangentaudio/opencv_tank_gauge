#!/usr/bin/python3

from flask import Flask, render_template, jsonify, request, redirect, url_for, Response, g
from flask import current_app as app
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
        
    
def template_spinner(id, step=1.0, fmt='n'):
    cfg = get_config_val(id)
    return '''spinner({{
    min: {min},
    max: {max},
    step: {step},
    numberFormat: "{fmt}",
    stop: function(event, ui) {{ set_config_value(event, ui, "{id}") }}
    }}).val({value})'''.format(min=cfg.min, max=cfg.max, value=cfg.value, step=step, fmt=fmt, id=id)


def gen_frames():
    streaming = True
    rd = redis.Redis(host='localhost', db=0)
    sub = rd.pubsub()
    sub.subscribe('encoded_preview')
    
    while streaming:
        try:
            for msg in sub.listen():
                if msg['channel'].decode('utf-8') == 'encoded_preview':
                    frame = rd.get('encoded_preview')
                
                    if frame is not None:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        except GeneratorExit:
            streaming = False
            

    print("Done streaming.")

    
@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/set_config_value')
def api_set_config_value():
    id = request.args.get('id')
    value = request.args.get('value')
    print("{}={}".format(id,value))
    set_config_val(id, value)
    set_redis_value('_config_' + id, value)
        
    return value

@app.route('/api/get_level')
def api_get_level():
    avg = float(get_redis_value('avg_level').decode('utf-8'))
    update_time = get_redis_value('avg_update_time').decode('utf-8')

    if avg is not None:
        return jsonify(level=round(avg, 1), update_time=update_time)
    
    return jsonify(error="No level reading available")
    
@app.route('/tune')
def tune():
    return render_template('tune.html')

@app.route('/')
def preview():
    return render_template('preview.html')


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8080)

    

