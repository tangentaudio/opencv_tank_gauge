#!/usr/bin/python3

import argparse
from picamera import PiCamera
from picamera.array import PiRGBArray
from datetime import datetime
import time
import cv2
import numpy as np
import sys
import os
from homeassistant_api import Client,State


parser = argparse.ArgumentParser(prog='gauge.py')
parser.add_argument('--tune', help='Interactive tuning mode', action='store_true')
ns = parser.parse_args()

args = vars(ns)
print(args)

SINGLE_CYCLE=not args['tune']
SHOW_IMAGES=args['tune']

FRAMERATE=32
TICK_THRESH=58
SLICEX = 120
ROTATE_ANGLE=0

level_avg_win = []
AVG_POINTS = 25.0

api_url = "http://homeassistant.local:8123/api"
token = None

os.chdir(os.path.dirname(sys.argv[0]))

with open("token.hass", "r") as f:
    token = f.read().strip()

assert token is not None



def contour_area(contours):
    cnt_area = []
    for i in range(0,len(contours),1):
        cnt_area.append(cv2.contourArea(contours[i]))
    list.sort(cnt_area, reverse=True)
    return cnt_area

def interpolate(tick_contours, indicator_contours, image):
    tick_fp = [100.0,75.0,50.0,25.0,0.0]
    tick_yvals = []
    indicator_yval = 0

    image_h = image.shape[0]
    image_w = image.shape[1]
    legend_w = 75

    if len(tick_contours) < 5 or len(indicator_contours) < 1:
        return [None, image]
    
    tick_cnt_area = contour_area(tick_contours)
    for i in range(0, len(tick_contours), 1):
        tick_contour = tick_contours[i]
        if (cv2.contourArea(tick_contour) >= tick_cnt_area[4]):
            x,y,w,h = cv2.boundingRect(tick_contour)
            tick_yval = y + h//2
            tick_yvals.append(tick_yval)

    ind_cnt_area = contour_area(indicator_contours)
    for i in range(0, len(indicator_contours), 1):
        indicator_contour = indicator_contours[i]
        if (cv2.contourArea(indicator_contour) >= ind_cnt_area[0]):
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
    
    if len(level_avg_win) < AVG_POINTS:
        level_avg_win.append(level)
        print("Raw level is {:.1f}".format(level))
       
    else:

        avg_array = np.array(level_avg_win)
        mean = np.mean(avg_array)
        standard_deviation = np.std(avg_array)
        distance_from_mean = abs(avg_array - mean)

        max_deviations = 1.1
        not_outlier = distance_from_mean < max_deviations * standard_deviation
        no_outliers = avg_array[not_outlier]

        print("Removed outliers:")
        print(no_outliers)
        
        avg = np.mean(no_outliers)


        print("New average level is {:.1f}".format(avg))

        new_state = client.set_state (State(state="{:.1f}".format(avg), entity_id='sensor.oil_tank_level'))

        level_avg_win = []
        
        return True

    return False




with Client(api_url, token) as client:

    camera = PiCamera()
    camera.resolution = (800,608)
    camera.framerate = FRAMERATE

    raw_capture = PiRGBArray(camera)

    for frame in camera.capture_continuous(raw_capture, format="bgr", use_video_port=True):

        # crop and rotate the image to correct, then 180 degrees because of upside down camera
        image = rotate_image(frame.array, ROTATE_ANGLE)
        image = cv2.rotate(image, 1, cv2.ROTATE_180)
        image = image[0:574,320:520]

        # crop a slice to find the indicators
        cropped = image[0:574, SLICEX:SLICEX+20]

        if SHOW_IMAGES:
            preview = image.copy()

        # convert to an inverted threshold image to find the tick marks
        img_gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
        ret, thresh = cv2.threshold(img_gray, TICK_THRESH, 255, cv2.THRESH_BINARY)
        thresh_inv = cv2.bitwise_not(thresh)

        if SHOW_IMAGES:
            im = cv2.cvtColor(thresh_inv, cv2.COLOR_GRAY2BGR)            
            preview[0:cropped.shape[0], SLICEX:SLICEX+cropped.shape[1]] = im
        
        # find contours that represent the tick marks
        tick_contours, tick_hierarchy = cv2.findContours(image=thresh_inv, mode=cv2.RETR_TREE, method=cv2.CHAIN_APPROX_NONE)

        # find the red indicator with a mask and range
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lower_red = np.array([145,112,0])
        upper_red = np.array([179,255,255])
        redmask = cv2.inRange(hsv, lower_red, upper_red)
        res = cv2.bitwise_and(image, image, mask= redmask)
        res = cv2.blur(res, (4,4), cv2.BORDER_DEFAULT)

        ind_gray = cv2.cvtColor(res, cv2.COLOR_BGR2GRAY)
        ret, ind_thresh = cv2.threshold(ind_gray, 1, 10, cv2.THRESH_BINARY)

        # find contours for the indicator
        ind_contours, ind_hierarchy = cv2.findContours(image=ind_thresh, mode=cv2.RETR_TREE, method=cv2.CHAIN_APPROX_SIMPLE)

        level, gauge = interpolate(tick_contours, ind_contours, image)

        if SHOW_IMAGES:
            if (len(ind_contours) >= 1):
                print(cv2.contourArea(ind_contours[0]))
                x,y,w,h = cv2.boundingRect(ind_contours[0])
                
                cv2.rectangle(preview, (x,y), (x+w, y+h), (0,0,255), 2)

            cv2.imshow("Preview", preview)
        

        
        if level is not None:
            if update_level(client, level):
                cv2.imwrite("/var/www/html/gauge.png", gauge)

                if SHOW_IMAGES:
                    cv2.imshow("Gauge", gauge)
                
                if SINGLE_CYCLE:
                    break

        key = cv2.waitKey(1) & 0xFF
        raw_capture.truncate(0)
        if key == ord("q"):
            break





