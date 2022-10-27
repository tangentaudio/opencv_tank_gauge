#!/usr/bin/python3

import redis
from homeassistant_api import Client,State

if __name__ == '__main__':

    api_url = "http://homeassistant.local:8123/api"
    token = None
    with open("token.hass", "r") as f:
        token = f.read().strip()

    assert token is not None
            
    rd = redis.Redis(host='localhost', port=6379, db=0, charset='utf-8', decode_responses=True)
    sub = rd.pubsub()
    
    sub.subscribe('avg_level')
    
    while True:
        with Client(api_url, token) as client:
            for msg in sub.listen():
                if msg['type'] == 'message':
                    c = msg['channel']
                    d = msg['data']
            
                    if c == 'avg_level':
                        level = round(float(d), 1)
                        print("level={}".format(level))
                        new_state = client.set_state(State(state=level, entity_id='sensor.oil_tank_level'))

