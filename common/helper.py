import json as json
from typing import Union
import serial


class Helper:

    def __init__(self):
        pass

    @staticmethod
    def is_a_json_object(value) -> Union[str, bool]:
        result = ""
        try:
            result = json.loads(value)
        except Exception as e:
            error_msg = f"Not a json object: {str(e)}"
            print(error_msg)
            return (error_msg, False)

        return (result, True)

    @staticmethod
    def setup_serial(serial_port, baudrate, timeout_sec):
        try:
            return serial.Serial(serial_port, baudrate, timeout=timeout_sec)
        except Exception as e:
            error_msg = f"{__name__}:{Helper.setup_serial.__name__}:setting serial config failed: error: " + \
                str(e)
            print(error_msg)
            exit()
    
    @staticmethod
    def is_key_exist_in_dictionary(key,dictionary):
        if key in dictionary:
            return True
        else:
            return False