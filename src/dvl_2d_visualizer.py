#!/usr/bin/env python3
"""
2D DVL Position Visualizer for Blueye Drone

This module provides a 2D visualization widget for displaying drone position data 
from a DVL (Doppler Velocity Log) sensor using matplotlib instead of OpenGL.
"""

import sys
import socket
import json
import threading
import time
from datetime import datetime
from collections import deque
import numpy as np

# PyQt5 imports
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QLabel, QGroupBox, QFormLayout, QLineEdit, QCheckBox,
    QSpinBox, QComboBox, QSplitter
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject

# Matplotlib for 2D plotting
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt


class DVLData:
    """Class for storing and processing DVL data."""
    
    def __init__(self):
        self.position = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.velocity = {"vx": 0.0, "vy": 0.0, "vz": 0.0}
        self.orientation = {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}
        self.altitude = 0.0
        self.timestamp = datetime.now()
        
    def update_position(self, x, y, z, roll=None, pitch=None, yaw=None):
        """Update position data."""
        self.position["x"] = x
        self.position["y"] = y
        self.position["z"] = z
        
        if roll is not None:
            self.orientation["roll"] = roll
        if pitch is not None:
            self.orientation["pitch"] = pitch
        if yaw is not None:
            self.orientation["yaw"] = yaw
            
        self.timestamp = datetime.now()
        
    def update_velocity(self, vx, vy, vz, altitude=None):
        """Update velocity data."""
        self.velocity["vx"] = vx
        self.velocity["vy"] = vy
        self.velocity["vz"] = vz
        
        if altitude is not None:
            self.altitude = altitude
            
        self.timestamp = datetime.now()


class DVLDataReceiver(QObject):
    """Class for receiving DVL data from a socket connection."""
    
    # Define signals
    position_updated = pyqtSignal(float, float, float, float, float, float)
    velocity_updated = pyqtSignal(float, float, float, float)
    connection_status = pyqtSignal(bool, str)
    
    def __init__(self, host="192.168.1.99", port=16171):
        super().__init__()
        self.host = host
        self.port = port
        self.socket = None
        self.running = False
        self.connected = False
        self.dvl_data = DVLData()
        
    def connect(self):
        """Connect to the DVL socket server."""
        if self.connected:
            return True
            
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)
            self.socket.connect((self.host, self.port))
            self.connected = True
            self.connection_status.emit(True, f"Connected to DVL at {self.host}:{self.port}")
            return True
        except Exception as e:
            self.connected = False
            self.connection_status.emit(False, f"Connection failed: {str(e)}")
            return False
    
    def disconnect(self):
        """Disconnect from the DVL socket server."""
        self.running = False
        if self.socket:
            self.socket.close()
            self.socket = None
        self.connected = False
        self.connection_status.emit(False, "Disconnected from DVL")
    
    def start_receiving(self):
        """Start receiving data in a separate thread."""
        if not self.connected:
            if not self.connect():
                return False
                
        self.running = True
        receiver_thread = threading.Thread(target=self._receive_data)
        receiver_thread.daemon = True
        receiver_thread.start()
        return True
    
    def _receive_data(self):
        """Receive and process DVL data."""
        if not self.socket:
            return
            
        buffer = b""
        
        while self.running:
            try:
                data = self.socket.recv(2048)
                if not data:
                    # Connection closed
                    self.connection_status.emit(False, "Connection closed by server")
                    break
                    
                buffer += data
                
                # Process complete JSON messages
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    try:
                        self._process_message(line.decode('utf-8'))
                    except:
                        # Skip invalid messages
                        pass
                        
            except socket.timeout:
                # Socket timeout, continue
                continue
                
            except socket.error as e:
                # Socket error
                self.connection_status.emit(False, f"Socket error: {str(e)}")
                break
                
            except Exception as e:
                # Other error
                self.connection_status.emit(False, f"Error: {str(e)}")
                break
                
        # Clean up
        self.disconnect()
    
    def _process_message(self, message):
        """Process a DVL message."""
        try:
            data = json.loads(message)
            data_type = data.get("type")
            
            if data_type == "velocity":
                # Process velocity data
                vx = data.get("vx", 0.0)
                vy = data.get("vy", 0.0)
                vz = data.get("vz", 0.0)
                altitude = data.get("altitude", 0.0)
                
                # Update internal data
                self.dvl_data.update_velocity(vx, vy, vz, altitude)
                
                # Emit signal
                self.velocity_updated.emit(vx, vy, vz, altitude)
                
            elif data_type == "position_local":
                # Process position data
                x = data.get("x", 0.0)
                y = data.get("y", 0.0)
                z = data.get("z", 0.0)
                roll = data.get("roll", 0.0)
                pitch = data.get("pitch", 0.0)
                yaw = data.get("yaw", 0.0)
                
                # Update internal data
                self.dvl_data.update_position(x, y, z, roll, pitch, yaw)
                
                # Emit signal
                self.position_updated.emit(x, y, z, roll, pitch, yaw)
                
        except json.JSONDecodeError:
            # Invalid JSON, ignore
            pass
        except Exception as e:
            # Other error
            print(f"Error processing message: {str(e)}")


class MockDVLDataGenerator(QObject):
    """Class for generating mock DVL data for testing."""
    
    # Define signals (same as DVLDataReceiver for compatibility)
    position_updated = pyqtSignal(float, float, float, float, float, float)
    velocity_updated = pyqtSignal(float, float, float, float)
    connection_status = pyqtSignal(bool, str)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.connected = False
        self.dvl_data = DVLData()
        self.timer = QTimer()
        self.timer.timeout.connect(self._generate_data)
        
        # Path parameters
        self.path_type = "circle"  # circle, square, helix
        self.center_x = 0.0
        self.center_y = 0.0
        self.center_z = 0.0
        self.radius = 5.0
        self.speed = 0.5
        self.noise = 0.2
        
        # For circular and square paths
        self.angle = 0.0
        
    def connect(self):
        """Simulate connection."""
        self.connected = True
        self.connection_status.emit(True, "Connected to mock DVL data generator")
        return True
    
    def disconnect(self):
        """Simulate disconnection."""
        self.running = False
        self.timer.stop()
        self.connected = False
        self.connection_status.emit(False, "Disconnected from mock DVL data generator")
    
    def start_receiving(self):
        """Start generating mock data."""
        if not self.connected:
            self.connect()
            
        self.running = True
        self.timer.start(100)  # Generate data every 100ms
        return True
    
    def _generate_data(self):
        """Generate mock DVL data."""
        if not self.running:
            return
            
        # Update position based on path type
        if self.path_type == "circle":
            # Circular path
            self.angle += self.speed * 0.1  # 0.1 seconds * speed
            if self.angle >= 360:
                self.angle -= 360
                
            x = self.center_x + self.radius * np.cos(np.radians(self.angle))
            y = self.center_y + self.radius * np.sin(np.radians(self.angle))
            z = self.center_z
            
            # Calculate orientation based on movement direction
            yaw = (self.angle + 90) % 360  # Tangent to the circle
            roll = 0
            pitch = 0
            
        elif self.path_type == "square":
            # Square path
            self.angle += self.speed * 0.1
            if self.angle >= 4:
                self.angle = 0
                
            segment = int(np.floor(self.angle))
            progress = self.angle - segment
            
            if segment == 0:
                # Moving along the bottom edge (x increasing)
                x = self.center_x + self.radius * (-1 + 2 * progress)
                y = self.center_y - self.radius
                yaw = 0
            elif segment == 1:
                # Moving along the right edge (y increasing)
                x = self.center_x + self.radius
                y = self.center_y + self.radius * (-1 + 2 * progress)
                yaw = 90
            elif segment == 2:
                # Moving along the top edge (x decreasing)
                x = self.center_x + self.radius * (1 - 2 * progress)
                y = self.center_y + self.radius
                yaw = 180
            else:  # segment == 3
                # Moving along the left edge (y decreasing)
                x = self.center_x - self.radius
                y = self.center_y + self.radius * (1 - 2 * progress)
                yaw = 270
                
            z = self.center_z
            roll = 0
            pitch = 0
            
        else:  # helix
            # Helical path
            self.angle += self.speed * 0.1
            if self.angle >= 360:
                self.angle -= 360
                self.center_z -= 1.0  # Descend after each complete circle
                
            x = self.center_x + self.radius * np.cos(np.radians(self.angle))
            y = self.center_y + self.radius * np.sin(np.radians(self.angle))
            z = self.center_z
            
            yaw = (self.angle + 90) % 360
            roll = 0
            pitch = 0
        
        # Add noise
        x += (np.random.random() - 0.5) * self.noise
        y += (np.random.random() - 0.5) * self.noise
        z += (np.random.random() - 0.5) * self.noise
        
        # Calculate velocities from position changes
        vx = self.speed * np.cos(np.radians(yaw))
        vy = self.speed * np.sin(np.radians(yaw))
        vz = 0.0 if self.path_type != "helix" else -0.05  # slight downward velocity for helix
        
        # Calculate altitude (distance to "bottom")
        altitude = abs(z - self.center_z) + 5.0  # Add 5m as a base altitude
        
        # Update internal data
        self.dvl_data.update_position(x, y, z, roll, pitch, yaw)
        self.dvl_data.update_velocity(vx, vy, vz, altitude)
        
        # Emit signals
        self.position_updated.emit(x, y, z, roll, pitch, yaw)
        self.velocity_updated.emit(vx, vy, vz, altitude)


class MatplotlibCanvas(FigureCanvas):
    """Matplotlib canvas for embedding plots in PyQt."""
    
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(MatplotlibCanvas, self).__init__(self.fig)


class DVL2DVisualizer(QWidget):
    """Main widget for 2D visualization of DVL data."""
    
    def __init__(self, parent=None, use_mock_data=True):
        super().__init__(parent)
        self.parent = parent
        self.use_mock_data = use_mock_data
        
        # Data management
        self.max_trail_points = 500
        self.position_history = {
            'x': deque(maxlen=self.max_trail_points),
            'y': deque(maxlen=self.max_trail_points),
            'z': deque(maxlen=self.max_trail_points),
            'time': deque(maxlen=self.max_trail_points)
        }
        self.start_time = time.time()
        
        # Set up data receiver
        if self.use_mock_data:
            self.data_receiver = MockDVLDataGenerator()
        else:
            self.data_receiver = DVLDataReceiver()
        
        # Connect signals
        self.data_receiver.position_updated.connect(self.on_position_updated)
        self.data_receiver.velocity_updated.connect(self.on_velocity_updated)
        self.data_receiver.connection_status.connect(self.on_connection_status)
        
        # Set up UI
        self.setup_ui()
        
        # Set up plot update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plots)
        self.update_timer.start(100)  # Update every 100ms
    
    def setup_ui(self):
        """Set up the user interface."""
        main_layout = QVBoxLayout(self)
        
        # Control panel
        control_layout = QHBoxLayout()
        main_layout.addLayout(control_layout)
        
        # Connection controls
        connection_group = QGroupBox("Connection")
        connection_layout = QFormLayout(connection_group)
        control_layout.addWidget(connection_group)
        
        if not self.use_mock_data:
            # Add connection settings for real DVL
            self.ip_edit = QLineEdit("192.168.1.99")
            connection_layout.addRow(QLabel("DVL IP:"), self.ip_edit)
            
            self.port_edit = QSpinBox()
            self.port_edit.setRange(1000, 65535)
            self.port_edit.setValue(16171)
            connection_layout.addRow(QLabel("DVL Port:"), self.port_edit)
        else:
            # Add settings for mock data generator
            self.path_combo = QComboBox()
            self.path_combo.addItems(["circle", "square", "helix"])
            self.path_combo.currentTextChanged.connect(self.on_path_changed)
            connection_layout.addRow(QLabel("Path Type:"), self.path_combo)
            
            self.speed_spin = QSpinBox()
            self.speed_spin.setRange(1, 10)
            self.speed_spin.setValue(5)
            self.speed_spin.valueChanged.connect(self.on_speed_changed)
            connection_layout.addRow(QLabel("Speed:"), self.speed_spin)
        
        # Connect button
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.on_connect_clicked)
        connection_layout.addRow(self.connect_button)
        
        # Status display
        self.status_label = QLabel("Not connected")
        connection_layout.addRow(QLabel("Status:"), self.status_label)
        
        # Visualization controls
        viz_group = QGroupBox("Visualization")
        viz_layout = QFormLayout(viz_group)
        control_layout.addWidget(viz_group)
        
        self.trail_check = QCheckBox()
        self.trail_check.setChecked(True)
        viz_layout.addRow(QLabel("Show Trail:"), self.trail_check)
        
        self.trail_length_spin = QSpinBox()
        self.trail_length_spin.setRange(10, 5000)
        self.trail_length_spin.setSingleStep(10)
        self.trail_length_spin.setValue(self.max_trail_points)
        self.trail_length_spin.valueChanged.connect(self.on_trail_length_changed)
        viz_layout.addRow(QLabel("Trail Length:"), self.trail_length_spin)
        
        self.clear_button = QPushButton("Clear Plots")
        self.clear_button.clicked.connect(self.clear_plots)
        viz_layout.addRow(self.clear_button)
        
        # Telemetry display
        telemetry_group = QGroupBox("Telemetry")
        telemetry_layout = QFormLayout(telemetry_group)
        control_layout.addWidget(telemetry_group)
        
        self.position_label = QLabel("x: 0.0 m, y: 0.0 m, z: 0.0 m")
        telemetry_layout.addRow(QLabel("Position:"), self.position_label)
        
        self.velocity_label = QLabel("vx: 0.0 m/s, vy: 0.0 m/s, vz: 0.0 m/s")
        telemetry_layout.addRow(QLabel("Velocity:"), self.velocity_label)
        
        self.orientation_label = QLabel("roll: 0.0°, pitch: 0.0°, yaw: 0.0°")
        telemetry_layout.addRow(QLabel("Orientation:"), self.orientation_label)
        
        self.altitude_label = QLabel("0.0 m")
        telemetry_layout.addRow(QLabel("Altitude:"), self.altitude_label)
        
        # Create plot layout
        plot_layout = QHBoxLayout()
        main_layout.addLayout(plot_layout, stretch=1)
        
        # 2D plots
        # XY Plot (top view)
        self.xy_canvas = MatplotlibCanvas(self, width=5, height=4, dpi=100)
        self.xy_canvas.axes.set_title('XY Position (Top View)')
        self.xy_canvas.axes.set_xlabel('X (meters)')
        self.xy_canvas.axes.set_ylabel('Y (meters)')
        self.xy_canvas.axes.grid(True)
        self.xy_canvas.axes.axis('equal')  # Equal aspect ratio
        plot_layout.addWidget(self.xy_canvas)
        
        # Depth Plot (depth vs time)
        self.depth_canvas = MatplotlibCanvas(self, width=5, height=4, dpi=100)
        self.depth_canvas.axes.set_title('Depth vs Time')
        self.depth_canvas.axes.set_xlabel('Time (seconds)')
        self.depth_canvas.axes.set_ylabel('Depth (meters)')
        self.depth_canvas.axes.grid(True)
        self.depth_canvas.axes.invert_yaxis()  # Depth increases downward
        plot_layout.addWidget(self.depth_canvas)
        
        # Initialize plot elements
        self.xy_scatter = self.xy_canvas.axes.scatter([], [], c='b', marker='o', s=30)
        self.xy_trail, = self.xy_canvas.axes.plot([], [], 'b-', alpha=0.5)
        self.xy_canvas.axes.set_xlim(-10, 10)
        self.xy_canvas.axes.set_ylim(-10, 10)
        
        self.depth_scatter = self.depth_canvas.axes.scatter([], [], c='r', marker='o', s=30)
        self.depth_trail, = self.depth_canvas.axes.plot([], [], 'r-', alpha=0.5)
        self.depth_canvas.axes.set_xlim(0, 60)  # 60 seconds of data
        self.depth_canvas.axes.set_ylim(0, 10)  # 0-10m depth
        
        # Set initial size
        self.resize(1000, 800)
    
    def on_connect_clicked(self):
        """Handle connect button click."""
        if self.data_receiver.connected:
            # Disconnect
            self.data_receiver.disconnect()
            self.connect_button.setText("Connect")
            self.status_label.setText("Not connected")
        else:
            # Connect
            if not self.use_mock_data:
                # Update connection settings from UI
                self.data_receiver.host = self.ip_edit.text()
                self.data_receiver.port = self.port_edit.value()
            
            success = self.data_receiver.start_receiving()
            if success:
                self.connect_button.setText("Disconnect")
            else:
                self.status_label.setText("Connection failed")
    
    def on_connection_status(self, connected, message):
        """Handle connection status updates."""
        self.status_label.setText(message)
        if connected:
            self.connect_button.setText("Disconnect")
        else:
            self.connect_button.setText("Connect")
    
    def on_position_updated(self, x, y, z, roll, pitch, yaw):
        """Handle position updates from DVL."""
        current_time = time.time() - self.start_time
        
        # Update position display
        self.position_label.setText(f"x: {x:.2f} m, y: {y:.2f} m, z: {z:.2f} m")
        self.orientation_label.setText(f"roll: {roll:.2f}°, pitch: {pitch:.2f}°, yaw: {yaw:.2f}°")
        
        # Store position in history
        self.position_history['x'].append(x)
        self.position_history['y'].append(y)
        self.position_history['z'].append(z)
        self.position_history['time'].append(current_time)
    
    def on_velocity_updated(self, vx, vy, vz, altitude):
        """Handle velocity updates from DVL."""
        # Update velocity display
        self.velocity_label.setText(f"vx: {vx:.2f} m/s, vy: {vy:.2f} m/s, vz: {vz:.2f} m/s")
        self.altitude_label.setText(f"{altitude:.2f} m")
    
    def update_plots(self):
        """Update the plots with current data."""
        if not self.position_history['x']:
            return  # No data yet
            
        # Update XY plot
        x_data = list(self.position_history['x'])
        y_data = list(self.position_history['y'])
        
        if self.trail_check.isChecked():
            self.xy_trail.set_data(x_data, y_data)
        else:
            self.xy_trail.set_data([], [])
            
        # Always update the current position marker
        self.xy_scatter.set_offsets([[x_data[-1], y_data[-1]]])
        
        # Auto-adjust limits if needed
        max_x = max(abs(min(x_data)), abs(max(x_data)))
        max_y = max(abs(min(y_data)), abs(max(y_data)))
        max_range = max(max_x, max_y) * 1.1  # Add 10% margin
        
        self.xy_canvas.axes.set_xlim(-max_range, max_range)
        self.xy_canvas.axes.set_ylim(-max_range, max_range)
        
        # Update depth plot
        time_data = list(self.position_history['time'])
        z_data = list(self.position_history['z'])
        
        if self.trail_check.isChecked():
            self.depth_trail.set_data(time_data, z_data)
        else:
            self.depth_trail.set_data([], [])
            
        # Always update the current depth marker
        self.depth_scatter.set_offsets([[time_data[-1], z_data[-1]]])
        
        # Auto-adjust limits if needed
        max_time = max(time_data)
        min_z = min(z_data) * 0.9  # Add 10% margin below
        max_z = max(z_data) * 1.1  # Add 10% margin above
        
        self.depth_canvas.axes.set_xlim(max(0, max_time - 60), max(60, max_time))  # Show last 60s
        self.depth_canvas.axes.set_ylim(max_z, min_z)  # Inverted Y axis
        
        # Redraw canvases
        self.xy_canvas.draw()
        self.depth_canvas.draw()
    
    def on_trail_length_changed(self, value):
        """Handle trail length change."""
        self.max_trail_points = value
        # Create new deques with the new maxlen
        old_x = list(self.position_history['x'])
        old_y = list(self.position_history['y'])
        old_z = list(self.position_history['z'])
        old_time = list(self.position_history['time'])
        
        self.position_history = {
            'x': deque(old_x[-value:] if len(old_x) > value else old_x, maxlen=value),
            'y': deque(old_y[-value:] if len(old_y) > value else old_y, maxlen=value),
            'z': deque(old_z[-value:] if len(old_z) > value else old_z, maxlen=value),
            'time': deque(old_time[-value:] if len(old_time) > value else old_time, maxlen=value)
        }
    
    def on_path_changed(self, path_type):
        """Handle path type change for mock data generator."""
        if hasattr(self.data_receiver, 'path_type'):
            self.data_receiver.path_type = path_type
    
    def on_speed_changed(self, speed):
        """Handle speed change for mock data generator."""
        if hasattr(self.data_receiver, 'speed'):
            self.data_receiver.speed = speed / 10.0  # Scale for better UI
    
    def clear_plots(self):
        """Clear all plot data."""
        self.position_history = {
            'x': deque(maxlen=self.max_trail_points),
            'y': deque(maxlen=self.max_trail_points),
            'z': deque(maxlen=self.max_trail_points),
            'time': deque(maxlen=self.max_trail_points)
        }
        self.start_time = time.time()
        
        # Reset plot elements
        self.xy_trail.set_data([], [])
        self.xy_scatter.set_offsets([[0, 0]])
        self.depth_trail.set_data([], [])
        self.depth_scatter.set_offsets([[0, 0]])
        
        # Redraw canvases
        self.xy_canvas.draw()
        self.depth_canvas.draw()
    
    def closeEvent(self, event):
        """Handle widget close event."""
        # Disconnect from DVL
        if self.data_receiver.connected:
            self.data_receiver.disconnect()
        
        # Stop update timer
        self.update_timer.stop()
        
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Parse command line arguments
    use_mock = False
    if len(sys.argv) > 1 and sys.argv[1] == "--real":
        use_mock = False
    
    # Create and show the visualizer
    visualizer = DVL2DVisualizer(use_mock_data=False)
    visualizer.show()
    
    sys.exit(app.exec_())
