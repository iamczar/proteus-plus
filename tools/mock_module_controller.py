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
import time
import math
from datetime import datetime
from typing import List, Dict
from pathlib import Path

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
SENSOR_DATA_INTERVAL_SEC: float = 0.1

# JSONL live history: match ModuleHandler layout so Live View backfill behaves
# identically when using this mock instead of real hardware.
_live_x_counters: Dict[int, int] = {}


def _repo_root() -> Path:
    """Resolve repository root, mirroring ModuleHandler._repo_root."""
    here = Path(__file__).resolve()
    return here.parents[1]


def _live_jsonl_dir() -> Path:
    """Directory for live JSONL history, mirroring ModuleHandler._live_jsonl_dir."""
    d = _repo_root() / "proteus-ui" / "data" / "live"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _append_live_jsonl(module_id: int, data: dict) -> None:
    """Append a live JSONL record for this module, using the same schema as
    ModuleHandler._append_live_jsonl so that Live View backfill works against
    files created by this mock.
    """
    try:
        x = int(_live_x_counters.get(module_id, 0))
        fp = _live_jsonl_dir() / f"module_{module_id}.jsonl"
        record = {
            "x": x,
            "ts": int(time.time() * 1000),  # ms epoch
            "data": data or {},
        }
        with fp.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        _live_x_counters[module_id] = x + 1
    except Exception:
        # Best-effort only; never interfere with publishing
        pass


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
    # Generate smooth sinusoidal variations for temperature, flow, and pressure
    # so that charts show clear wave-like behavior over time.
    t = time.time()
    # Base values roughly matching previous example, with modest amplitudes
    base_temp = 26.35
    temp_amp = 0.4
    temp_measured = base_temp + temp_amp * math.sin(2.0 * math.pi * 0.01 * t)

    base_flow = 66.0
    flow_amp = 3.0
    flow_measured = base_flow + flow_amp * math.sin(2.0 * math.pi * 0.02 * t)

    base_pressure = -829.0
    pressure_amp = 5.0
    pressure_measured = base_pressure + pressure_amp * math.sin(2.0 * math.pi * 0.015 * t)

    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

    data = {
        "oxygen_pid": 0.0,
        "circ_pump_speed": 0.0,
        "temp_measured": round(temp_measured, 3),
        "oxygen_setpoint": 0.0,
        "pressure_kd": 0.0,
        "oxygen_ki": 0.0,
        "oxygen_kd": 0.0,
        # Mirror the flow/pressure sinusoid into oxygen channels so Live View
        # shows clearly changing traces.
        "oxygen_measured_1": flow_measured,
        "oxygen_measured_2": flow_measured * 0.95,
        "oxygen_measured_3": flow_measured * 1.05,
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
        # Mirror the data_logger sensor_data into live JSONL so that the UI
        # backfill path sees the same structure it would from ModuleHandler.
        try:
            data = payload.get("data") if isinstance(payload, dict) else None
            if isinstance(data, dict):
                _append_live_jsonl(module_id, data)
        except Exception:
            pass
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


