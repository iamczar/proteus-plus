from __future__ import annotations

from typing import Any

from common.logger import Logger
from common.mqtt_connection import MQTTConnection


class MQTTSender:
    """Publish helper bound to a shared `MQTTConnection`."""

    def __init__(self, connection: MQTTConnection, logger: Logger):
        self.connection = connection
        self.logger = logger

    def publish(self, topic: str, payload: Any, qos: int = 0, retain: bool = False) -> None:
        self.connection.publish(topic, payload, qos=qos, retain=retain)
        self.logger.debug(f"MQTTSender published to '{topic}' (qos={qos}, retain={retain})")


