# Cleansend

A streamlined Python project for generating realistic electric vehicle telemetry data for testing the dashboard. This project creates protobuf-formatted data matching the exact specifications used by the dashboard's serial communication system.

## Quick Start

### Prerequisites

- Python 3.8+ (managed by [uv](https://docs.astral.sh/uv/))
- Linux system with `/dev/ttyUSB*` or similar serial ports
- Optional: **2x SiK Radios** for realistic two-radio testing

### Installation

```bash
# The project uses uv for dependency management
cd cleansend

# Install dependencies (automatic with uv)
uv run python cleansend.py --help
```

## Project Structure

```
cleansend/
├── cleansend.py # Main vehicle simulation with mission profiles
├── telemetry_sender.py        # Base telemetry data generator class
├── telemetry_pb2.py           # Generated Python protobuf code
├── telemetry.proto            # Protobuf schema definition
├── pyproject.toml             # Project dependencies
├── uv.lock                    # Dependency lock file
├── README.md                  # This file
└── .python-version            # Python version specification
```

## Usage

### Vehicle Simulator

Simulate realistic electric vehicle behavior with mission profiles:

```bash
# City driving simulation
uv run python cleansend.py --port /dev/ttyUSB0 --mission-profile city

# Highway cruising
uv run python cleansend.py --port /dev/ttyUSB0 --mission-profile highway

# Track day (aggressive driving)
uv run python cleansend.py --port /dev/ttyUSB0 --mission-profile track_day

# Efficiency test (gentle driving)
uv run python cleansend.py --port /dev/ttyUSB0 --mission-profile efficiency_test

# Parked/idle vehicle
uv run python cleansend.py --port /dev/ttyUSB0 --mission-profile idle
```

#### Available Mission Profiles:
- **`city`**: Stop/start traffic patterns, 0-40% throttle, 60s cycles
- **`highway`**: Sustained cruising, 60-95% throttle, passing maneuvers  
- **`track_day`**: Aggressive driving, 70-100% throttle, high thermal stress
- **`efficiency_test`**: Gentle eco-driving, 10-25% throttle
- **`idle`**: Parked vehicle, minimal activity

## Two-Radio Setup (Realistic Testing)

For the most realistic testing, use two SiK radios: one for the "vehicle" and one for the dashboard.

### Quick Two-Radio Setup:

1. **Configure both radios** with matching settings (NET_ID, frequency, etc.)

2. **Start vehicle simulator** on first radio:
   ```bash
   cd cleansend
   uv run python cleansend.py --port /dev/ttyUSB0 --mission-profile highway
   ```

3. **Start dashboard** and connect to second radio:
   ```bash
   cd dashboard
   bun run dev
   # Browser: Connect to /dev/ttyUSB1
   ```

4. **Watch live telemetry** from simulated vehicle!

## Generated Data Types

### APPS (Accelerator Pedal Position Sensor)
- **Throttle Position**: 0-100% with realistic acceleration patterns
- **Motor Current**: 0-150A based on throttle position
- **Motor RPM**: 0-4000 RPM with realistic response
- **State**: Running, calibrating, error states

### BMS (Battery Management System)
- **Pack Voltage**: Calculated from individual cell voltages
- **Current**: Positive/negative current measurements
- **Segments**: 5 battery segments with 12 cells each
- **Cell Voltages**: 3.0-4.3V per cell with realistic variation
- **Temperatures**: 23 thermistors per segment
- **Shutdown Status**: Normal operation or fault conditions

### Inverter (Motor Controller)
- **Motor Control**: RPM, duty cycle, drive enable status
- **Electrical Values**: Voltage, current measurements
- **Temperature**: Controller and motor temperature monitoring
- **Fault Codes**: NO_FAULTS, overcurrent, overtemperature, etc.
- **Limit States**: Various protection limits and thresholds

## Command Line Options

### cleansend.py

```bash
uv run python cleansend.py [OPTIONS]

Options:
  -p, --port PORT         SiK radio serial port (e.g., /dev/ttyUSB0) [REQUIRED]
  -m, --mission-profile   Mission profile: idle, city, highway, track_day, efficiency_test
  -b, --baud RATE         Baud rate (default: 57600)
  -r, --rate HZ           Packet rate in Hz (default: 10.0)
  -d, --duration SEC      Duration in seconds (default: run forever)
  -h, --help              Show help message
```

### Examples

```bash
# Highway simulation
uv run python cleansend.py -p /dev/ttyUSB0 -m highway

# High-frequency track day simulation
uv run python cleansend.py -p /dev/ttyUSB0 -m track_day -r 20.0

# 5-minute city driving test
uv run python cleansend.py -p /dev/ttyUSB0 -m city -d 300

# Test with different baud rate
uv run python cleansend.py -p /dev/ttyUSB0 -m efficiency_test -b 115200
```

## Dashboard Integration

### Two-Radio Testing (Recommended)

1. **Configure SiK radios** with matching settings

2. **Start vehicle simulator**:
   ```bash
   cd cleansend
   uv run python cleansend.py --port /dev/ttyUSB0 --mission-profile highway
   ```

3. **Start dashboard and connect to second radio**:
   ```bash
   cd dashboard
   bun run dev
   # Browser: Connect to /dev/ttyUSB1
   ```

## Data Format

### Protobuf Wire Format

The system uses Protocol Buffers for efficient binary serialization:

```protobuf
message TelemetryPacket {
  enum DataType {
    DATA_TYPE_APPS = 1;
    DATA_TYPE_BMS = 2;
    DATA_TYPE_INVERTER = 3;
  }
  
  DataType type = 1;
  uint64 timestamp_ms = 2;
  
  oneof payload {
    APPSData apps_data = 3;
    BMSData bms_data = 4;
    InverterData inverter_data = 5;
  }
}
```

### Packet Sizes
- **APPS packets**: ~25-40 bytes
- **BMS packets**: ~800-1200 bytes (depends on segment count)
- **Inverter packets**: ~45-60 bytes

### Update Rate
- Default: 10Hz (3.33Hz per data type)
- Configurable: 1-100Hz
- Production: Typically 5-20Hz

## Troubleshooting

### Serial Port Issues

**Permission Denied**:
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER

# Or set permissions directly
sudo chmod 666 /dev/ttyUSB0
```

**Port Not Found**:
```bash
# List all USB devices
lsusb

# Check kernel messages
dmesg | tail

# List all serial ports
ls -la /dev/tty*
```

### Two-Radio Issues

**No communication between radios**:
```bash
# Test basic radio link
echo "test" > /dev/ttyUSB0
cat /dev/ttyUSB1  # Should show "test"

# Check radio configuration (NET_ID, frequency must match)
```

**Dashboard not receiving data**:
1. **Check Browser**: Use Chrome or Edge (Web Serial API required)
2. **Check Port**: Verify connecting to correct radio port
3. **Check Data**: Use dashboard test page to verify protobuf mode
4. **Check Logs**: Check `/tmp/vehicle_simulator.log` for errors

## Development

### Adding New Mission Profiles

Add new profiles by modifying the `profiles` dictionary in `cleansend.py`:

```python
def _custom_profile(self, elapsed_time: float) -> dict:
    return {
        'throttle_target': 0.5,  # 50% throttle
        'base_temp': 30.0,       # Base temperature
        'scenario': 'Custom Driving'
    }
```

### Features

The clean vehicle simulator includes:

- **Physics-based relationships**: Throttle → Current → Heat → RPM
- **Mission-specific behavior**: Different thermal and load characteristics
- **Realistic noise**: Gaussian noise on sensor readings
- **Trip statistics**: Odometer, energy consumption tracking
- **Thermal modeling**: Load-dependent temperature rise
- **Clean output**: All logging goes to `/tmp/vehicle_simulator.log`

## License

This project follows the MIT license.

**Happy Testing!**
