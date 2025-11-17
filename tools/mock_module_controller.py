"""
Mock Module Controller
----------------------

This script pretends to be the real `ModuleController` by:
- periodically publishing a list of "connected" module IDs to
  `module_controller/list-of-modules`
- publishing fake live sensor data for each module ID to
  `live-sensor-data/<module-id>`

Edit the configuration constants in the section below to change module IDs,
publish rates, or MQTT connection details.
"""

import json
import os
import random
import time
from datetime import datetime
from typing import List

import paho.mqtt.client as mqtt


# ---------------------------------------------------------------------------
# Configuration (edit these values as needed)
# ---------------------------------------------------------------------------

# MQTT broker settings (defaults can be overridden with environment variables)
MQTT_HOST: str = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT: int = int(os.getenv("MQTT_PORT", "1883"))

# List of module IDs this mock controller will advertise and publish for
# Example: [3005, 3006, 3007]
MODULE_IDS: List[int] = [3005]

# How often to publish the module list, in seconds
MODULE_LIST_INTERVAL_SEC: float = 2.0

# How often to publish live sensor data for each module, in seconds
# e.g. 0.5 => 2 Hz, 0.2 => 5 Hz
SENSOR_DATA_INTERVAL_SEC: float = 0.5


# ---------------------------------------------------------------------------
# MQTT callbacks
# ---------------------------------------------------------------------------

def on_connect(client: mqtt.Client, userdata, flags, reason_code, properties):
    """Handle MQTT connection events (paho-mqtt v2 compatible)."""
    try:
        rc_int = int(getattr(reason_code, "value", reason_code))
    except Exception:
        rc_int = 1
    print(f"[mock_module_controller] Connected to MQTT broker {MQTT_HOST}:{MQTT_PORT} "
          f"with result code {reason_code} (int={rc_int})")


def on_disconnect(client: mqtt.Client, userdata, reason_code, properties):
    """Handle MQTT disconnection events (paho-mqtt v2 compatible)."""
    try:
        rc_int = int(getattr(reason_code, "value", reason_code))
    except Exception:
        rc_int = 0
    print(f"[mock_module_controller] Disconnected from MQTT broker: {reason_code} (int={rc_int})")


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------

def build_module_list_payload() -> dict:
    """Build the JSON payload for module_controller/list-of-modules."""
    return {
        "command": "module_list",
        "modules": MODULE_IDS,
        "timestamp": time.time(),
    }


def build_sensor_payload(module_id: int) -> dict:
    """
    Build a fake sensor payload matching the example structure:

    {
      "message_source": "data_logger",
      "module_id": "3005",
      "timestamp": "2025-08-24 10:05:03.101098",
      "alpha_command": "sensor_data",
      "data": { ... }
    }
    """
    # Slightly vary temperature, flow, and pressure to look "alive"
    base_temp = 26.35
    temp_measured = base_temp + random.uniform(-0.2, 0.2)
    flow_measured = 66.0 + random.uniform(-1.0, 1.0)
    pressure_measured = -829.0 + random.uniform(-1.0, 1.0)

    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

    data = {
        "oxygen_pid": 0.0,
        "circ_pump_speed": 0.0,
        "temp_measured": round(temp_measured, 3),
        "oxygen_setpoint": 0.0,
        "pressure_kd": 0.0,
        "oxygen_ki": 0.0,
        "oxygen_kd": 0.0,
        "oxygen_measured_1": -3000.0,
        "oxygen_measured_2": -3000.0,
        "oxygen_measured_3": -3000.0,
        "oxygen_measured_4": 0.0,
        "state_id": 0.0,
        "pressure_pump_speed": 0.0,
        "pressure_kp": 0.0,
        "oxygen_kp": 0.0,
        "oxy_measured": 0.0,
        "pressure_measured": round(pressure_measured, 4),
        "pressure_setpoint": 0.0,
        "pressure_pid": 0.0,
        "flow_measured": round(flow_measured, 3),
        "pressure_ki": 0.0,
    }

    return {
        "message_source": "data_logger",
        "module_id": str(module_id),
        "timestamp": timestamp_str,
        "alpha_command": "sensor_data",
        "data": data,
    }


# ---------------------------------------------------------------------------
# Publisher loops
# ---------------------------------------------------------------------------

def publish_module_list(client: mqtt.Client) -> None:
    payload = build_module_list_payload()
    topic = "module_controller/list-of-modules"
    client.publish(topic, json.dumps(payload))
    print(f"[mock_module_controller] Published module list to '{topic}': {payload}")


def publish_sensor_data_for_all_modules(client: mqtt.Client) -> None:
    for module_id in MODULE_IDS:
        payload = build_sensor_payload(module_id)
        topic = f"live-sensor-data/{module_id}"
        client.publish(topic, json.dumps(payload))
        print(f"[mock_module_controller] Published sensor data to '{topic}'")


def run() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    # Connect to MQTT broker
    client.connect(MQTT_HOST, MQTT_PORT)

    # Start network loop in background thread
    client.loop_start()

    last_module_list_time = 0.0
    last_sensor_time = 0.0

    try:
        print("[mock_module_controller] Starting publish loops "
              f"(modules={MODULE_IDS}, module_list_interval={MODULE_LIST_INTERVAL_SEC}s, "
              f"sensor_interval={SENSOR_DATA_INTERVAL_SEC}s)")
        while True:
            now = time.time()

            if now - last_module_list_time >= MODULE_LIST_INTERVAL_SEC:
                publish_module_list(client)
                last_module_list_time = now

            if now - last_sensor_time >= SENSOR_DATA_INTERVAL_SEC:
                publish_sensor_data_for_all_modules(client)
                last_sensor_time = now

            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n[mock_module_controller] Stopping (KeyboardInterrupt)")
    finally:
        try:
            client.loop_stop()
        except Exception:
            pass
        try:
            client.disconnect()
        except Exception:
            pass
        print("[mock_module_controller] Clean shutdown complete")


if __name__ == "__main__":
    run()


