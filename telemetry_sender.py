#!/usr/bin/env python3
"""
Telemetry Data Sender for Electric Car Dashboard

This script generates realistic telemetry data for APPS (Accelerator Pedal Position Sensor),
BMS (Battery Management System), and Inverter (Motor Controller) systems, then sends it
over serial port in protobuf format for testing the dashboard.
"""

import time
import math
import random
import serial
import argparse
import logging
from datetime import datetime
from typing import Optional, List

import telemetry_pb2


class TelemetrySender:
    """Generates and sends realistic telemetry data over serial port."""
    
    def __init__(self, port: str, baud_rate: int = 57600):
        self.port = port
        self.baud_rate = baud_rate
        self.serial_conn: Optional[serial.Serial] = None
        
        # State variables for realistic data generation
        self.time_offset = time.time()
        self.throttle_position = 0.0
        self.motor_rpm = 0
        self.motor_current = 0.0
        self.battery_voltage = 84.0  # Nominal 20S Li-ion pack voltage
        self.pack_temperature = 25.0
        self.controller_temp = 30.0
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def connect(self) -> bool:
        """Connect to serial port."""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0
            )
            self.logger.info(f"Connected to {self.port} at {self.baud_rate} baud")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to {self.port}: {e}")
            return False

    def disconnect(self):
        """Disconnect from serial port."""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            self.logger.info("Disconnected from serial port")

    def generate_apps_data(self, elapsed_time: float) -> telemetry_pb2.APPSData:
        """Generate realistic APPS (Accelerator Pedal Position Sensor) data."""
        # Simulate realistic throttle patterns
        if elapsed_time < 5:
            # Startup phase - idle
            self.throttle_position = 0.0
            state = telemetry_pb2.APPSData.APPS_STATE_RUNNING
        elif elapsed_time < 10:
            # Gentle acceleration
            target = 0.3 + 0.2 * math.sin(elapsed_time * 0.5)
            self.throttle_position += (target - self.throttle_position) * 0.1
            state = telemetry_pb2.APPSData.APPS_STATE_RUNNING
        elif elapsed_time < 15:
            # Variable throttle
            target = 0.5 + 0.3 * math.sin(elapsed_time * 1.2)
            self.throttle_position += (target - self.throttle_position) * 0.1
            state = telemetry_pb2.APPSData.APPS_STATE_RUNNING
        else:
            # Random patterns
            if random.random() < 0.05:  # 5% chance of going to idle
                target = 0.0
            else:
                target = 0.2 + 0.6 * random.random()
            self.throttle_position += (target - self.throttle_position) * 0.08
            state = telemetry_pb2.APPSData.APPS_STATE_RUNNING

        # Clamp throttle position
        self.throttle_position = max(0.0, min(1.0, self.throttle_position))
        
        # Calculate motor current and RPM based on throttle
        self.motor_current = self.throttle_position * 150.0 + random.gauss(0, 2)  # Up to 150A
        self.motor_rpm = int(self.throttle_position * 4000 + random.gauss(0, 50))  # Up to 4000 RPM
        
        return telemetry_pb2.APPSData(
            state=state,
            current_throttle_percentage=self.throttle_position,
            current_motor_current=self.motor_current,
            current_motor_rpm=max(0, self.motor_rpm)
        )

    def generate_bms_segment(self, segment_id: int, base_temp: float) -> telemetry_pb2.BMSSegmentData:
        """Generate data for a single BMS segment."""
        # Generate 12 cell voltages (3.3V - 4.2V per cell)
        cell_voltages = []
        for i in range(12):
            base_voltage = 3.7 + 0.3 * math.sin(time.time() * 0.1 + i * 0.5)
            cell_voltage = base_voltage + random.gauss(0, 0.02)  # Add some variation
            cell_voltages.append(max(3.0, min(4.3, cell_voltage)))

        # Generate 23 temperatures (mix of cell and ambient temperatures)
        temperatures = []
        for i in range(23):
            if i < 3:  # Onboard thermistors near balancers
                temp = base_temp + random.gauss(0, 2) + 5  # Slightly warmer
            else:  # Cell temperatures
                temp = base_temp + random.gauss(0, 1.5)
                # Add heat based on current load
                temp += abs(self.motor_current) * 0.05
            temperatures.append(temp)

        return telemetry_pb2.BMSSegmentData(
            buck_converter_rail_voltage=3.3 + random.gauss(0, 0.05),
            connected_cell_tap_bitset=0xFFF,  # All 12 cells connected
            degraded_cell_tap_bitset=0x000,   # No degraded cells
            connected_thermistor_bitset=0x7FFFFF,  # All 23 thermistors connected
            cell_voltages=cell_voltages,
            temperatures=temperatures
        )

    def generate_bms_data(self, elapsed_time: float) -> telemetry_pb2.BMSData:
        """Generate realistic BMS (Battery Management System) data."""
        # Update pack temperature with some realistic variation
        self.pack_temperature = 25.0 + 10 * math.sin(elapsed_time * 0.02) + random.gauss(0, 1)
        
        # Calculate currents based on motor load
        positive_current = max(0, self.motor_current + random.gauss(0, 1))
        negative_current = max(0, -min(0, random.gauss(0, 0.5)))  # Minimal negative current
        
        # Generate data for 5 segments (typical for mid-size EV battery)
        segments = []
        for i in range(5):
            segment = self.generate_bms_segment(i, self.pack_temperature + random.gauss(0, 2))
            segments.append(segment)

        return telemetry_pb2.BMSData(
            shutdown_activated=False,
            shutdown_reason=telemetry_pb2.BMSData.SHUTDOWN_REASON_UNSPECIFIED,
            measured_lvs_12v_rail=12.0 + random.gauss(0, 0.2),
            positive_current=positive_current,
            negative_current=negative_current,
            segments=segments
        )

    def generate_inverter_data(self, elapsed_time: float) -> telemetry_pb2.InverterData:
        """Generate realistic Inverter (Motor Controller) data."""
        # Update controller temperature
        ambient_temp = 25.0
        load_factor = abs(self.motor_current) / 150.0  # Normalize current load
        self.controller_temp = ambient_temp + load_factor * 25 + random.gauss(0, 2)
        
        # Motor temperature follows controller but with more thermal mass
        motor_temp = self.controller_temp * 0.8 + random.gauss(0, 1.5)
        
        # Calculate ERPM (Electrical RPM) - typically 7x mechanical RPM for motors
        erpm = int(self.motor_rpm * 7 + random.gauss(0, 50))
        
        # Duty cycle based on throttle position
        duty_cycle = self.throttle_position * 0.9 + random.gauss(0, 0.02)
        duty_cycle = max(0.0, min(1.0, duty_cycle))
        
        # Voltage varies slightly with load
        input_voltage = self.battery_voltage + random.gauss(0, 1)
        
        # Generate limit states based on conditions
        limit_states = telemetry_pb2.InverterData.InverterLimitStates(
            capacitor_temperature=self.controller_temp > 70,
            dc_current_limit=abs(self.motor_current) > 140,
            drive_enable_limit=False,
            igbt_acceleration_limit=False,
            igbt_temperature_limit=self.controller_temp > 80,
            input_voltage_limit=input_voltage < 70 or input_voltage > 90,
            motor_acceleration_temperature_limit=motor_temp > 85,
            motor_temperature_limit=motor_temp > 100,
            rpm_minimum_limit=self.motor_rpm < 100 and self.throttle_position > 0.1,
            rpm_maximum_limit=self.motor_rpm > 3800,
            power_limit=self.motor_current * input_voltage > 50000  # 50kW limit
        )
        
        # Fault code logic
        fault_code = telemetry_pb2.InverterData.FAULT_CODE_NO_FAULTS
        if self.controller_temp > 90:
            fault_code = telemetry_pb2.InverterData.FAULT_CODE_CONTROLLER_OVERTEMPERATURE
        elif motor_temp > 110:
            fault_code = telemetry_pb2.InverterData.FAULT_CODE_MOTOR_OVERTEMPERATURE
        elif input_voltage < 60:
            fault_code = telemetry_pb2.InverterData.FAULT_CODE_UNDERVOLTAGE
        elif input_voltage > 95:
            fault_code = telemetry_pb2.InverterData.FAULT_CODE_OVERVOLTAGE
        elif abs(self.motor_current) > 160:
            fault_code = telemetry_pb2.InverterData.FAULT_CODE_OVERCURRENT

        return telemetry_pb2.InverterData(
            fault_code=fault_code,
            erpm=max(0, erpm),
            duty_cycle=duty_cycle,
            input_dc_voltage=input_voltage,
            ac_motor_current=abs(self.motor_current) + random.gauss(0, 1),
            dc_battery_current=self.motor_current + random.gauss(0, 0.5),
            controller_temperature=self.controller_temp,
            motor_temperature=motor_temp,
            drive_enabled=fault_code == telemetry_pb2.InverterData.FAULT_CODE_NO_FAULTS,
            limit_states=limit_states
        )

    def create_telemetry_packet(self, data_type: int, timestamp_ms: int, **kwargs) -> telemetry_pb2.TelemetryPacket:
        """Create a telemetry packet with the specified data."""
        packet = telemetry_pb2.TelemetryPacket(
            type=data_type,
            timestamp_ms=timestamp_ms
        )
        
        if data_type == telemetry_pb2.TelemetryPacket.DATA_TYPE_APPS:
            packet.apps_data.CopyFrom(kwargs['apps_data'])
        elif data_type == telemetry_pb2.TelemetryPacket.DATA_TYPE_BMS:
            packet.bms_data.CopyFrom(kwargs['bms_data'])
        elif data_type == telemetry_pb2.TelemetryPacket.DATA_TYPE_INVERTER:
            packet.inverter_data.CopyFrom(kwargs['inverter_data'])
            
        return packet

    def send_packet(self, packet: telemetry_pb2.TelemetryPacket) -> bool:
        """Send a telemetry packet over serial."""
        if not self.serial_conn or not self.serial_conn.is_open:
            return False
            
        try:
            data = packet.SerializeToString()
            self.serial_conn.write(data)
            return True
        except Exception as e:
            self.logger.error(f"Failed to send packet: {e}")
            return False

    def run_simulation(self, duration: float = None, packet_rate: float = 10.0):
        """Run the telemetry simulation."""
        if not self.connect():
            return
            
        self.logger.info(f"Starting telemetry simulation at {packet_rate} packets/second")
        if duration:
            self.logger.info(f"Will run for {duration} seconds")
        else:
            self.logger.info("Running indefinitely (Ctrl+C to stop)")
            
        packet_interval = 1.0 / packet_rate
        packet_count = 0
        data_types = [
            telemetry_pb2.TelemetryPacket.DATA_TYPE_APPS,
            telemetry_pb2.TelemetryPacket.DATA_TYPE_BMS,
            telemetry_pb2.TelemetryPacket.DATA_TYPE_INVERTER
        ]
        
        try:
            start_time = time.time()
            last_packet_time = start_time
            
            while True:
                current_time = time.time()
                elapsed_time = current_time - start_time
                
                # Check if we should stop
                if duration and elapsed_time >= duration:
                    break
                    
                # Check if it's time for the next packet
                if current_time - last_packet_time >= packet_interval:
                    timestamp_ms = int(current_time * 1000)
                    
                    # Cycle through data types
                    data_type = data_types[packet_count % len(data_types)]
                    
                    # Generate appropriate data
                    if data_type == telemetry_pb2.TelemetryPacket.DATA_TYPE_APPS:
                        apps_data = self.generate_apps_data(elapsed_time)
                        packet = self.create_telemetry_packet(data_type, timestamp_ms, apps_data=apps_data)
                        self.logger.info(f"APPS: throttle={apps_data.current_throttle_percentage:.2f}, "
                                       f"current={apps_data.current_motor_current:.1f}A, "
                                       f"rpm={apps_data.current_motor_rpm}")
                        
                    elif data_type == telemetry_pb2.TelemetryPacket.DATA_TYPE_BMS:
                        bms_data = self.generate_bms_data(elapsed_time)
                        packet = self.create_telemetry_packet(data_type, timestamp_ms, bms_data=bms_data)
                        total_voltage = sum(sum(seg.cell_voltages) for seg in bms_data.segments)
                        self.logger.info(f"BMS: pack_voltage={total_voltage:.1f}V, "
                                       f"current={bms_data.positive_current:.1f}A, "
                                       f"segments={len(bms_data.segments)}")
                        
                    elif data_type == telemetry_pb2.TelemetryPacket.DATA_TYPE_INVERTER:
                        inverter_data = self.generate_inverter_data(elapsed_time)
                        packet = self.create_telemetry_packet(data_type, timestamp_ms, inverter_data=inverter_data)
                        self.logger.info(f"Inverter: rpm={inverter_data.erpm//7}, "
                                       f"duty={inverter_data.duty_cycle:.2f}, "
                                       f"temp={inverter_data.controller_temperature:.1f}°C, "
                                       f"fault={inverter_data.fault_code}")
                    
                    # Send the packet
                    if self.send_packet(packet):
                        packet_count += 1
                    else:
                        self.logger.error("Failed to send packet, stopping simulation")
                        break
                        
                    last_packet_time = current_time
                    
                # Small sleep to prevent busy waiting
                time.sleep(0.001)
                
        except KeyboardInterrupt:
            self.logger.info("Simulation stopped by user")
        except Exception as e:
            self.logger.error(f"Simulation error: {e}")
        finally:
            self.disconnect()
            self.logger.info(f"Sent {packet_count} packets total")


def list_serial_ports() -> List[str]:
    """List available serial ports."""
    import serial.tools.list_ports
    return [port.device for port in serial.tools.list_ports.comports()]


def main():
    parser = argparse.ArgumentParser(description="Electric Car Telemetry Data Sender")
    parser.add_argument("--port", "-p", help="Serial port (e.g., /dev/ttyUSB0 or COM3)")
    parser.add_argument("--baud", "-b", type=int, default=57600, help="Baud rate (default: 57600)")
    parser.add_argument("--rate", "-r", type=float, default=10.0, help="Packet rate in Hz (default: 10.0)")
    parser.add_argument("--duration", "-d", type=float, help="Duration in seconds (default: run forever)")
    parser.add_argument("--list-ports", "-l", action="store_true", help="List available serial ports")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.list_ports:
        ports = list_serial_ports()
        print("Available serial ports:")
        for port in ports:
            print(f"  {port}")
        return
    
    if not args.port:
        ports = list_serial_ports()
        if ports:
            print("Available serial ports:")
            for port in ports:
                print(f"  {port}")
            print()
            print("Please specify a port with --port <port>")
        else:
            print("No serial ports found. Please connect your device and try again.")
        return
    
    # Create and run the telemetry sender
    sender = TelemetrySender(args.port, args.baud)
    sender.run_simulation(args.duration, args.rate)


if __name__ == "__main__":
    main() 