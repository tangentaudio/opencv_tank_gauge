#!/usr/bin/python3

import time
import board
import neopixel
import requests
from threading import Thread,Lock
from enum import Enum

class States(Enum):
    INIT = 1
    ERROR = 2
    QUERY = 3
    LEVEL = 4

class GaugePixels:
    def __init__(self):
        self.pixels = neopixel.NeoPixel(board.D21, 16, brightness=0.1, pixel_order=neopixel.GRB, auto_write=False)

        self.state = States.INIT
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
            self.lock.acquire()
            state = self.state
            phase = self.phase
            level = self.level
            warn = self.warn
            self.lock.release()

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
                    phase = -1
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
                    phase = -1
                    
            elif state == States.LEVEL:
                if phase == 0:
                    warn, l = self.display_level(level, True)

                elif phase == 10:
                    if warn:
                        self.pixels.fill((0,0,0))
                        self.pixels.show()

                elif phase == 15:
                    phase = -1    
            else:
                pass

            time.sleep(0.100)
            
            self.lock.acquire()
            if self.state != state:
                phase = 0
            else:
                phase = phase + 1
            self.phase = phase
            self.warn = warn
            self.lock.release()
                	

    def set_state(self, state):
        self.lock.acquire()
        self.state = state
        self.lock.release()
        print("set state={s}".format(s=state))
              
    def set_level(self, level):
        self.lock.acquire()
        self.level = level
        self.lock.release()
        print("set level={l}".format(l=level))
        
if __name__ == '__main__':
    gauge = GaugePixels()
    time.sleep(2)
    
    while True:

        try:
            gauge.set_state(States.QUERY)
            r = requests.get('http://localhost:8080/random_test')
            j = r.json()
            print(j['level'])
            gauge.set_level(j['level'])
            gauge.set_state(States.LEVEL)

            time.sleep(10)
            
        except requests.exceptions.ConnectionError:
            gauge.set_state(States.ERROR)
            time.sleep(5)

