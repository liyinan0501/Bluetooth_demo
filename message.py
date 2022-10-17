import json
from mqtt_manager import *

data = {
    "measurement": "testi",
    "fields": {"climatechamber_experiment": "Tempature 55"},
    "tags": {"experiment": "experiment 2", "operator": "Matias"},
}

data_Json = json.dumps(data, indent=4)

mqtt = MqttManager()
mqtt.connect()
mqtt.publish("database/write/point", data_Json, 0)

print(data_Json)
