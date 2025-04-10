import time
import paho.mqtt.client as mqtt


# Define callbacks
def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    client.subscribe("test/topic")


def on_message(client, userdata, msg):
    print(f"Received message: '{msg.payload.decode()}' on topic '{msg.topic}'")


# Create client instance
client = mqtt.Client()

# Assign callbacks
client.on_connect = on_connect
client.on_message = on_message

# Connect to broker
client.connect("mosquitto", 1883, 60)

# Start the loop
client.loop_start()

# Publish a test message
client.publish("test/topic", "Hello from Paho MQTT!")

# Keep it running for a bit to receive messages

time.sleep(5)

# Stop the loop and disconnect
client.loop_stop()
client.disconnect()

print("Done.")
