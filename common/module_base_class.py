from typing import List, Tuple
from abc import ABC, abstractmethod
import paho.mqtt.client as mqtt
from helper import Helper
from logger import Logger


class ModuleBaseClass(ABC):

    def __init__(self, mqtt_client: mqtt.Client,sub_topics:List[Tuple[str,int]],logger:Logger):
        try:
            self.mqtt_client = mqtt_client
            self.mqtt_client_id = str(mqtt_client._client_id)
            self.sub_topics = sub_topics
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.on_message = self.on_message
            self.mqtt_client.on_disconnect = self.on_disconnect
            self.mqtt_client.connect("127.0.0.1")
            self.logger = logger
        except Exception as e:
            msg = f"{self.__class__.__name__}: failed to connect Error: {str(e)}"
            raise Exception(msg)

    @abstractmethod
    def is_a_valid_message(self, msg_json_obj) -> bool:
        """Check that a message is valid."""
        pass

    @abstractmethod
    def handle_message(self, msg_json_obj):
        pass

    @abstractmethod
    def run(self):
        pass

    def on_connect(self, client, userdata, flags, rc):
        if rc==0:
            msg = f"{self.client_id}:{self.__class__.__name__}: Connected with result code {str(rc)}"
            self.logger.debug(msg)
            self.mqtt_client.subscribe(self.sub_topics)
        else:
            msg = f"{self.client_id}:{self.__class__.__name__}: Couldn't connect - return code: {str(rc)}"
            self.logger.debug(msg)

    def on_disconnect(self, client, userdata, rc):
        msg = f"{self.client_id}:{self.__class__.__name__}: disconnected: reason {str(rc)}"
        self.mqtt_client.connected_flag=False
        self.mqtt_client.disconnect_flag=True
        self.logger.debug(msg)

    def on_message(self, client, userdata, msg):
        (msg_json_obj, is_msg_json_obj) = Helper.is_a_json_object(msg.payload)
        msg = f"{self.__class__.__name__}{self.on_message.__name__}: recieved a message: "
        self.logger.debug(msg_json_obj)
        
        if(False == is_msg_json_obj):
            log_msg = f"{self.__class__.__name__}{self.on_message.__name__}: msg is malformed"
            self.logger.debug(log_msg)
            return
        else:
            log_msg = f"{self.__class__.__name__}:{self.on_message.__name__}: msg is a json object"
            self.logger.debug(log_msg)

        if(self.is_a_valid_message(msg_json_obj)):
            self.logger.debug(f"{self.__class__.__name__}:{self.on_message.__name__}: msg is valid")
            self.handle_message(msg_json_obj)
        else:
            log_msg = f"{self.__class__.__name__}:{self.on_message.__name__}: msg is not valid"
            self.logger.debug(log_msg)

    def start_mqtt_loop(self):
        msg = f"{self.__class__.__name__}:{self.start_mqtt_loop.__name__}: start mqtt loop"
        self.logger.info(msg)
        self.mqtt_client.loop_forever()