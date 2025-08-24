"""
Integration test (hardware-in-the-loop).

Preconditions:
- Alpha hardware connected to the host and powered.
- Module Controller is already running (python -m module_controller).
- Mosquitto broker available at MQTT_HOST (default 127.0.0.1).

Behavior:
- Publishes Proteus-UI envelope to start a sequence using tests/test_sequence_file.csv
- Waits for sequence init ACK on sys-logger/<module_id>
- Waits for sequence completion on file-info/<module_id>

Usage:
  MQTT_HOST=127.0.0.1 MODULE_ID=3005 python -m unittest tests/integration_alpha_sequence_mqtt_test.py
"""

import os
import json
import time
import unittest
from typing import Any, Dict

import paho.mqtt.client as mqtt


def now_iso() -> str:
    import datetime as _dt
    return _dt.datetime.now().isoformat()


class MqttCapture:
    def __init__(self, host: str):
        self.host = host
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self._connected = False
        self.messages: list[tuple[str, Dict[str, Any]]] = []

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        self._connected = (int(reason_code) == 0)

    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode(errors="ignore")
            obj = json.loads(payload)
            self.messages.append((msg.topic, obj))
        except Exception:
            pass

    def connect(self):
        self.client.connect(self.host)
        self.client.loop_start()
        # wait a moment for connection
        t0 = time.time()
        while not self._connected and time.time() - t0 < 3.0:
            time.sleep(0.01)
        return self._connected

    def disconnect(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass

    def clear(self):
        self.messages.clear()

    def subscribe(self, topics: list[str]):
        for t in topics:
            self.client.subscribe(t)

    def wait_for(self, predicate, timeout_s: float):
        deadline = time.time() + timeout_s
        scan_idx = 0
        while time.time() < deadline:
            # scan newly received messages only
            while scan_idx < len(self.messages):
                topic, obj = self.messages[scan_idx]
                scan_idx += 1
                try:
                    if predicate(topic, obj):
                        return topic, obj
                except Exception:
                    pass
            time.sleep(0.02)
        return None, None


class IntegrationAlphaSequenceMqttTest(unittest.TestCase):
    def setUp(self):
        self.mqtt_host = os.getenv("MQTT_HOST", "127.0.0.1")
        self.module_id = os.getenv("MODULE_ID", "3005")
        self.csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_sequence_file.csv"))
        if not os.path.exists(self.csv_path):
            self.fail(f"CSV file not found: {self.csv_path}")

        self.mqtt = MqttCapture(self.mqtt_host)
        ok = self.mqtt.connect()
        if not ok:
            self.fail(f"Failed to connect to MQTT broker at {self.mqtt_host}")

        # subscribe to topics we expect
        self.sys_logger_topic = f"sys-logger/{self.module_id}"
        self.file_info_topic = f"file-info/{self.module_id}"
        self.mqtt.subscribe([self.sys_logger_topic, self.file_info_topic])

    def tearDown(self):
        self.mqtt.disconnect()

    def _publish_start_sequence(self):
        envelope = {
            "message_source": "proteus-ui",
            "timestamp": now_iso(),
            "message": {
                "command": "start_sequence",
                "file_path": self.csv_path,
            },
        }
        topic = f"sequence-commands/{self.module_id}"
        payload = json.dumps(envelope)
        # Use a temporary client for publish to avoid interfering with capture
        pub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        pub.connect(self.mqtt_host)
        pub.loop_start()
        time.sleep(0.05)
        pub.publish(topic, payload)
        time.sleep(0.05)
        pub.loop_stop()
        pub.disconnect()

    def test_sequence_start_to_completion(self):
        # publish start
        self.mqtt.clear()
        self._publish_start_sequence()

        # expect init ACK on sys-logger
        def is_init_ack(topic, obj):
            if topic != self.sys_logger_topic:
                return False
            cmd = obj.get("command")
            msg = obj.get("message") if isinstance(obj.get("message"), dict) else None
            if cmd == "sequence_ack":
                return True
            if msg and msg.get("command") == "sequence_ack":
                return True
            return False

        _, ack = self.mqtt.wait_for(is_init_ack, timeout_s=30.0)
        self.assertIsNotNone(ack, "No sequence init ACK received")

        # expect sequence complete on file-info topic
        def is_complete(topic, obj):
            if topic != self.file_info_topic:
                return False
            cmd = obj.get("command")
            msg = obj.get("message") if isinstance(obj.get("message"), dict) else None
            if cmd == "sequence_complete":
                return True
            if msg and msg.get("command") == "sequence_complete":
                return True
            return False

        _, complete = self.mqtt.wait_for(is_complete, timeout_s=120.0)
        self.assertIsNotNone(complete, "No sequence_complete received on file-info topic")


if __name__ == "__main__":
    unittest.main()


