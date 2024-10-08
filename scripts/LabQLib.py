'''
-----------------------------------------------------------
LABV Peristaltic Pump Control Library Using Modbus Protocol
-----------------------------------------------------------
'''

import serial
import struct

#------------------------------------------------------#
#   LIBRARY MANAGING THE COMMUNICATION WITH THE PUMP   #
#------------------------------------------------------#

class LABV:

    # Initialize the object and establish a serial connection with the corresponding data format
    def __init__(self, port, address=1, baudrate=9600, parity='E', bytesize=8, stopbits=1, timeout=1):
        print(f"Connecting to port {port} at {baudrate} baudrate...")
        self.ser = serial.Serial(port=port, baudrate=baudrate, parity=parity,
                                 bytesize=bytesize, stopbits=stopbits, timeout=timeout)
        self.address = address

    # Connect the pump
    def connect(self):
        if not self.ser.is_open:
            self.ser.open()

    # Close the serial connection
    def disconnect(self):
        if self.ser.is_open:
            self.ser.close()

    # Calculate the CRC (Cyclic Redundancy Check) for data integrity as
    # explained in "The MODBUS RTU Communication Protocol" section
    def _calculate_crc(self, data):
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc.to_bytes(2, byteorder='little')

    # Convert data into bytes for communication
    def _prepare_data(self, data, data_type):
        if data_type == 'float':
            return struct.pack('&gt;f', data)
        elif data_type == 'int':
            return data.to_bytes(2, byteorder='big')
        else:
            raise ValueError("Data type not supported.")

    # Construct, send commands to the pump and verify the response
    def _send_command(self, function_code, register_address, data, data_type):
        data_bytes = self._prepare_data(data, data_type)
        payload = bytearray([self.address, function_code])
        payload.extend(register_address.to_bytes(2, byteorder='big'))

        if function_code == 0x10:  # Write multiple registers
            number_of_registers = len(data_bytes) // 2
            payload.extend(number_of_registers.to_bytes(2, byteorder='big'))
            payload.append(len(data_bytes))
            payload.extend(data_bytes)
        else:
            payload.extend(data_bytes)

        crc = self._calculate_crc(payload)
        payload.extend(crc)
        print(f"Sending payload: {payload.hex()}")  # Debug: Print the payload

        self.ser.write(payload)
        response = self.ser.read(8) # Adjust as per the device response length
        if len(response) != 8:
            raise ValueError("Invalid response length")
        if self._calculate_crc(response[:-2]) != response[-2:]:
            raise ValueError("Invalid CRC")
        return response

    #------------------------------#
    #   BASIC PARAMETERS SETTING   #
    #------------------------------#

    # Start the pump
    def start_pump(self):
        print("Starting pump...")
        response = self._send_command(0x06, 0x03F0, 0x0001, 'int')
        print(f"Start pump response: {response.hex()}")

    # Stop the pump
    def stop_pump(self):
        print("Stopping pump...")
        response = self._send_command(0x06, 0x03F0, 0x0000, 'int')
        print(f"Stop pump response: {response.hex()}")

    # Set the pump head
    def set_pump_head(self, pump_head):
        print(f"Setting pump head to {pump_head}...")
        response = self._send_command(0x06, 0x03E8, pump_head, 'int')
        print(f"Set pump head response: {response.hex()}")

    # Set the tube size
    def set_tube_size(self, tube_size):
        print(f"Setting tube size to {tube_size}...")
        response = self._send_command(0x06, 0x03E9, tube_size, 'int')
        print(f"Set tube size response: {response.hex()}")

    # Set the direction of rotation
    def set_direction(self, direction):
        print(f"Setting direction to {direction}...")
        data = 0x0001 if direction.upper() == "CW" else 0x0000
        response = self._send_command(0x06, 0x03F1, data, 'int')
        print(f"Set direction response: {response.hex()}")

    # Set the speed of the pump in RPM
    def set_speed(self, speed):
        print(f"Setting speed to {speed} RPM...")
        response = self._send_command(0x10, 0x03EA, speed, 'float')
        print(f"Set speed response: {response.hex()}")

    # Set the flow rate in mL/min
    def set_flow_rate(self, flow_rate):
        print(f"Setting flow rate to {flow_rate} mL/min...")
        response = self._send_command(0x10, 0x03EC, flow_rate, 'float')
        print(f"Set flow rate response: {response.hex()}")

    # Set the flow volume in mL
    def set_flow_volume(self, volume):
        print(f"Setting flow volume to {volume} mL...")
        response = self._send_command(0x10, 0x03F3, volume, 'float')
        print(f"Set flow volume response: {response.hex()}")

    # Set the working time in seconds
    def set_working_time(self, time):
        print(f"Setting working time to {time} seconds...")
        response = self._send_command(0x10, 0x03FA, time, 'float')
        print(f"Set working time response: {response.hex()}")

    # Set the working mode
    def set_working_mode(self, mode):
        """
        Working modes:
        0: Transferring
        1: Fixed volume measurement
        2: Fixed time and volume
        """
        if mode not in [0, 1, 2]:
            raise ValueError("Invalid working mode. Must be 0, 1, or 2.")

        print(f"Setting working mode to {mode}...")
        response = self._send_command(0x06, 0x03FC, mode, 'int')
        print(f"Set working mode response: {response.hex()}")

    # Set the pause time in seconds
    def set_pause_time(self, time):
        print(f"Setting pause time to {time} seconds...")
        response = self._send_command(0x10, 0x03FD, time, 'float')
        print(f"Set pause time response: {response.hex()}")

    # Set the number of copies
    def set_copy_numbers(self, numbers):
        print(f"Setting copy numbers to {numbers}...")
        response = self._send_command(0x06, 0x03FF, numbers, 'int')
        print(f"Set copy numbers response: {response.hex()}")

    # Set the back suction angle in degrees
    def set_back_suction_angle(self, angle):
        print(f"Setting back suction angle to {angle} degrees...")
        response = self._send_command(0x06, 0x03EF, angle, 'int')
        print(f"Set back suction angle response: {response.hex()}")

    # Start or stop full speed running
    def set_full_speed_running(self, start):
        state = "Start" if start else "Stop"
        print(f"{state} full speed running...")
        data = 0x0001 if start else 0x0000
        response = self._send_command(0x06, 0x03F2, data, 'int')
        print(f"{state} full speed running response: {response.hex()}")

    #---------------------------------------#
    #   CALIBRATION PARAMETERS SETTING UP   #
    #---------------------------------------#

    # Set the testing time in seconds
    def set_testing_time(self, time):
        print(f"Setting testing time to {time} seconds...")
        response = self._send_command(0x06, 0x07D1, time, 'int')
        print(f"Set testing time response: {response.hex()}")

    # Start the calibration test
    def start_test(self):
        print("Starting test...")
        response = self._send_command(0x06, 0x07D2, 0x0001, 'int')
        print(f"Start test response: {response.hex()}")

    # Stop the calibration test
    def stop_test(self):
        print("Stopping test...")
        response = self._send_command(0x06, 0x07D2, 0x0000, 'int')
        print(f"Stop test response: {response.hex()}")

    # Set the actual volume in mL
    def set_actual_volume(self, volume):
        print(f"Setting actual volume to {volume} mL...")
        response = self._send_command(0x10, 0x07D3, volume, 'float')
        print(f"Set actual volume response: {response.hex()}")

    # Restore calibration defaults
    def restore_defaults(self):
        print("Restoring defaults...")
        response = self._send_command(0x06, 0x07D5, 0x0001, 'int')
        print(f"Restore defaults response: {response.hex()}")

    # Perform micro adjustment (increase or decrease)
    def micro_adjustment(self, increase=True):
        action = "Increase" if increase else "Decrease"
        print(f"{action} micro adjustment...")
        data = 0x0001 if increase else 0x0000
        response = self._send_command(0x06, 0x07D6, data, 'int')
        print(f"{action} micro adjustment response: {response.hex()}")

#-----------------------------------------------------------------------#
#   EXAMPLES ON HOW TO USE THE DEFINED CLASS TO CONTROL THE LABV PUMP   #
#-----------------------------------------------------------------------#

if __name__ == "__main__":
    pump = LABV(port='COM6', address=1)  # Change port and address according to your setup
    pump.connect()

    try:
        pump.set_pump_head(5)
        pump.set_tube_size(16)
        pump.set_direction("CW")
        pump.set_speed(50)
        pump.set_flow_rate(50.0)
        pump.set_back_suction_angle(0)
        pump.set_full_speed_running(True)
        pump.start_pump()

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        pump.stop_pump()
        pump.disconnect()