#!/usr/bin/env python3
"""
Clean Vehicle Telemetry Simulator - No console output contamination

This version sends ONLY clean protobuf data to the serial port with no
logging output that could interfere with the dashboard parsing.
"""

import argparse
import time
import math
import random
import logging
import sys
from telemetry_sender import TelemetrySender

# Redirect all logging to a file instead of console to prevent contamination
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='/tmp/vehicle_simulator.log',  # Log to file, not console
    filemode='w'
)

class CleanVehicleSimulator(TelemetrySender):
    """Vehicle simulator that sends ONLY clean protobuf data."""
    
    def __init__(self, port: str, mission_profile: str = "city", baud_rate: int = 57600):
        # Initialize parent but redirect all logging to file
        super().__init__(port, baud_rate)
        self.mission_profile = mission_profile
        
        # Vehicle state
        self.odometer = 0.0
        self.trip_time = 0.0
        self.energy_consumed = 0.0
        self.last_update_time = 0.0
        
        # Mission profiles (simplified inline)
        self.profiles = {
            'idle': lambda t: {'throttle_target': 0.0, 'base_temp': 25.0, 'scenario': 'Idle'},
            'city': self._city_profile,
            'highway': self._highway_profile,
            'track_day': self._track_profile,
            'efficiency_test': lambda t: {'throttle_target': 0.15 + 0.1 * math.sin(t * 0.05), 'base_temp': 22.0, 'scenario': 'Efficiency'}
        }
        
        # Suppress all console output by redirecting stdout/stderr during serial operations
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
    
    def _city_profile(self, elapsed_time: float) -> dict:
        cycle_time = elapsed_time % 60
        if cycle_time < 15:
            throttle = min(0.4, cycle_time / 15 * 0.4)
        elif cycle_time < 35:
            throttle = 0.3 + 0.1 * math.sin(elapsed_time * 0.3)
        elif cycle_time < 45:
            throttle = max(0.0, 0.3 - (cycle_time - 35) / 10 * 0.3)
        else:
            throttle = 0.0
        return {'throttle_target': throttle, 'base_temp': 30.0, 'scenario': 'City'}
    
    def _highway_profile(self, elapsed_time: float) -> dict:
        if elapsed_time < 10:
            throttle = 0.6 + (elapsed_time / 10) * 0.2
        else:
            base_throttle = 0.75
            passing_cycle = (elapsed_time - 10) % 120
            if 40 < passing_cycle < 60:
                throttle = base_throttle + 0.2
            else:
                throttle = base_throttle + 0.05 * math.sin(elapsed_time * 0.1)
        return {'throttle_target': max(0.0, min(1.0, throttle)), 'base_temp': 35.0, 'scenario': 'Highway'}
    
    def _track_profile(self, elapsed_time: float) -> dict:
        lap_time = elapsed_time % 180
        if lap_time < 120:
            throttle = 0.7 + 0.3 * abs(math.sin(lap_time * 0.1))
        else:
            throttle = 0.2 + 0.1 * math.sin(lap_time * 0.2)
        return {'throttle_target': max(0.0, min(1.0, throttle)), 'base_temp': 45.0, 'scenario': 'Track'}
    
    def connect(self) -> bool:
        """Connect with minimal logging."""
        try:
            import serial
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0
            )
            # Only log to file, not console
            logging.info(f"Connected to {self.port}")
            return True
        except Exception as e:
            logging.error(f"Failed to connect: {e}")
            return False
    
    def send_packet(self, packet) -> bool:
        """Send packet with zero console output."""
        if not self.serial_conn or not self.serial_conn.is_open:
            return False
        try:
            # Temporarily suppress ALL output during serial write
            sys.stdout = open('/dev/null', 'w')
            sys.stderr = open('/dev/null', 'w')
            
            data = packet.SerializeToString()
            self.serial_conn.write(data)
            self.serial_conn.flush()  # Ensure data is sent immediately
            
            # Restore output
            sys.stdout.close()
            sys.stderr.close()
            sys.stdout = self.original_stdout
            sys.stderr = self.original_stderr
            
            return True
        except Exception as e:
            # Restore output in case of error
            try:
                sys.stdout.close()
                sys.stderr.close()
            except:
                pass
            sys.stdout = self.original_stdout
            sys.stderr = self.original_stderr
            logging.error(f"Send error: {e}")
            return False
    
    def generate_clean_data(self, elapsed_time: float):
        """Generate telemetry data without any side effects."""
        profile_func = self.profiles.get(self.mission_profile, self.profiles['city'])
        profile_data = profile_func(elapsed_time)
        
        # Update vehicle state
        if self.last_update_time > 0:
            dt = elapsed_time - self.last_update_time
            speed_kmh = (self.motor_rpm / 4000) * 120
            self.odometer += (speed_kmh * dt) / 3600
            self.energy_consumed += (self.motor_current * self.battery_voltage * dt) / 3600000
        self.last_update_time = elapsed_time
        
        # Smooth throttle transitions
        target_throttle = profile_data['throttle_target']
        throttle_diff = target_throttle - self.throttle_position
        self.throttle_position += throttle_diff * 0.15
        self.throttle_position = max(0.0, min(1.0, self.throttle_position))
        
        # Update vehicle parameters
        self.motor_current = self.throttle_position * 150.0 + random.gauss(0, 3)
        self.motor_rpm = int(self.throttle_position * 4000 + random.gauss(0, 100))
        self.pack_temperature = profile_data['base_temp'] + abs(self.motor_current) * 0.1 + random.gauss(0, 2)
        
        # Controller temperature based on mission
        load_factor = abs(self.motor_current) / 150.0
        if self.mission_profile == "track_day":
            self.controller_temp = profile_data['base_temp'] + load_factor * 35
        elif self.mission_profile == "highway":
            self.controller_temp = profile_data['base_temp'] + load_factor * 25
        else:
            self.controller_temp = profile_data['base_temp'] + load_factor * 20
        self.controller_temp += random.gauss(0, 2)
    
    def run_clean_simulation(self, duration: float = None, packet_rate: float = 10.0):
        """Run simulation with absolutely no console output."""
        if not self.connect():
            print("Failed to connect to serial port", file=sys.stderr)
            return
        
        print(f"🚗 Clean Vehicle Simulator Started")
        print(f"   Profile: {self.mission_profile}")
        print(f"   Port: {self.port}")
        print(f"   Rate: {packet_rate}Hz")
        print(f"   Logging to: /tmp/vehicle_simulator.log")
        print(f"   Press Ctrl+C to stop")
        print()
        
        import telemetry_pb2
        
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
            last_status_time = start_time
            
            while True:
                current_time = time.time()
                elapsed_time = current_time - start_time
                
                if duration and elapsed_time >= duration:
                    break
                
                # Send packets at specified rate
                if current_time - last_packet_time >= packet_interval:
                    timestamp_ms = int(current_time * 1000)
                    data_type = data_types[packet_count % len(data_types)]
                    
                    # Generate clean data
                    self.generate_clean_data(elapsed_time)
                    
                    # Create and send appropriate packet
                    if data_type == telemetry_pb2.TelemetryPacket.DATA_TYPE_APPS:
                        apps_data = super().generate_apps_data(elapsed_time)
                        packet = self.create_telemetry_packet(data_type, timestamp_ms, apps_data=apps_data)
                    elif data_type == telemetry_pb2.TelemetryPacket.DATA_TYPE_BMS:
                        bms_data = super().generate_bms_data(elapsed_time)
                        packet = self.create_telemetry_packet(data_type, timestamp_ms, bms_data=bms_data)
                    elif data_type == telemetry_pb2.TelemetryPacket.DATA_TYPE_INVERTER:
                        inverter_data = super().generate_inverter_data(elapsed_time)
                        packet = self.create_telemetry_packet(data_type, timestamp_ms, inverter_data=inverter_data)
                    
                    if self.send_packet(packet):
                        packet_count += 1
                    
                    last_packet_time = current_time
                
                # Status update every 30 seconds to console (not serial)
                if current_time - last_status_time >= 30:
                    print(f"📊 Packets sent: {packet_count}, Odometer: {self.odometer:.1f}km")
                    last_status_time = current_time
                
                time.sleep(0.001)
                
        except KeyboardInterrupt:
            print(f"\n🛑 Stopped. Final stats: {packet_count} packets, {self.odometer:.1f}km")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            logging.error(f"Simulation error: {e}")
        finally:
            if self.serial_conn:
                self.serial_conn.close()
            logging.info(f"Simulation ended: {packet_count} packets sent")

def main():
    parser = argparse.ArgumentParser(description="Clean Electric Vehicle Telemetry Simulator")
    parser.add_argument("--port", "-p", required=True, help="Serial port (e.g., /dev/ttyUSB0)")
    parser.add_argument("--mission-profile", "-m", 
                       choices=["idle", "city", "highway", "track_day", "efficiency_test"],
                       default="city", help="Driving mission profile")
    parser.add_argument("--baud", "-b", type=int, default=57600, help="Baud rate")
    parser.add_argument("--rate", "-r", type=float, default=10.0, help="Packet rate in Hz")
    parser.add_argument("--duration", "-d", type=float, help="Duration in seconds")
    
    args = parser.parse_args()
    
    simulator = CleanVehicleSimulator(args.port, args.mission_profile, args.baud)
    simulator.run_clean_simulation(args.duration, args.rate)

if __name__ == "__main__":
    main() 