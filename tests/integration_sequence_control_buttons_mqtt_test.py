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
        self.sc_events = []
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.connect(self.MQTT_HOST)
        self.thread = self.client.loop_start()
        # Subscribe only to SequenceController status (events/acks for control commands)
        self.client.subscribe([(f"sequence-controller-status/{self.MODULE_ID}", 0)])

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
        # SequenceController events (e.g., paused/resumed/stopped)
        if payload.get("message_source") != "sequence_controller":
            return
        m = payload.get("message")
        if isinstance(m, dict):
            ev = m.get("event")
            if ev:
                self.sc_events.append(ev)

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
        # UI command and expected SequenceController event (if applicable)
        commands = [
            ("stop_sequence", "stopped"),
            ("pause_sequence", "paused"),
            ("resume_sequence", "resumed"),
            ("retrieve_data", None),
            ("start_data_log", None),
            ("stop_data_log", None),
        ]

        for ui_cmd, sc_event in commands:
            self.sc_events = []
            self._publish_ui_command(ui_cmd)

            if sc_event:
                # For control commands, assert SequenceController event arrives
                self.assertTrue(
                    self._wait_for(lambda: sc_event in self.sc_events, timeout=10.0),
                    f"No SequenceController event '{sc_event}' for {ui_cmd}",
                )
            else:
                # For data/logging commands, do not assert SC events; fire-and-forget
                time.sleep(0.2)


if __name__ == "__main__":
    unittest.main()


