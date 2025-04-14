from typing import List, Tuple
import paho.mqtt.client as mqtt_client
from common.helper import Helper
from common.module_base_class import ModuleBaseClass
from common.logger import Logger

class SerialManager(ModuleBaseClass):
    def __init__(self,mqtt_client:mqtt_client,
                 sub_topics:List[Tuple[str,int]],
                 valid_incoming_msg_ids:list,
                 logger:Logger):
        
        try:
            super().__init__(mqtt_client,sub_topics,logger)
            self.valid_incoming_msg_ids = valid_incoming_msg_ids
        except Exception as e:
            msg = f"{self.__class__.__name__}:{self.__init__.__name__}: failed to instantiate Error: {e}"
            self.logger.error(msg)
            exit()
    
    def is_valid_message(self, msg_json_obj) -> bool:
        return msg_json_obj["msg_src"] in self.valid_incoming_msg_ids

    def open_serial_connections(self,serial_config_file):
        pass
    
    def send_module_heart_beat(self):
        pass

    def handle_message(self, msg_json_obj):
        pass
    
    def run(self):
        pass