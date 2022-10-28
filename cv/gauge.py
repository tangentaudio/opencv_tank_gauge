#!/usr/bin/python

import redis
from picamera import PiCamera
from picamera.array import PiRGBArray
import cv2
import numpy as np
from datetime import datetime
from threading import Thread
import time

class GaugeCV:

    REQUIRED_CONFIG_KEYS = \
        ['rotate_angle',
         'crop_x1',
         'crop_x2',
         'crop_y1',
         'crop_y2',
         'slice_x1',
         'slice_x2',
         'indicator_blur',
         'tick_blur',
         'tick_threshold',
         'indicator_threshold',
         'level_average_points',
         'level_max_deviation']

    def __init__(self):
        GaugeCV.REQUIRED_CONFIG_KEYS.sort()
        
        self.rd = redis.Redis(host='localhost', port=6379, db=0)
        
        self.level_avg_win = []
        self.config = {}
        self.camera = None
        self.cam_buf = None
        self.preview = None
        self.avg = 0.0
        self.avg_update_time = None

        self.mean = None
        self.std_dev = None
        self.no_outliers = None
        
        self.running = True

        t = Thread(target=self.thread_func)
        t.start()

    def stop(self):
        self.running = False
        
    def thread_func(self):
        have_config = False
        
        with PiCamera() as self.camera:
            self.camera.resolution = (800,608)
            with PiRGBArray(self.camera, size=(800, 608)) as self.cam_buf:
                if not self.get_config():
                    print("Config not available yet.")
                else:
                    have_config = True
                    
                while self.running:
                    if self.get_config():
                        if not have_config:
                            have_config = True
                            print("Got config from redis.")
                            
                        self.process_image()
                    else:
                        time.sleep(1)
                        
    def get_config(self):
        have_keys = []
        for key in GaugeCV.REQUIRED_CONFIG_KEYS:
            value = self.rd.get('_config_' + key)
            if value is not None:
                value = value.decode('utf-8')
                self.config[key] = float(value)
                have_keys.append(key)

        have_keys.sort()

        return GaugeCV.REQUIRED_CONFIG_KEYS == have_keys
                    
    def config_int(self, key, default=0):
        if key in self.config:
            return int(self.config[key])
        else:
            return default

    def contour_area(self, contours):
        cnt_area = []
        for i in range(0,len(contours),1):
            cnt_area.append(cv2.contourArea(contours[i]))
        list.sort(cnt_area, reverse=True)
        return cnt_area    

    def interpolate(self, tick_contours, indicator_contours, image):
        slice_x1 = self.config_int('slice_x1')
        slice_x2 = self.config_int('slice_x2')
        crop_x1 = self.config_int('crop_x1')
        crop_x2 = self.config_int('crop_x2')
        crop_y1 = self.config_int('crop_y1')
        
        tick_fp = [100.0,75.0,50.0,25.0,0.0]
        tick_yvals = []
        indicator_yval = 0

        image_h = image.shape[0]
        image_w = image.shape[1]
        legend_w = 25

        if len(tick_contours) < 5 or len(indicator_contours) < 1:
            return [None, image]

        tick_cnt_area = self.contour_area(tick_contours)
        for i in range(0, len(tick_contours), 1):
            tick_contour = tick_contours[i]
            if (cv2.contourArea(tick_contour) >= tick_cnt_area[4]):
                x,y,w,h = cv2.boundingRect(tick_contour)
                tick_yval = y + h//2
                tick_yvals.append(tick_yval)

        ind_cnt_area = self.contour_area(indicator_contours)
        for i in range(0, len(indicator_contours), 1):
            indicator_contour = indicator_contours[i]
            if (cv2.contourArea(indicator_contour) >= ind_cnt_area[0]):
                x,y,w,h = cv2.boundingRect(indicator_contour)
                indicator_yval = y + h//2

        tick_yvals.sort()

        if len(tick_yvals) == 5:

            font = cv2.FONT_HERSHEY_SIMPLEX

            for i in range(0, len(tick_yvals), 1):
                yval = tick_yvals[i] + crop_y1
                fpval = tick_fp[i]

                image=cv2.rectangle(image,(slice_x2,yval),(slice_x2 + legend_w,yval),(0,255,0),2)

                image=cv2.putText(image, "{:.0f}%".format(fpval), (slice_x2+legend_w,yval+10), font, 1.0, (0,255,0), 2, cv2.LINE_AA) 

            level = np.interp([indicator_yval], tick_yvals, tick_fp)[0]

            image=cv2.rectangle(image,(crop_x1-legend_w,indicator_yval+crop_y1),(crop_x2,indicator_yval + crop_y1),(0,0,255),3)
            image=cv2.putText(image, "{:.1f}%".format(level), (crop_x1-legend_w-100,indicator_yval+crop_y1+10), font, 1.0, (0,0,255), 2, cv2.LINE_AA) 

            now = datetime.now()
            dt_string = now.strftime("%m/%d/%Y %H:%M:%S")        
            image=cv2.putText(image, dt_string, (0, image_h - 5), font, 1.0, (32,32,32), 2, cv2.LINE_AA) 

            return [level, image]
        return [None, image]

    def rotate_image(self, image, angle):
      image_center = tuple(np.array(image.shape[1::-1]) / 2)
      rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
      result = cv2.warpAffine(image, rot_mat, image.shape[1::-1], flags=cv2.INTER_LINEAR)
      return result

    def preview_render_list(self, preview, l, x, y = 0, color=(0,0,0)):
        if preview is not None:
            pi = 0
            font = cv2.FONT_HERSHEY_SIMPLEX
            for pv in l:
                preview = cv2.putText(preview, "{:02d}: {:.2f}".format(pi, pv), (x, y + (pi+1) * 16), font, 0.5, color, 1, cv2.LINE_AA)
                pi = pi + 1
        
        return preview

    def preview_render_stats(self, preview, mean, std_dev, mean_clean):
        x = 600
        y = 0
        if preview is not None:
            font = cv2.FONT_HERSHEY_SIMPLEX
            preview = cv2.putText(preview, "MEAN: {:.2f}".format(mean), (x, y + 16), font, 0.5, (128,0,0), 1, cv2.LINE_AA)
            preview = cv2.putText(preview, "STD DEV: {:.2f}".format(std_dev), (x, y + 32), font, 0.5, (128,0,0), 1, cv2.LINE_AA)

            preview = cv2.putText(preview, "AVG: {:.2f}".format(mean_clean), (x, y + 48), font, 0.5, (0,0,128), 1, cv2.LINE_AA)
        return preview
    
    def average_level(self, level, preview):
        level_average_points = self.config_int('level_average_points')
        max_deviations = self.config['level_max_deviation']
        
        if len(self.level_avg_win) < level_average_points:
            self.level_avg_win.append(level)

            preview = self.preview_render_list(preview, self.level_avg_win, 0)

            if self.mean is not None and self.std_dev is not None and self.no_outliers is not None:
                preview = self.preview_render_list(preview, self.no_outliers, 100, 0, (64,0,0))
                preview = self.preview_render_stats(preview, self.mean, self.std_dev, self.avg)
                
        else:
            avg_array = np.array(self.level_avg_win)
            mean = np.mean(avg_array)
            standard_deviation = np.std(avg_array)
            distance_from_mean = abs(avg_array - mean)

            not_outlier = distance_from_mean <= max_deviations * standard_deviation
            no_outliers = avg_array[not_outlier]

            preview = self.preview_render_list(preview, self.level_avg_win, 0, 0)
            preview = self.preview_render_list(preview, no_outliers, 100, 0, (64,0,0))
            
            avg = np.mean(no_outliers)

            preview = self.preview_render_stats(preview, mean, standard_deviation, avg)

            self.mean = mean
            self.std_dev = standard_deviation
            self.no_outliers = no_outliers
            
            self.level_avg_win = []

            return avg, preview

        return None, preview

    def process_image(self):
        crop_x1 = self.config_int('crop_x1')
        crop_y1 = self.config_int('crop_y1')
        crop_x2 = self.config_int('crop_x2')
        crop_y2 = self.config_int('crop_y2')
        slice_x1 = self.config_int('slice_x1')
        slice_x2 = self.config_int('slice_x2')
        rotate_angle = self.config['rotate_angle']
        tick_blur = int(self.config['tick_blur'])
        indicator_blur = int(self.config['indicator_blur'])
        tick_threshold = self.config['tick_threshold']
        indicator_threshold = self.config['indicator_threshold']
        
        # capture a frame from the camera
        self.cam_buf.truncate(0)
        self.camera.capture(self.cam_buf, format="bgr")
        frame = self.cam_buf.array

        # crop and rotate the image to correct, then 180 degrees because of upside down camera
        image = self.rotate_image(frame, rotate_angle)
        image = cv2.rotate(image, 1, cv2.ROTATE_180)

        # create a preview image for the web stream
        preview = image.copy()

        # crop a slice to find the tick marks
        tick_crop = image[crop_y1:crop_y2, slice_x1:slice_x2]

        # convert to an inverted threshold image to find the tick marks
        tick_crop_gray = cv2.cvtColor(tick_crop, cv2.COLOR_BGR2GRAY)
        tick_crop_gray = cv2.blur(tick_crop_gray, (tick_blur,tick_blur), cv2.BORDER_DEFAULT)
        ret, tick_thresh = cv2.threshold(tick_crop_gray, tick_threshold, 255, cv2.THRESH_BINARY)
        tick_thresh_inv = cv2.bitwise_not(tick_thresh)

        # copy the inverted threshold image onto the preview image in the correct location
        tick_thresh_inv_bgr = cv2.cvtColor(tick_thresh_inv, cv2.COLOR_GRAY2BGR)
        tick_thresh_inv_bgr = cv2.bitwise_or(tick_crop, tick_thresh_inv_bgr)
        preview[crop_y1:crop_y1 + tick_crop.shape[0], slice_x1:slice_x1+tick_crop.shape[1]] = tick_thresh_inv_bgr

        # find contours that represent the tick marks
        tick_contours, tick_hierarchy = cv2.findContours(image=tick_thresh_inv, mode=cv2.RETR_TREE, method=cv2.CHAIN_APPROX_NONE)

        # crop a rectangle from the image to find the indicator
        ind_crop = image[crop_y1:crop_y2, crop_x1:crop_x2]

        # find the red indicator with a mask and range
        ind_crop_hsv = cv2.cvtColor(ind_crop, cv2.COLOR_BGR2HSV)

        ind_lower_red = np.array([145,112,0])
        ind_upper_red = np.array([179,255,255])

        ind_red_mask = cv2.inRange(ind_crop_hsv, ind_lower_red, ind_upper_red)
        ind_masked = cv2.bitwise_and(ind_crop, ind_crop, mask=ind_red_mask)
        ind_masked = cv2.blur(ind_masked, (indicator_blur,indicator_blur), cv2.BORDER_DEFAULT)

        ind_masked_gray = cv2.cvtColor(ind_masked, cv2.COLOR_BGR2GRAY)
        ret, ind_masked_thresh = cv2.threshold(ind_masked_gray, indicator_threshold, 255, cv2.THRESH_BINARY)

        # copy the indicator threshold image onto the preview
        prev_ind_thresh = cv2.cvtColor(ind_masked_thresh, cv2.COLOR_GRAY2BGR)
        prev_ind_thresh = cv2.bitwise_or(ind_crop, prev_ind_thresh)

        preview[crop_y1:crop_y1 + prev_ind_thresh.shape[0], crop_x1:crop_x1+prev_ind_thresh.shape[1]] = prev_ind_thresh

        # find contours for the indicator
        ind_contours, ind_hierarchy = cv2.findContours(image=ind_masked_thresh, mode=cv2.RETR_TREE, method=cv2.CHAIN_APPROX_SIMPLE)

        # draw the crops on the preview
        preview = cv2.rectangle(preview, (crop_x1, crop_y1), (crop_x2, crop_y2), (0,32,192), 2)
        preview = cv2.rectangle(preview, (slice_x1, crop_y1), (slice_x2, crop_y2), (0,192,0), 2)

        level, preview = self.interpolate(tick_contours, ind_contours, preview)

        avg = None
        if level is not None:
            avg, preview = self.average_level(level, preview)
            if avg is not None:
                
                now = str(datetime.now())
                self.rd.set('avg_level', avg)
                self.rd.set('avg_update_time', now)

                self.rd.publish('avg_level', avg)
                self.rd.publish('avg_update_time', now)

                self.avg = avg
                self.avg_update_time = now
                
        if preview is not None:
            ret, buffer = cv2.imencode('.jpg', preview)
            self.rd.set('encoded_preview', buffer.tobytes())
            self.rd.publish('encoded_preview', 'updated')


        if avg is not None:
            self.rd.publish('encoded_preview', 'updated')            
            return True
        
        return False

    def close(self):
        if self.camera is not None:
            self.camera.close()



if __name__ == '__main__':
    cv = GaugeCV()
    while True:
        time.sleep(1)
