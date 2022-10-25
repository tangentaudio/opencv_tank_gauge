from picamera import PiCamera
from picamera.array import PiRGBArray
import cv2
import numpy as np
from datetime import datetime

class GaugeCV:
    def __init__(self):
        print("GaugeCV __init__")
        self.level_avg_win = []
        self.config = {}
        self.camera = None
        self.preview = None
        self.avg = 0.0

    def set_config(self, d):
        self.config = d

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

    def average_level(self, level):

        if len(self.level_avg_win) < self.config_int('level_average_points'):
            self.level_avg_win.append(level)
        else:
            avg_array = np.array(self.level_avg_win)
            mean = np.mean(avg_array)
            standard_deviation = np.std(avg_array)
            distance_from_mean = abs(avg_array - mean)

            max_deviations = self.config['level_max_deviation']
            not_outlier = distance_from_mean <= max_deviations * standard_deviation
            no_outliers = avg_array[not_outlier]

            avg = np.mean(no_outliers)

            self.level_avg_win = []

            return avg

        return None

    def process_image(self):
        # get config values
        crop_x1 = self.config_int('crop_x1')
        crop_y1 = self.config_int('crop_y1')
        crop_x2 = self.config_int('crop_x2')
        crop_y2 = self.config_int('crop_y2')
        slice_x1 = self.config_int('slice_x1')
        slice_x2 = self.config_int('slice_x2')
        
        with PiCamera() as self.camera:
            self.camera.resolution = (800,608)
            with PiRGBArray(self.camera, size=(800, 608)) as output:
                self.camera.capture(output, format="bgr")
                frame = output.array

                # crop and rotate the image to correct, then 180 degrees because of upside down camera
                image = self.rotate_image(frame, self.config['rotate_angle'])
                image = cv2.rotate(image, 1, cv2.ROTATE_180)

                # create a preview image for the web stream
                preview = image.copy()
                
                # crop a slice to find the tick marks
                tick_crop = image[crop_y1:crop_y2, slice_x1:slice_x2]
                
                # convert to an inverted threshold image to find the tick marks
                tick_crop_gray = cv2.cvtColor(tick_crop, cv2.COLOR_BGR2GRAY)
                tick_crop_gray = cv2.blur(tick_crop_gray, (4,4), cv2.BORDER_DEFAULT)
                ret, tick_thresh = cv2.threshold(tick_crop_gray, self.config['tick_threshold'], 255, cv2.THRESH_BINARY)
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
                ind_masked = cv2.blur(ind_masked, (4,4), cv2.BORDER_DEFAULT)

                ind_masked_gray = cv2.cvtColor(ind_masked, cv2.COLOR_BGR2GRAY)
                ret, ind_masked_thresh = cv2.threshold(ind_masked_gray, 50, 255, cv2.THRESH_BINARY)

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

                self.preview = preview
                
                avg = None
                if level is not None:
                    avg = self.average_level(level)
                    if avg is not None:
                        self.avg = avg
                        return True
               
        return False

    def close(self):
        if self.camera is not None:
            self.camera.close()

    def get_encoded(self):
        if self.preview is not None:
            ret, buffer = cv2.imencode('.jpg', self.preview)
            return buffer.tobytes()
        return None

    def get_error_image_encoded(self):
        image = np.zeros((608,800,3), np.uint8)
        font = cv2.FONT_HERSHEY_SIMPLEX
        image = cv2.putText(image,'Pi Camera Busy',(270,340), font, 1,(0,0,255),2,cv2.LINE_AA)
        ret, buffer = cv2.imencode('.jpg', image)
        return buffer.tobytes()
    
    def get_avg(self):
        return self.avg
