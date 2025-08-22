import paho.mqtt.client as mqtt
from common.logger import Logger
from .module_controller import ModuleController


def main():
    logger = Logger("ModuleController", "logs/module_controller.log", "info", True, True)
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    controller = ModuleController(mqtt_client, logger)
    controller.run()


if __name__ == "__main__":
    main()


