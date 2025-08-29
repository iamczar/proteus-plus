import os
import json
import time
import unittest
from datetime import datetime

import paho.mqtt.client as mqtt


def now_iso():
    return datetime.now().isoformat()


class SequenceControlButtonsTest(unittest.TestCase):
    MODULE_ID = int(os.getenv("MODULE_ID", "3005"))
    MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")

    def setUp(self):
        self._connected = False
        self.acks = []
        self.executed = []
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.connect(self.MQTT_HOST)
        self.thread = self.client.loop_start()
        # Subscribe to Alpha status where acks/executions are reported
        self.client.subscribe([(f"alphacommsmanager-status/{self.MODULE_ID}", 0)])

        # Wait for connection
        t0 = time.time()
        while not self._connected and time.time() - t0 < 3.0:
            time.sleep(0.05)
        self.assertTrue(self._connected, f"Failed to connect to MQTT broker at {self.MQTT_HOST}")

    def tearDown(self):
        try:
            self.client.loop_stop()
        except Exception:
            pass
        try:
            self.client.disconnect()
        except Exception:
            pass

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        try:
            self._connected = (int(getattr(reason_code, "value", 1)) == 0)
        except Exception:
            self._connected = False

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8", errors="ignore"))
        except Exception:
            return
        inner = payload.get("message") if isinstance(payload.get("message"), dict) else {}
        cmd = inner.get("command")
        action = inner.get("action")
        if cmd in ("stop", "pause", "resume", "retrieve_data", "start_data_log", "stop_data_log"):
            if action in ("ack", "acknowledged", "received"):
                self.acks.append(cmd)
            if action in ("executed", "done", "completed"):
                self.executed.append(cmd)

    def _publish_ui_command(self, command_name: str):
        topic = f"sequence-commands/{self.MODULE_ID}"
        env = {
            "message_source": "proteus-ui",
            "timestamp": now_iso(),
            "message": {"command": command_name},
        }
        self.client.publish(topic, json.dumps(env))

    def _wait_for(self, predicate, timeout=5.0):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if predicate():
                return True
            time.sleep(0.05)
        return False

    def test_buttons_ack_then_execute(self):
        commands = [
            ("stop_sequence", "stop"),
            ("pause_sequence", "pause"),
            ("resume_sequence", "resume"),
            ("retrieve_data", "retrieve_data"),
            ("start_data_log", "start_data_log"),
            ("stop_data_log", "stop_data_log"),
        ]

        for ui_cmd, alpha_cmd in commands:
            self.acks.clear()
            self.executed.clear()
            self._publish_ui_command(ui_cmd)

            # Wait for ack first
            self.assertTrue(
                self._wait_for(lambda: alpha_cmd in self.acks, timeout=10.0),
                f"No ack for {ui_cmd} ({alpha_cmd})",
            )

            # Then optional executed/done
            self._wait_for(lambda: alpha_cmd in self.executed, timeout=10.0)


if __name__ == "__main__":
    unittest.main()


