#!/usr/bin/env python

import time
from datetime import datetime
import board
import neopixel
from threading import Thread,Lock
from enum import Enum
import redis
import os

class States(Enum):
    INIT = 1
    ERROR = 2
    QUERY = 3
    LEVEL = 4
    SHUTDOWN = 5

class GaugePixels:
    def __init__(self):
        self.pixels = neopixel.NeoPixel(board.D21, 16, brightness=0.1, pixel_order=neopixel.GRB, auto_write=False)

        self.state = States.INIT
        self.state_update = True
        self.phase = 0
        self.level = 0.0
        self.warn = False
        self.lock = Lock()
        
        t = Thread(target=self.thread_func)
        t.start()

        
    def display_level(self, level, show=True):
        print("display level={l}".format(l=level))
        self.pixels.fill((0,0,0))

        warn = False
        
        color = (0,255,0)
        if level > 0.0 and level < 30.0:
            color = (255, 0, 0)
            warn = True
        elif level >= 30 and level < 70:
            color = (192, 192, 0)
            
        last = int(15 * (level / 100.0)) + 1;
            
        for pixel in range(0,last,1):
            self.pixels[pixel] = color

        if show:
            self.pixels.show()
        
        return [warn, last]
       
        
    def thread_func(self):
        while True:
            with self.lock:
                state = self.state
                state_update = self.state_update
                phase = self.phase
                level = self.level
                warn = self.warn

            if state_update:
                phase = 0
            else:
                phase = phase + 1
                
            if state == States.INIT:
                if phase == 0:
                    self.pixels.fill((0,0,255))
                    self.pixels.show()
                elif phase == 10:
                    self.pixels.fill((0,0,0))
                    self.pixels.show()
                pass
            elif state == States.ERROR:
                if phase == 0:
                    self.pixels.fill((255,0,0))
                    self.pixels.show()
                elif phase == 5:
                    self.pixels.fill((0,0,0))
                    self.pixels.show()
                elif phase == 10:
                    phase = 0
                pass
            elif state == States.QUERY:
                if phase == 0:
                    self.pixels.fill((0,0,0))
                    self.pixels.show()
                elif phase == 3:
                    self.pixels[6] = (0,0,255)
                    self.pixels[7] = (255,255,255)
                    self.pixels[8] = (0,0,255)
                    self.pixels.show()
                elif phase == 6:
                    phase = 0
                    
            elif state == States.LEVEL:
                if phase == 0:
                    # show level and top LED as blue to indicate an update
                    warn, last = self.display_level(level, False)
                    self.pixels[15] = (0, 0, 255)
                    self.pixels.show()

                elif phase == 10:
                    # show the plain level
                    warn, last = self.display_level(level, True)
                    
                elif phase == 15:
                    # blink the level if in warning state
                    if warn:
                        self.pixels.fill((0,0,0))
                        self.pixels.show()

                elif phase == 20:
                    # jump back to plain level display in warning state
                    if warn:
                        phase = 10
                    
            elif state == States.SHUTDOWN:
                if phase == 0:
                    self.pixels.fill((0,0,0))
                    self.pixels[0] = (255, 255, 255)
                    self.pixels.show()
                        
            else:
                pass

            time.sleep(0.100)

            with self.lock:
                if state_update:
                    self.state_update = False
                self.phase = phase
                self.warn = warn
                

                	

    def set_state(self, state):
        with self.lock:
            self.state = state
            self.state_update = True

        print("set state={s}".format(s=state))
              
    def set_level(self, level):
        with self.lock:
            self.level = level

        print("set level={l}".format(l=level))
        
if __name__ == '__main__':
    gauge = GaugePixels()
   
    rd = redis.Redis(host='localhost', port=6379, db=0, charset='utf-8', decode_responses=True)
    sub = rd.pubsub()
    
    sub.subscribe('avg_level', 'avg_update_time', 'shutdown')
    while True:
        for msg in sub.listen():
            if msg['type'] == 'message':
                c = msg['channel']
                d = msg['data']
            
                if c == 'avg_level':
                    level = float(d)
                elif c == 'avg_update_time':
                    update_time = datetime.strptime(d, '%Y-%m-%d %H:%M:%S.%f')
                    age = (datetime.now() - update_time).total_seconds()

                    if (age < 600.0):
                        gauge.set_level(level)
                        gauge.set_state(States.LEVEL)

                    else:
                        gauge.set_state(States.ERROR)
                elif c == 'shutdown':
                    gauge.set_state(States.SHUTDOWN)
                    time.sleep(1)
                    if d == 'reboot':
                        os.system('/usr/sbin/reboot')
                    else:
                        os.system('/usr/sbin/poweroff -f')
                        

