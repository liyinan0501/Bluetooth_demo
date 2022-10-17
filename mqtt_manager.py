import paho.mqtt.client as paho
import sys


class MqttManager(object):
    def __init__(self) -> None:
        self.client = paho.Client()

    def connect(self):
        if self.client.connect("localhost", 1883, 60) != 0:
            print("Can not connect to MQTT broker!")
            sys.exit(-1)
        else:
            print("MQTT connection is Ok.")

    def publish(self, topic, msg, qos):
        self.client.publish(topic, msg, qos)
