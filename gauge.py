from picamera import PiCamera
from picamera.array import PiRGBArray
from datetime import datetime
import time
import cv2
import numpy as np
import os
from homeassistant_api import Client,State

SHOW=False
TICK_THRESH=52
SLICEX = 140


level_avg_win = []
AVG_POINTS = 50.0
last_avg = 0.0

api_url = "http://homeassistant.local:8123/api"
token = None
with open("token.hass", "r") as f:
    token = f.read().strip()

assert token is not None



def nothing(x):
    pass

def contour_area(contours):
    cnt_area = []
    for i in range(0,len(contours),1):
        cnt_area.append(cv2.contourArea(contours[i]))
    list.sort(cnt_area, reverse=True)
    return cnt_area

def draw_bounding_box(contours, image, number_of_boxes=1, color=(0,0,255)):
    cnt_area = contour_area(contours)
    for i in range(0,len(contours),1):
        cnt = contours[i]
        if (cv2.contourArea(cnt) > cnt_area[number_of_boxes]):
            x,y,w,h = cv2.boundingRect(cnt)

            dim = image.shape
            width = image.shape[1]

            ypos = y + h//2
            image=cv2.rectangle(image,(0,ypos),(width,ypos),color,2)

            font = cv2.FONT_HERSHEY_SIMPLEX
            image=cv2.putText(image, str(ypos), (0,ypos-4), font, 1, color, 2, cv2.LINE_AA) 

    return image

def interpolate(tick_contours, indicator_contours, image):
    tick_fp = [100.0,75.0,50.0,25.0,0.0]
    tick_yvals = []
    indicator_yval = 0

    image_h = image.shape[0]
    image_w = image.shape[1]
    legend_w = 75

    if len(tick_contours) < 6 or len(indicator_contours) < 2:
        return [None, image]
    
    tick_cnt_area = contour_area(tick_contours)
    for i in range(0, len(tick_contours), 1):
        tick_contour = tick_contours[i]
        if (cv2.contourArea(tick_contour) > tick_cnt_area[5]):
            x,y,w,h = cv2.boundingRect(tick_contour)
            tick_yval = y + h//2
            tick_yvals.append(tick_yval)

    ind_cnt_area = contour_area(indicator_contours)
    for i in range(0, len(indicator_contours), 1):
        indicator_contour = indicator_contours[i]
        if (cv2.contourArea(indicator_contour) > ind_cnt_area[1]):
            x,y,w,h = cv2.boundingRect(indicator_contour)
            indicator_yval = y + h//2

    tick_yvals.sort()

    if len(tick_yvals) == 5:

        font = cv2.FONT_HERSHEY_SIMPLEX

        for i in range(0, len(tick_yvals), 1):
            yval = tick_yvals[i]
            fpval = tick_fp[i]

            image=cv2.rectangle(image,(0,yval),(legend_w,yval),(0,255,0),2)

            image=cv2.putText(image, "{:.0f}%".format(fpval), (0,yval-4), font, 0.7, (0,255,0), 2, cv2.LINE_AA) 

            
        image=cv2.rectangle(image,(legend_w,0),(legend_w,image_h),(0,255,0),2)

        level = np.interp([indicator_yval], tick_yvals, tick_fp)[0]

        image=cv2.rectangle(image,(legend_w,indicator_yval),(image_w,indicator_yval),(0,0,255),3)
        image=cv2.putText(image, "{:.1f}%".format(level), (legend_w + 10,indicator_yval-5), font, 0.7, (0,0,255), 2, cv2.LINE_AA) 

        now = datetime.now()
        dt_string = now.strftime("%m/%d/%Y %H:%M:%S")        
        image=cv2.putText(image, dt_string, (0, image_h - 5), font, 0.5, (255,255,255), 2, cv2.LINE_AA) 

      
        
        return [level, image]


    return [None, image]

def rotate_image(image, angle):
  image_center = tuple(np.array(image.shape[1::-1]) / 2)
  rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
  result = cv2.warpAffine(image, rot_mat, image.shape[1::-1], flags=cv2.INTER_LINEAR)
  return result



def update_level(client, level):
    global level_avg_win
    global last_avg
    
    if len(level_avg_win) < AVG_POINTS:
        level_avg_win.append(level)
        print("Raw level is {:.1f}".format(level))
       
    else:
        sum = 0.0
        for i in range(0, len(level_avg_win), 1):
            sum = sum + level_avg_win[i]

        avg = sum / AVG_POINTS

        level_avg_win = []

        avg_r = float("{:.1f}".format(avg))
        lavg_r = float("{:1f}".format(last_avg))

        if avg_r != lavg_r:
            print("New average level is {:.1f}".format(avg))
            new_state = client.set_state (State(state="{:.1f}".format(avg), entity_id='sensor.oil_tank_level'))
            last_avg = avg

            return True
    return False




with Client(api_url, token) as client:

    camera = PiCamera()
    camera.resolution = (800,608)
    camera.framerate = 8

    raw_capture = PiRGBArray(camera)


    for frame in camera.capture_continuous(raw_capture, format="bgr", use_video_port=True):

        # crop and rotate the image 180 degrees
        image = frame.array[0:549,300:500]
        image = cv2.rotate(image, 1, cv2.ROTATE_180)
        
        # crop a slice to find the indicators
        cropped = image[0:549, SLICEX:160]

        # find the black tick lines using threshold
        img_gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
        ret, thresh = cv2.threshold(img_gray, TICK_THRESH, 255, cv2.THRESH_BINARY)

        # invert the threshold image
        thresh_inv = cv2.bitwise_not(thresh)

        # find contours that represent the tick marks
        tick_contours, tick_hierarchy = cv2.findContours(image=thresh_inv, mode=cv2.RETR_TREE, method=cv2.CHAIN_APPROX_NONE)

        # find the red indicator with a mask and range
        hsv = cv2.cvtColor(cropped, cv2.COLOR_BGR2HSV)
        lower_red = np.array([137,112,0])
        upper_red = np.array([179,255,255])
        redmask = cv2.inRange(hsv, lower_red, upper_red)
        res = cv2.bitwise_and(cropped, cropped, mask= redmask)

        ind_gray = cv2.cvtColor(res, cv2.COLOR_BGR2GRAY)
        ret, ind_thresh = cv2.threshold(ind_gray, 1, 10, cv2.THRESH_BINARY)

        # find contours for the indicator
        ind_contours, ind_hierarchy = cv2.findContours(image=ind_thresh, mode=cv2.RETR_TREE, method=cv2.CHAIN_APPROX_SIMPLE)


        level, gauge = interpolate(tick_contours, ind_contours, image)

        if level is not None:
            if update_level(client, level):
                cv2.imwrite("/var/www/html/gauge.png", gauge)
        if SHOW:
            # show final image
            cv2.imshow('Gauge', gauge)


        key = cv2.waitKey(1) & 0xFF
        raw_capture.truncate(0)
        if key == ord("q"):
            break
