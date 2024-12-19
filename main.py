# Import required libraries
import network
import socket
import time
from time import sleep
import onewire
import ds18x20
import dht
import machine
import json
from umqtt.simple import MQTTClient
import variables # custom variables file

# setup WLAN
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# prevent the wireless chip from activating power-saving mode when it is idle
wlan.config(pm = 0xa11140) 

# Connect to your AP using your login details
wlan.connect(variables.SSID, variables.SSID_PW)
while wlan.isconnected() == False:
    print('Waiting for connection...')
    time.sleep(1)
print("Connected to WiFi")

# DS sensors bytearrays
poolsensor = variables.poolsensor
pondsensor = variables.pondsensor

# setup internal temp and LED
adcpin = 4
inttemp = machine.ADC(adcpin)
intled = machine.Pin("LED", machine.Pin.OUT)

# setup ds18b20 sensor(s)
ds_pin = machine.Pin(22)
ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))

# setup DHT11 sensor
dht_pin = machine.Pin(21)
dht_sensor = dht.DHT11(dht_pin)

# check ds sensor exists
roms = ds_sensor.scan()
print('Found DS sensors: ', roms)

# check dht sensor exists
print('Found DHT sensors: ', dht_sensor)

# MQTT details
mqtt_host      = variables.mqtthost
mqtt_client_id = variables.mqttclientid
mqtt_publish_topic = variables.mqttpublishtopic

# function for internal temp
def ReadPicoTemp():
    adc_value = inttemp.read_u16()
    volt = (3.3/65535) * adc_value
    temperature = 27 - (volt - 0.706)/0.001721
    return round(temperature, 1)

# function for ds18b20 sensor(s) temps
def ReadDS18b20Temp(sensor):
    err = None
    temp = None
    try:
        # convert temp
        ds_sensor.convert_temp()
        # pause
        time.sleep_ms(750)
        # get temp
        temp = ds_sensor.read_temp(sensor)
        # pause
        time.sleep_ms(750)
    except Exception as err:
        print('Failed reading DS sensor: ', sensor)
        temp = None
    return temp

def ReadDHTSensor():
    try:
        # get sensor reading
        dht_sensor.measure()
        #create dictionary
        dht_read = {
            "temp": dht_sensor.temperature(),
            "humidity": dht_sensor.humidity()
        }
        # pause
        time.sleep_ms(750)
    except Exception as err:
        print('Failed reading DHT sensor')
        dht_read = {
            "temp": None,
            "humidity": None
        }
    return dht_read

def GetWLANStr(SSID):
    try:
        accessPoints = wlan.scan() 
        for ap in accessPoints:
            if ap[0] == bytes(SSID, 'utf-8'):
                strength = int((f'{ap[3]}'))
    except Exception as err:
        print('Error: ', err)
        strength = None
    return strength

# Initialize our MQTTClient and connect to the MQTT server
mqtt_client = MQTTClient(client_id=mqtt_client_id, server=mqtt_host)

try:
    mqtt_client.connect()
    print("Connected to MQTT server")
except Exception as e:
    print("Failed to connect to MQTT server:", e)

# Function to publish sensor data to MQTT
def publish_sensor_data():
    while True:

        # Read temp from onboard sensor
        picotemp = ReadPicoTemp()
        
        # get pool temp
        pooltemp = ReadDS18b20Temp(poolsensor)
       
        # get pond temp
        pondtemp = ReadDS18b20Temp(pondsensor)

        # get DHT reading
        DHTread = ReadDHTSensor()

        # get WLAN Signal Strength
        wlanrssi = GetWLANStr(variables.SSID)

        # Create payload
        payload = {
            "picotemp": picotemp,
            "pooltemp": pooltemp,
            "pondtemp": pondtemp,
            "airtemp": DHTread["temp"],
            "humidity": DHTread["humidity"],
            "wlanRSSI": wlanrssi
        }
        
        # Convert payload to JSON
        payload_json = json.dumps(payload)
        
        try:
            # Publish to MQTT topic
            mqtt_client.publish(mqtt_publish_topic, payload_json)
            print("Published data to MQTT:", payload_json)
        except Exception as e:
            print("Failed to publish to MQTT:", e)
        
        # Wait before sending the next data
        time.sleep(60)  # Adjust the sleep time as needed

# Start publishing sensor data
publish_sensor_data()
