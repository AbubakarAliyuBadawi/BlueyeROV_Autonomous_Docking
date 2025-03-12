# Blueye Drone Docking System

A modular system for guiding a Blueye underwater drone to an autonomous docking station using USBL (Ultra Short Baseline) positioning data with the [Blueye SDK](https://github.com/BluEye-Robotics/blueye.sdk).

## Overview

This system enables a Blueye underwater drone to navigate to a docking station at a specific depth by:

1. Reading relative position data from a USBL system
2. Converting relative coordinates to absolute GPS coordinates
3. Creating a multi-stage mission plan
4. Executing the mission safely with proper monitoring and logging

## Directory Structure

```
blueye-docking-system/
├── src/                     # Source code
│   ├── config.py            # Configuration parameters
│   ├── drone.py             # Drone connection and control
│   ├── mission.py           # Mission building and execution
│   ├── navigation.py        # Navigation strategies
│   ├── utils.py             # Utility functions
│   ├── gui.py               # Graphical user interface
│   ├── dvl_visualizer.py    # 3D DVL data visualization
│   ├── dvl_2d_visualizer.py # 2D DVL data visualization
│   ├── usbl_data.py         # Mock USBL server for testing
│   └── main.py              # Application entry point
├── mission_logs/            # Mission log storage
├── tests/                   # Unit and integration tests
├── docs/                    # Documentation
│   ├── images/              # Diagrams and screenshots
│   └── api/                 # API documentation
├── LICENSE                  # License file
└── README.md                # This file
```

## Module Descriptions

- **config.py**: Central configuration parameters for the entire system
- **utils.py**: Utility functions for logging, coordinate conversion, and USBL data handling
- **navigation.py**: Navigation strategy implementations (three-stage and direct approaches)
- **mission.py**: Mission building, execution, and telemetry logging
- **drone.py**: Drone connection management and mission execution
- **gui.py**: Graphical user interface for system control and visualization
- **dvl_visualizer.py**: 3D visualization of DVL (Doppler Velocity Log) position data
- **dvl_2d_visualizer.py**: 2D visualization of DVL position data
- **usbl_data.py**: Mock USBL server for testing without physical hardware
- **main.py**: Main application entry point with command-line interface

## Features

- **Three-Stage Navigation**: 
  1. Navigate to a point directly above the docking station
  2. Descend to the target depth
  3. Move horizontally to the exact docking position

- **Direct Navigation**: Alternative strategy for a more direct approach (when position is well-known)

- **USBL Integration**: Reads and averages position data from USBL system

- **Coordinate Conversion**: Transforms relative USBL coordinates to absolute GPS coordinates

- **Comprehensive Logging**: Detailed mission logs with telemetry data

- **Configurable Parameters**: Easily adjustable settings for speeds, depths, etc.

- **GUI Interface**: User-friendly interface for mission control and visualization

- **Position Visualization**: Real-time display of drone position using DVL data

## Requirements

- Python 3.6+
- Blueye SDK (`blueye.sdk`)
- NumPy
- PyQt5 for GUI
- Matplotlib for 2D visualization
- PyQtGraph and OpenGL for 3D visualization
- OpenCV (optional, for camera integration)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/blueye-docking-system.git
   cd blueye-docking-system
   ```

2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

3. Install the Blueye SDK according to the [official instructions](https://github.com/BluEye-Robotics/blueye.sdk).

## Usage

### Command Line Interface

Basic usage with default parameters:

```bash
python src/main.py
```

With custom parameters:

```bash
python src/main.py --docking-depth 80.0 --approach-speed 0.25 --drone-ip 192.168.1.101
```

### Command-line Options

#### Drone Settings
- `--drone-ip`: IP address of the Blueye drone (default: 192.168.1.101)
- `--drone-timeout`: Connection timeout in seconds (default: 30)

#### USBL Settings
- `--usbl-ip`: IP address of the USBL system (default: 192.168.1.189)
- `--usbl-port`: Port number of the USBL system (default: 9200)
- `--usbl-samples`: Number of USBL samples to average (default: 5)
- `--no-usbl`: Skip USBL reading and use docking station coordinates directly

#### Docking Station Settings
- `--docking-lat`: Docking station latitude (default: 66.442387)
- `--docking-lon`: Docking station longitude (default: 10.369335)
- `--docking-depth`: Docking station depth in meters (default: 80.0)

#### Mission Settings
- `--timeout`: Maximum mission duration in seconds (default: 1800)
- `--approach-speed`: Horizontal movement speed in m/s (default: 0.3)
- `--descent-speed`: Vertical movement speed in m/s (default: 0.2)
- `--direct-approach`: Use direct approach instead of three-stage approach

### Graphical User Interface

To launch the GUI:

```bash
python src/gui.py
```

The GUI provides:
- Configuration panels for all mission parameters
- USBL connection testing
- Position calculation testing
- Mission execution and monitoring
- Real-time telemetry display
- DVL position visualization
- Camera feed (if available)

## How It Works

### USBL Coordinate Conversion

The system converts USBL relative coordinates (x, y) to absolute GPS coordinates (latitude, longitude) using the following process:

1. Calculate distance from origin: `distance = √(x² + y²)`
2. Calculate bearing angle: `bearing = atan2(x, y)`
3. Apply haversine formula to calculate new coordinates given the docking station position, distance, and bearing

### Navigation Strategies

#### Three-Stage Navigation
The default strategy approaches the docking station in three stages:
1. **Horizontal Approach**: Navigate to a point directly above the docking station at a safe depth
2. **Vertical Descent**: Descend to the docking station depth
3. **Final Approach**: Move horizontally to the exact docking station coordinates

#### Direct Navigation
An alternative strategy that takes a more direct path to the docking station:
- Simultaneously sets target depth and position
- More efficient for shorter distances
- Enable with the `--direct-approach` flag

## Mission Logging

Mission logs are saved to the `mission_logs/` directory in JSON format, with detailed telemetry and status information. Each log includes:

- Mission start and end timestamps
- Drone position and telemetry data
- Mission status at each log point
- Success/failure information

## Extending the System

### Adding a New Navigation Strategy
1. Create a new class in `navigation.py` that extends `NavigationStrategy`
2. Implement the `create_mission()` method
3. Add the new strategy option to `main.py`

### Customizing the GUI
The GUI is built with PyQt5 and can be customized by modifying `gui.py`.

## Troubleshooting

### Connection Issues
- Ensure the drone is powered on and connected to the network
- Verify the IP address is correct (default: 192.168.1.101)
- Check that the USBL system is operational and connected

### USBL Reading Errors
- Verify the USBL system connection settings
- Ensure the transceiver and transducer are functioning properly
- Try increasing the number of samples with `--usbl-samples`

### Mission Execution Problems
- Check the mission logs for detailed error information
- Verify the drone has sufficient battery power
- Ensure the docking station coordinates are accurate
