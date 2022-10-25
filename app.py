#!/usr/bin/python3

import sqlite3
from flask import Flask, render_template, jsonify, request, redirect, url_for, Response, g
from picamera import PiCamera
from picamera.array import PiRGBArray
import numpy as np
import cv2

app = Flask(__name__, static_url_path='', static_folder='static', template_folder='templates')

DATABASE = 'db/gauge.db'

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

def rotate_image(image, angle):
  image_center = tuple(np.array(image.shape[1::-1]) / 2)
  rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
  result = cv2.warpAffine(image, rot_mat, image.shape[1::-1], flags=cv2.INTER_LINEAR)
  return result

def gen_frames():
    with PiCamera() as camera:
        streaming = True
            
        while streaming:        
            camera.resolution = (800,608)
            with PiRGBArray(camera, size=(800, 608)) as output:
                camera.capture(output, format="bgr")
                frame = output.array
                frame = cv2.rotate(frame, 1, cv2.ROTATE_180)

                with app.app_context():
                    crop_x1 = get_config_int('crop_x1')
                    crop_y1 = get_config_int('crop_y1')
                    crop_x2 = get_config_int('crop_x2')
                    crop_y2 = get_config_int('crop_y2')

                    slice_x1 = get_config_int('slice_x1')
                    slice_x2 = get_config_int('slice_x2')

                    rotate_angle = get_config_val('rotate_angle')['value']

                    frame = rotate_image(frame, -(rotate_angle))
                    frame = cv2.rectangle(frame, (crop_x1, crop_y1), (crop_x2, crop_y2), (192, 192,0), 1)

                    frame = cv2.rectangle(frame, (slice_x1, crop_y1), (slice_x2, crop_y2), (255,255,0), 1)

                ret, buffer = cv2.imencode('.jpg', frame)
                frame = buffer.tobytes()

                try:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                except GeneratorExit:
                    print("Generator exits, closing camera")
                    camera.close()
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
    return value

@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    app.jinja_env.globals.update(template_slider=template_slider)
    app.run(debug=False, host='0.0.0.0', port=8080)

