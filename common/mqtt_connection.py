from __future__ import annotations

import json
import ssl
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import paho.mqtt.client as mqtt

from common.logger import Logger


OnMessageCallback = Callable[[mqtt.Client, Any, mqtt.MQTTMessage], None]


@dataclass
class MQTTConnectionConfig:
    host: str = "127.0.0.1"
    port: int = 1883
    keepalive: int = 60
    client_id: Optional[str] = None
    clean_session: bool = True
    username: Optional[str] = None
    password: Optional[str] = None

    # TLS settings
    tls_enabled: bool = False
    ca_certs: Optional[str] = None
    certfile: Optional[str] = None
    keyfile: Optional[str] = None
    tls_insecure: bool = False

    # Last Will and Testament
    will_topic: Optional[str] = None
    will_payload: Optional[str] = None
    will_qos: int = 0
    will_retain: bool = False

    # Reconnect backoff
    reconnect_min_delay: int = 1
    reconnect_max_delay: int = 120


class MQTTConnection:
    """Manage a shared paho-mqtt connection and lifecycle.

    - Creates and configures the underlying `mqtt.Client`
    - Connects/disconnects; manages loop_start/loop_stop
    - Handles TLS, username/password, and LWT
    - Exposes subscribe/publish helpers
    - Allows additional on_message listeners to be attached
    """

    def __init__(self, config: MQTTConnectionConfig, logger: Logger):
        self.config = config
        self.logger = logger

        self._client = mqtt.Client(client_id=self.config.client_id, clean_session=self.config.clean_session)
        if self.config.username is not None:
            self._client.username_pw_set(self.config.username, self.config.password)

        if self.config.tls_enabled:
            ssl_context = ssl.create_default_context(cafile=self.config.ca_certs) if self.config.ca_certs else ssl.create_default_context()
            if self.config.certfile and self.config.keyfile:
                ssl_context.load_cert_chain(certfile=self.config.certfile, keyfile=self.config.keyfile)
            if self.config.tls_insecure:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            self._client.tls_set_context(ssl_context)

        if self.config.will_topic is not None:
            self._client.will_set(
                topic=self.config.will_topic,
                payload=self.config.will_payload or "",
                qos=self.config.will_qos,
                retain=self.config.will_retain,
            )

        # Connection flags/events
        self._connected_event = threading.Event()
        self._disconnect_requested = False

        # Public listener registry (additional on_message callbacks)
        self._on_message_listeners: List[OnMessageCallback] = []

        # Configure client callbacks
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.reconnect_delay_set(min_delay=self.config.reconnect_min_delay, max_delay=self.config.reconnect_max_delay)

    @property
    def client(self) -> mqtt.Client:
        return self._client

    def connect(self, start_loop: bool = True, timeout_sec: Optional[float] = 5.0) -> None:
        """Connect to the broker and optionally start the network loop in a background thread.

        If `timeout_sec` is provided, this waits up to that many seconds for an initial successful connection.
        """
        self._disconnect_requested = False
        self._connected_event.clear()

        try:
            self._client.connect(self.config.host, self.config.port, self.config.keepalive)
        except Exception as exc:
            self.logger.error(f"MQTT connect error: {exc}")
            raise

        if start_loop:
            self._client.loop_start()

        if timeout_sec is not None:
            self._connected_event.wait(timeout=timeout_sec)

    def disconnect(self) -> None:
        self._disconnect_requested = True
        try:
            self._client.disconnect()
        finally:
            # Stop loop if it was started
            try:
                self._client.loop_stop()
            except Exception:
                pass
            self._connected_event.clear()

    def is_connected(self) -> bool:
        return self._connected_event.is_set()

    def wait_for_connect(self, timeout_sec: Optional[float] = None) -> bool:
        return self._connected_event.wait(timeout=timeout_sec)

    def subscribe(self, topic: str, qos: int = 0) -> None:
        result, mid = self._client.subscribe(topic, qos=qos)
        if result != mqtt.MQTT_ERR_SUCCESS:
            self.logger.warn(f"MQTT subscribe failed for '{topic}' (code={result})")

    def subscribe_many(self, topics: Iterable[Tuple[str, int]]) -> None:
        # paho supports list-of-tuples subscribe
        result, mid = self._client.subscribe(list(topics))
        if result != mqtt.MQTT_ERR_SUCCESS:
            self.logger.warn(f"MQTT subscribe_many failed (code={result})")

    def unsubscribe(self, topic: str) -> None:
        try:
            self._client.unsubscribe(topic)
        except Exception as exc:
            self.logger.warn(f"MQTT unsubscribe error for '{topic}': {exc}")

    def add_on_message_listener(self, callback: OnMessageCallback) -> None:
        self._on_message_listeners.append(callback)

    def remove_on_message_listener(self, callback: OnMessageCallback) -> None:
        if callback in self._on_message_listeners:
            self._on_message_listeners.remove(callback)

    def publish(self, topic: str, payload: Any, qos: int = 0, retain: bool = False) -> None:
        serialized: Any
        if isinstance(payload, (bytes, bytearray, memoryview)):
            serialized = payload
        elif isinstance(payload, str):
            serialized = payload
        else:
            try:
                serialized = json.dumps(payload)
            except Exception:
                # Fallback to str()
                serialized = str(payload)

        result = self._client.publish(topic, serialized, qos=qos, retain=retain)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            self.logger.warn(f"MQTT publish failed for '{topic}' (code={result.rc})")

    # Internal paho callbacks
    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Dict[str, Any], rc: int) -> None:
        if rc == 0:
            self.logger.info(f"MQTT connected to {self.config.host}:{self.config.port}")
            self._connected_event.set()
        else:
            self.logger.warn(f"MQTT connect failed (rc={rc})")

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:
        if self._disconnect_requested:
            self.logger.info("MQTT disconnected by request")
        else:
            # rc != 0 usually means unexpected disconnect; paho will auto-reconnect
            self.logger.warn(f"MQTT disconnected (rc={rc}); will attempt reconnect if loop is running")
        self._connected_event.clear()

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        for listener in list(self._on_message_listeners):
            try:
                listener(client, userdata, msg)
            except Exception as exc:
                self.logger.error(f"on_message listener error: {exc}")


