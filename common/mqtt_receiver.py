from __future__ import annotations

import json
from typing import Any, Callable, Dict, Optional

import paho.mqtt.client as mqtt

from common.logger import Logger
from common.mqtt_connection import MQTTConnection


MessageHandler = Callable[[str, Dict[str, Any]], None]


class MQTTReceiver:
    """Subscribe to topics and dispatch JSON-decoded messages.

    This receiver attaches to a shared `MQTTConnection` and listens for messages.
    It expects payloads to be UTF-8 JSON by default, but can optionally pass through
    raw payloads when JSON decoding fails.
    """

    def __init__(self, connection: MQTTConnection, logger: Logger, accept_non_json: bool = False):
        self.connection = connection
        self.logger = logger
        self.accept_non_json = accept_non_json

        # topic -> handler
        self._handlers: Dict[str, MessageHandler] = {}

        # Attach a single on_message hook; we do filtering per-topic here
        self.connection.add_on_message_listener(self._on_message)

    def subscribe(self, topic: str, handler: MessageHandler, qos: int = 0) -> None:
        self._handlers[topic] = handler
        self.connection.subscribe(topic, qos=qos)
        self.logger.debug(f"MQTTReceiver subscribed to '{topic}'")

    def unsubscribe(self, topic: str) -> None:
        if topic in self._handlers:
            del self._handlers[topic]
        self.connection.unsubscribe(topic)

    def _match_topic(self, filter_topic: str, message_topic: str) -> bool:
        # Simple matcher supporting '+' and '#' wildcards like MQTT
        # Fast-path exact match
        if filter_topic == message_topic:
            return True

        filter_levels = filter_topic.split('/')
        message_levels = message_topic.split('/')

        for i, f in enumerate(filter_levels):
            if f == '#':
                return True
            if i >= len(message_levels):
                return False
            if f == '+':
                continue
            if f != message_levels[i]:
                return False
        return len(message_levels) == len(filter_levels)

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        for topic_filter, handler in self._handlers.items():
            if not self._match_topic(topic_filter, msg.topic):
                continue

            try:
                payload_text = msg.payload.decode('utf-8') if isinstance(msg.payload, (bytes, bytearray, memoryview)) else str(msg.payload)
                try:
                    data = json.loads(payload_text)
                except Exception:
                    if self.accept_non_json:
                        data = {"raw": payload_text}
                    else:
                        self.logger.debug(f"MQTTReceiver dropped non-JSON message on '{msg.topic}'")
                        continue
                handler(msg.topic, data)
            except Exception as exc:
                self.logger.error(f"MQTTReceiver handler error on '{msg.topic}': {exc}")


