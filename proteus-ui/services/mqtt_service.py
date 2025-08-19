import os
import sys
import queue
from pathlib import Path
from typing import Any, Dict, Tuple

import streamlit as st

# Ensure repository root is importable so we can use shared MQTT classes in `common/`
_this_file = Path(__file__).resolve()
# .../proteus-plus/proteus-ui/services/mqtt_service.py
# parents[0]=.../proteus-ui/services, [1]=.../proteus-ui, [2]=.../proteus-plus
_repo_root = _this_file.parents[2]
if str(_repo_root) not in sys.path:
    sys.path.append(str(_repo_root))

from common.logger import Logger  # type: ignore
from common.mqtt_connection import MQTTConnection, MQTTConnectionConfig  # type: ignore
from common.mqtt_receiver import MQTTReceiver  # type: ignore
from common.mqtt_sender import MQTTSender  # type: ignore


# Global MQTT config for the UI. Edit these values in code to configure the UI connection.
# Username/password are optional; leave as None for no auth.
UI_MQTT_CONFIG = {
    "HOST": "127.0.0.1",
    "PORT": 1883,
    "USERNAME": None,
    "PASSWORD": None,
}


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class MQTTService(metaclass=Singleton):
    """Streamlit-friendly MQTT service using the shared connection classes.

    - Keeps a single connection across Streamlit reruns
    - Exposes subscribe/publish helpers
    - Buffers inbound messages per-topic in thread-safe queues
    - UI can periodically drain queues to update state
    """

    def __init__(self) -> None:
        # Read configuration from module-level globals only (no secrets/env)
        host = str(UI_MQTT_CONFIG.get("HOST", "127.0.0.1"))
        port = int(UI_MQTT_CONFIG.get("PORT", 1883))
        username = UI_MQTT_CONFIG.get("USERNAME")
        password = UI_MQTT_CONFIG.get("PASSWORD")

        self.logger = Logger("UI-MQTT", "ui_mqtt.log", "info", True, False)
        config = MQTTConnectionConfig(
            host=str(host),
            port=port,
            keepalive=60,
            client_id="proteus-ui",
            clean_session=True,
            username=username,
            password=password,
            will_topic="ui/status",
            will_payload="offline",
            will_qos=0,
            will_retain=False,
        )

        self.connection = MQTTConnection(config, self.logger)
        # Accept non-JSON payloads so plain text messages are not dropped
        self.receiver = MQTTReceiver(self.connection, self.logger, accept_non_json=True)
        self.sender = MQTTSender(self.connection, self.logger)

        # topic -> Queue[(topic, data)]
        self._queues: Dict[str, queue.Queue[Tuple[str, Any]]] = {}

        # Establish connection (background loop)
        try:
            self.connection.connect(start_loop=True, timeout_sec=3.0)
        except Exception as exc:
            self.logger.error(f"Failed to connect MQTT in UI: {exc}")

    def subscribe(self, topic: str, qos: int = 0) -> None:
        if topic not in self._queues:
            self._queues[topic] = queue.Queue()

        def _handler(actual_topic: str, data: Any) -> None:
            try:
                self._queues[topic].put_nowait((actual_topic, data))
            except Exception:
                # Best effort; drop if full or other error
                pass

        self.receiver.subscribe(topic, _handler, qos=qos)

    def drain(self, topic: str, max_items: int = 500) -> list[Tuple[str, Any]]:
        items: list[Tuple[str, Any]] = []
        q = self._queues.get(topic)
        if not q:
            return items
        for _ in range(max_items):
            try:
                items.append(q.get_nowait())
            except Exception:
                break
        return items

    def publish(self, topic: str, payload: Any, qos: int = 0, retain: bool = False) -> None:
        self.sender.publish(topic, payload, qos=qos, retain=retain)


