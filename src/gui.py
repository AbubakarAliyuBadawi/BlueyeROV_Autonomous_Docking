#!/usr/bin/env python3
"""
GUI for the Blueye docking system - Fixed version
"""
import math
import sys
import os
import time
import json
import threading
from datetime import datetime
from pathlib import Path
import cv2
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QImage, QPixmap
from dvl_visualizer import DVLVisualizer
from dvl_2d_visualizer import DVL2DVisualizer

# Force the X11 backend for Linux systems
os.environ["QT_QPA_PLATFORM"] = "xcb"

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QGroupBox, QFormLayout,
    QTextEdit, QTabWidget, QComboBox, QCheckBox, QSpinBox,
    QDoubleSpinBox, QFileDialog, QMessageBox, QSplitter
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont, QIcon, QTextCursor

# Import system components - adjust these imports as needed for your setup
from config import Config
from utils import setup_logging, CoordinateConverter, USBLReader, USBLData
from navigation import ThreeStageNavigation, DirectNavigation
from drone import DroneManager
from mission import MissionManager


class MissionWorker(QThread):
    """Worker thread for running missions without blocking the GUI."""
    
    # Define signals - using simple types to avoid threading issues
    status_signal = pyqtSignal(str, bool)  # message, is_error
    mission_started = pyqtSignal()
    mission_completed = pyqtSignal(bool, str)  # success, message
    telemetry_signal = pyqtSignal(str)  # JSON-formatted telemetry
    
    def __init__(self, config, navigation_strategy, use_usbl=True):
        super().__init__()
        self.config = config
        self.navigation_strategy = navigation_strategy
        self.use_usbl = use_usbl
        self.is_running = False
        self.drone_manager = None
        self.mission_manager = None
    
    def run(self):
        """Main execution method for the thread."""
        self.is_running = True
        self.status_signal.emit("Starting mission...", False)
        
        try:
            # Initialize drone manager
            self.drone_manager = DroneManager(
                ip=self.config.DRONE_IP,
                timeout=self.config.DRONE_CONNECT_TIMEOUT
            )
            
            # Connect to drone
            self.status_signal.emit("Connecting to drone...", False)
            if not self.drone_manager.connect():
                self.status_signal.emit("Failed to connect to drone.", True)
                self.mission_completed.emit(False, "Drone connection failed")
                return
            
            # Get drone position from USBL if requested
            drone_position = None
            
            if self.use_usbl:
                self.status_signal.emit("Getting drone position from USBL...", False)
                usbl_data = self._get_usbl_data()
                
                if not usbl_data:
                    self.status_signal.emit("Could not get USBL data. Using default position.", True)
                else:
                    # Convert relative coordinates to absolute position
                    drone_lat, drone_lon = CoordinateConverter.relative_to_absolute(
                        self.config.DOCKING_LAT, self.config.DOCKING_LON, usbl_data.x, usbl_data.y
                    )
                    
                    drone_position = {
                        'lat': drone_lat,
                        'lon': drone_lon
                    }
                    
                    self.status_signal.emit(f"Drone position: lat={drone_lat:.6f}, lon={drone_lon:.6f}", False)
            
            # If USBL is not used or failed, use default position
            if not drone_position:
                # Use docking station coordinates as a placeholder
                drone_position = {
                    'lat': self.config.DOCKING_LAT,
                    'lon': self.config.DOCKING_LON,
                }
                self.status_signal.emit(f"Using default position: lat={drone_position['lat']:.6f}, lon={drone_position['lon']:.6f}", False)
            
            # Set up docking station position
            docking_position = {
                'lat': self.config.DOCKING_LAT,
                'lon': self.config.DOCKING_LON,
                'depth': self.config.DOCKING_DEPTH
            }
            
            # Initialize mission manager with telemetry callback
            self.mission_manager = MissionManager(
                navigation_strategy=self.navigation_strategy,
                config=self.config
            )
            
            # Define telemetry callback
            def telemetry_callback(mission_status, telemetry):
                if not self.is_running:
                    return
                
                # Create a combined data structure
                data = {
                    "timestamp": datetime.now().isoformat(),
                    "mission_status": {
                        "state": mission_status.state.name,
                        "time_elapsed": mission_status.time_elapsed,
                        "estimated_time_remaining": mission_status.estimated_time_to_complete,
                        "distance_to_complete": mission_status.distance_to_complete,
                        "completed_instructions": len(mission_status.completed_instruction_ids),
                        "total_instructions": mission_status.total_number_of_instructions
                    },
                    "telemetry": {
                        "depth": telemetry.get("depth") if telemetry else None,
                        "water_temperature": telemetry.get("water_temperature") if telemetry else None,
                        "battery": telemetry.get("battery") if telemetry else None
                    }
                }
                
                # Convert to JSON string for safe thread communication
                try:
                    self.telemetry_signal.emit(json.dumps(data))
                except Exception as e:
                    self.status_signal.emit(f"Error sending telemetry: {str(e)}", True)
            
            # Start the mission
            self.status_signal.emit("Building mission...", False)
            mission = self.mission_manager.build_mission(
                drone_position=drone_position,
                target_position=docking_position
            )
            
            # Start mission logging
            self.mission_manager.start_mission_logging(
                mission_name=mission.name,
                drone_info={"position": drone_position},
                target_info=docking_position
            )
            
            # Emit signal that mission has started
            self.mission_started.emit()
            
            # Execute the mission
            self.status_signal.emit(f"Executing mission: {mission.name}", False)
            success = self.drone_manager.run_mission(
                mission=mission,
                max_duration=self.config.MAX_MISSION_DURATION,
                telemetry_callback=telemetry_callback
            )
            
            # End mission logging
            reason = "Completed successfully" if success else "Failed or aborted"
            log_path = self.mission_manager.end_mission_logging(
                success=success,
                reason=reason
            )
            
            # Emit signal that mission has completed
            self.mission_completed.emit(success, f"Mission {reason}. Log saved to {log_path}")
            
        except Exception as e:
            self.status_signal.emit(f"Error during mission: {str(e)}", True)
            self.mission_completed.emit(False, f"Error: {str(e)}")
        
        finally:
            # Clean up
            if self.drone_manager:
                self.status_signal.emit("Disconnecting from drone...", False)
                self.drone_manager.disconnect()
            
            self.is_running = False
    
    def _get_usbl_data(self):
        """Get USBL data from the USBL system."""
        try:
            # Connect to USBL and get position
            usbl_reader = USBLReader(
                host=self.config.USBL_IP,
                port=self.config.USBL_PORT,
                timeout=5  # Use a shorter timeout for UI responsiveness
            )
            
            if not usbl_reader.connect():
                self.status_signal.emit("Failed to connect to USBL.", True)
                return None
            
            try:
                # Read USBL data
                self.status_signal.emit(f"Reading {self.config.USBL_SAMPLES} USBL samples...", False)
                usbl_data = usbl_reader.read_data(
                    num_samples=min(self.config.USBL_SAMPLES, 3),  # Limit samples for UI
                    timeout=10  # Shorter timeout
                )
                
                if not usbl_data:
                    self.status_signal.emit("Failed to read USBL data.", True)
                    return None
                
                self.status_signal.emit(
                    f"USBL data: x={usbl_data.x:.2f}m, y={usbl_data.y:.2f}m, heading={usbl_data.heading:.2f}°", 
                    False
                )
                return usbl_data
            finally:
                # Always disconnect from USBL
                usbl_reader.disconnect()
        except Exception as e:
            self.status_signal.emit(f"Error reading USBL data: {str(e)}", True)
            return None
    
    def stop(self):
        """Stop the mission if it's running."""
        if not self.is_running:
            return
        
        self.is_running = False
        self.status_signal.emit("Stopping mission...", False)
        
        # Try to stop the mission
        if self.drone_manager:
            try:
                if self.drone_manager.drone and self.drone_manager.drone.connected:
                    self.drone_manager.drone.mission.stop()
                    self.status_signal.emit("Mission stopped.", False)
            except Exception as e:
                self.status_signal.emit(f"Error stopping mission: {str(e)}", True)


class DockingSystemGUI(QMainWindow):
    """Main GUI window for the docking system."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Blueye Docking System")
        self.resize(1000, 800)
        
        # Initialize class variables
        self.config = Config()
        self.mission_worker = None
        self.mission_log_path = Path("mission_logs")
        self.mission_log_path.mkdir(exist_ok=True, parents=True)
        
        # Set up the UI
        self._setup_ui()
        
        # Load default config values into UI
        self._load_config_to_ui()
    
    def _setup_ui(self):
        """Set up the user interface."""
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create splitter for configuration and logs
        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter)
        
        # Top section: Configuration
        config_widget = QWidget()
        config_layout = QVBoxLayout(config_widget)
        splitter.addWidget(config_widget)
        
        # Configuration tabs
        self.config_tabs = QTabWidget()
        config_layout.addWidget(self.config_tabs)
        
        # Tab 1: Connection Settings
        self._create_connection_tab()
        
        # Tab 2: Mission Settings
        self._create_mission_tab()
        
        # Tab 3: Advanced Settings
        self._create_advanced_tab()
        
        # Tab 4: Position Test
        self._create_position_test_tab()
        
        # Tab 5: Camera
        self._create_camera_tab()
        
        # Tab 6: DVL Position
        # self._create_dvl_tab()
        
        # Tab 6: DVL Position
        self._create_dvl_2d_tab()
        
        
        # Control buttons
        control_layout = QHBoxLayout()
        config_layout.addLayout(control_layout)
        
        self.run_button = QPushButton("Run Mission")
        self.run_button.setMinimumHeight(40)
        self.run_button.clicked.connect(self._on_run_mission)
        control_layout.addWidget(self.run_button)
        
        self.stop_button = QPushButton("Stop Mission")
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._on_stop_mission)
        control_layout.addWidget(self.stop_button)
        
        # Bottom section: Logs and Telemetry
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        splitter.addWidget(log_widget)
        
        # Log display tab widget
        self.log_tabs = QTabWidget()
        log_layout.addWidget(self.log_tabs)
        
        # Tab 1: Status Log
        self.status_log = QTextEdit()
        self.status_log.setReadOnly(True)
        self.log_tabs.addTab(self.status_log, "Status Log")
        
        # Tab 2: Telemetry
        self.telemetry_display = QTextEdit()
        self.telemetry_display.setReadOnly(True)
        self.log_tabs.addTab(self.telemetry_display, "Telemetry")
        
        # Tab 3: Mission Logs
        self.mission_logs = QTextEdit()
        self.mission_logs.setReadOnly(True)
        self.log_tabs.addTab(self.mission_logs, "Mission Logs")
        
        # Set initial splitter sizes
        splitter.setSizes([400, 400])
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
    def _create_dvl_2d_tab(self):
        """Create a tab for DVL position visualization using 2D plots."""
        
        # Create the DVL visualizer widget
        # Set use_mock_data=False to use real DVL data, True for simulated data
        self.dvl_visualizer = DVL2DVisualizer(parent=self, use_mock_data=False)
        
        # Add the tab directly - the visualizer is already a complete widget
        self.config_tabs.addTab(self.dvl_visualizer, "DVL Position 2D")
    
    # def _create_dvl_tab(self):
    #     """Create a tab for DVL position visualization."""
        
    #     # Create the DVL visualizer widget
    #     # Set use_mock_data=False to use real DVL data, True for simulated data
    #     self.dvl_visualizer = DVLVisualizer(parent=self, use_mock_data=False)
        
    #     # Add the tab directly - the visualizer is already a complete widget
    #     self.config_tabs.addTab(self.dvl_visualizer, "DVL Position 3D")


    # # Then, in your _setup_ui method, add a call to this method:
    # # After your existing tab creation calls (like self._create_connection_tab()), add:
    # # self._create_dvl_tab()


    # If you want to ensure the visualizer is properly cleaned up, add this to your
    # closeEvent method:
    def closeEvent(self, event):
        """Handle window close event."""
        # Clean up any existing resources
        
        # Close DVL visualizer if it exists
        if hasattr(self, 'dvl_visualizer'):
            self.dvl_visualizer.closeEvent(event)
        
        # Accept the close event
        event.accept()
    
    def _create_camera_tab(self):
        """Create a tab for the camera feed."""
        camera_tab = QWidget()
        camera_layout = QVBoxLayout(camera_tab)
        
        # Camera controls group
        control_group = QGroupBox("Camera Controls")
        control_layout = QFormLayout(control_group)
        camera_layout.addWidget(control_group)
        
        # Add camera IP field (defaults to drone IP)
        self.camera_ip_edit = QLineEdit(self.config.DRONE_IP)
        control_layout.addRow(QLabel("Camera IP:"), self.camera_ip_edit)
        
        # Add camera port field
        self.camera_port_edit = QLineEdit("8554")
        control_layout.addRow(QLabel("RTSP Port:"), self.camera_port_edit)
        
        # Add camera path field
        self.camera_path_edit = QLineEdit("test")
        control_layout.addRow(QLabel("RTSP Path:"), self.camera_path_edit)
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        control_layout.addRow(buttons_layout)
        
        # Start camera button
        self.start_camera_button = QPushButton("Start Camera")
        self.start_camera_button.clicked.connect(self._on_start_camera)
        buttons_layout.addWidget(self.start_camera_button)
        
        # Stop camera button
        self.stop_camera_button = QPushButton("Stop Camera")
        self.stop_camera_button.clicked.connect(self._on_stop_camera)
        self.stop_camera_button.setEnabled(False)
        buttons_layout.addWidget(self.stop_camera_button)
        
        # Camera display
        self.camera_display_label = QLabel("Camera feed will appear here")
        self.camera_display_label.setAlignment(Qt.AlignCenter)
        self.camera_display_label.setMinimumHeight(480)
        self.camera_display_label.setStyleSheet("background-color: black; color: white;")
        camera_layout.addWidget(self.camera_display_label)
        
        # Add the tab
        self.config_tabs.addTab(camera_tab, "Camera")
        
        # Initialize video capture variables
        self.video_capture = None
        self.video_timer = QTimer()
        self.video_timer.timeout.connect(self._update_camera_frame)
        
    def _on_start_camera(self):
        """Start the camera stream."""
        # Get camera connection details
        camera_ip = self.camera_ip_edit.text()
        camera_port = self.camera_port_edit.text()
        camera_path = self.camera_path_edit.text()
        
        # Build RTSP URL
        rtsp_url = f"rtsp://{camera_ip}:{camera_port}/{camera_path}"
        
        # Build GStreamer pipeline
        gst_pipeline = (
            f"rtspsrc location={rtsp_url} latency=0 ! "
            "rtph264depay ! avdec_h264 ! videoconvert ! appsink"
        )
        
        # Update status
        self._append_status(f"Connecting to camera at {rtsp_url}...", False)
        
        # Initialize video capture
        try:
            self.video_capture = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
            
            if not self.video_capture.isOpened():
                self._append_status("Failed to open camera stream.", True)
                self.camera_display_label.setText("Failed to connect to camera")
                return
            
            # Update UI
            self._append_status("Camera stream connected successfully.", False)
            self.start_camera_button.setEnabled(False)
            self.stop_camera_button.setEnabled(True)
            
            # Start timer to update frames
            self.video_timer.start(33)  # ~30 fps
            
        except Exception as e:
            self._append_status(f"Error connecting to camera: {str(e)}", True)
            self.camera_display_label.setText(f"Error: {str(e)}")

    def _on_stop_camera(self):
        """Stop the camera stream."""
        # Stop the timer
        self.video_timer.stop()
        
        # Release video capture
        if self.video_capture and self.video_capture.isOpened():
            self.video_capture.release()
            self.video_capture = None
        
        # Update UI
        self._append_status("Camera stream stopped.", False)
        self.camera_display_label.setText("Camera feed stopped")
        self.start_camera_button.setEnabled(True)
        self.stop_camera_button.setEnabled(False)
        
    def closeEvent(self, event):
        """Handle window close event."""
        # Stop camera if running
        if hasattr(self, 'video_timer') and self.video_timer.isActive():
            self.video_timer.stop()
            
        if hasattr(self, 'video_capture') and self.video_capture and self.video_capture.isOpened():
            self.video_capture.release()
        
        # Accept the close event
        event.accept()
        
    def _update_camera_frame(self):
        """Update the camera frame in the GUI."""
        if self.video_capture and self.video_capture.isOpened():
            ret, frame = self.video_capture.read()
            
            if not ret:
                self._append_status("Error reading camera frame.", True)
                self._on_stop_camera()
                return
            
            # Convert the frame to QImage
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
            
            # Scale the image to fit the label while maintaining aspect ratio
            pixmap = QPixmap.fromImage(q_img)
            self.camera_display_label.setPixmap(pixmap.scaled(
                self.camera_display_label.width(), 
                self.camera_display_label.height(),
                Qt.KeepAspectRatio
            ))
        
    def _create_connection_tab(self):
        """Create the connection settings tab."""
        connection_tab = QWidget()
        connection_layout = QVBoxLayout(connection_tab)
        
        # Drone Connection Group
        drone_group = QGroupBox("Drone Connection")
        drone_layout = QFormLayout(drone_group)
        connection_layout.addWidget(drone_group)
        
        # Add test button for drone connection
        self.test_drone_button = QPushButton("Test Drone Connection")
        self.test_drone_button.clicked.connect(self._on_test_drone)
        drone_layout.addRow(self.test_drone_button)
        
        self.drone_ip_edit = QLineEdit()
        drone_layout.addRow(QLabel("Drone IP:"), self.drone_ip_edit)
        
        self.drone_timeout_spin = QSpinBox()
        self.drone_timeout_spin.setRange(5, 300)
        self.drone_timeout_spin.setSuffix(" seconds")
        drone_layout.addRow(QLabel("Connection Timeout:"), self.drone_timeout_spin)
        
        # USBL Connection Group
        usbl_group = QGroupBox("USBL Connection")
        usbl_layout = QFormLayout(usbl_group)
        connection_layout.addWidget(usbl_group)
        
        self.use_usbl_check = QCheckBox("Use USBL for positioning")
        self.use_usbl_check.setChecked(True)
        self.use_usbl_check.stateChanged.connect(self._on_use_usbl_changed)
        usbl_layout.addRow(self.use_usbl_check)
        
        self.usbl_ip_edit = QLineEdit()
        usbl_layout.addRow(QLabel("USBL IP:"), self.usbl_ip_edit)
        
        self.usbl_port_spin = QSpinBox()
        self.usbl_port_spin.setRange(1, 65535)
        usbl_layout.addRow(QLabel("USBL Port:"), self.usbl_port_spin)
        
        self.usbl_samples_spin = QSpinBox()
        self.usbl_samples_spin.setRange(1, 100)
        usbl_layout.addRow(QLabel("USBL Samples:"), self.usbl_samples_spin)
        
        # Add test button for USBL
        self.test_usbl_button = QPushButton("Test USBL Connection")
        self.test_usbl_button.clicked.connect(self._on_test_usbl)
        usbl_layout.addRow(self.test_usbl_button)
        
        # Add the tab
        self.config_tabs.addTab(connection_tab, "Connection")
    
    def _create_mission_tab(self):
        """Create the mission settings tab."""
        mission_tab = QWidget()
        mission_layout = QVBoxLayout(mission_tab)
        
        # Docking Station Group
        docking_group = QGroupBox("Docking Station")
        docking_layout = QFormLayout(docking_group)
        mission_layout.addWidget(docking_group)
        
        self.docking_lat_edit = QLineEdit()
        docking_layout.addRow(QLabel("Latitude:"), self.docking_lat_edit)
        
        self.docking_lon_edit = QLineEdit()
        docking_layout.addRow(QLabel("Longitude:"), self.docking_lon_edit)
        
        self.docking_depth_spin = QDoubleSpinBox()
        self.docking_depth_spin.setRange(0, 150)
        self.docking_depth_spin.setDecimals(1)
        self.docking_depth_spin.setSuffix(" meters")
        docking_layout.addRow(QLabel("Depth:"), self.docking_depth_spin)
        
        # Navigation Strategy Group
        nav_group = QGroupBox("Navigation Strategy")
        nav_layout = QFormLayout(nav_group)
        mission_layout.addWidget(nav_group)
        
        self.nav_strategy_combo = QComboBox()
        self.nav_strategy_combo.addItem("Three-Stage Approach", "three_stage")
        self.nav_strategy_combo.addItem("Direct Approach", "direct")
        nav_layout.addRow(QLabel("Strategy:"), self.nav_strategy_combo)
        
        self.approach_speed_spin = QDoubleSpinBox()
        self.approach_speed_spin.setRange(0.1, 1.0)
        self.approach_speed_spin.setDecimals(2)
        self.approach_speed_spin.setSingleStep(0.05)
        self.approach_speed_spin.setSuffix(" m/s")
        nav_layout.addRow(QLabel("Approach Speed:"), self.approach_speed_spin)
        
        self.descent_speed_spin = QDoubleSpinBox()
        self.descent_speed_spin.setRange(0.1, 1.0)
        self.descent_speed_spin.setDecimals(2)
        self.descent_speed_spin.setSingleStep(0.05)
        self.descent_speed_spin.setSuffix(" m/s")
        nav_layout.addRow(QLabel("Descent Speed:"), self.descent_speed_spin)
        
        # Add the tab
        self.config_tabs.addTab(mission_tab, "Mission")
    def _on_test_drone(self):
        """Test the drone connection."""
        # Update config from UI
        try:
            self._update_config_from_ui()
        except ValueError:
            return
        
        self._append_status("<b>Testing drone connection...</b>", False)
        
        # Disable test button to prevent multiple clicks
        self.test_drone_button.setEnabled(False)
        
        def test_drone_worker():
            try:
                # Create drone manager for testing
                drone_manager = DroneManager(
                    ip=self.config.DRONE_IP,
                    timeout=self.config.DRONE_CONNECT_TIMEOUT
                )
                
                # Connect to drone
                self._append_status("Connecting to drone...", False)
                if not drone_manager.connect():
                    self._append_status("Failed to connect to drone.", True)
                    return
                
                self._append_status("Connected to drone successfully.", False)
                
                # Get drone info
                try:
                    self._append_status(f"Drone Serial Number: {drone_manager.drone.serial_number}", False)
                    self._append_status(f"Software Version: {drone_manager.drone.software_version}", False)
                    
                    # Get battery level if available
                    try:
                        battery = drone_manager.drone.battery.level
                        self._append_status(f"Battery Level: {battery:.1f}%", False)
                    except:
                        self._append_status("Battery level not available", False)
                    
                    # Get depth if available
                    try:
                        depth = drone_manager.drone.depth
                        self._append_status(f"Current Depth: {depth:.1f}m", False)
                    except:
                        self._append_status("Depth information not available", False)
                    
                    self._append_status("Drone connection test completed successfully.", False)
                    
                except Exception as e:
                    self._append_status(f"Error getting drone information: {str(e)}", True)
                    
                finally:
                    # Always disconnect
                    self._append_status("Disconnecting from drone...", False)
                    drone_manager.disconnect()
                    self._append_status("Disconnected from drone.", False)
                    
            except Exception as e:
                self._append_status(f"Error during drone connection test: {str(e)}", True)
                
            finally:
                # Re-enable the test button from the main thread
                self.test_drone_button.setEnabled(True)
        
        # Start the worker thread
        threading.Thread(target=test_drone_worker, daemon=True).start()
    
    def _create_advanced_tab(self):
        """Create the advanced settings tab."""
        advanced_tab = QWidget()
        advanced_layout = QVBoxLayout(advanced_tab)
        
        # General Settings Group
        general_group = QGroupBox("General Settings")
        general_layout = QFormLayout(general_group)
        advanced_layout.addWidget(general_group)
        
        self.max_duration_spin = QSpinBox()
        self.max_duration_spin.setRange(60, 7200)
        self.max_duration_spin.setSingleStep(60)
        self.max_duration_spin.setSuffix(" seconds")
        general_layout.addRow(QLabel("Maximum Mission Duration:"), self.max_duration_spin)
        
        self.acceptance_radius_spin = QDoubleSpinBox()
        self.acceptance_radius_spin.setRange(0.5, 10.0)
        self.acceptance_radius_spin.setDecimals(1)
        self.acceptance_radius_spin.setSingleStep(0.5)
        self.acceptance_radius_spin.setSuffix(" meters")
        general_layout.addRow(QLabel("Acceptance Radius:"), self.acceptance_radius_spin)
        
        self.approach_depth_offset_spin = QDoubleSpinBox()
        self.approach_depth_offset_spin.setRange(1.0, 20.0)
        self.approach_depth_offset_spin.setDecimals(1)
        self.approach_depth_offset_spin.setSingleStep(1.0)
        self.approach_depth_offset_spin.setSuffix(" meters")
        general_layout.addRow(QLabel("Approach Depth Offset:"), self.approach_depth_offset_spin)
        
        # Configuration Management Group
        config_group = QGroupBox("Configuration Management")
        config_layout = QHBoxLayout(config_group)
        advanced_layout.addWidget(config_group)
        
        self.save_config_button = QPushButton("Save Configuration")
        self.save_config_button.clicked.connect(self._on_save_config)
        config_layout.addWidget(self.save_config_button)
        
        self.load_config_button = QPushButton("Load Configuration")
        self.load_config_button.clicked.connect(self._on_load_config)
        config_layout.addWidget(self.load_config_button)
        
        self.reset_config_button = QPushButton("Reset to Defaults")
        self.reset_config_button.clicked.connect(self._on_reset_config)
        config_layout.addWidget(self.reset_config_button)
        
        # Add the tab
        self.config_tabs.addTab(advanced_tab, "Advanced")
    
    def _on_use_live_usbl(self):
        """Get live USBL data and populate the test fields."""
        try:
            self._update_config_from_ui()
        except ValueError:
            return
        
        self.result_display.clear()
        self.result_display.append("<b>Fetching live USBL data...</b>")
        
        # Disable button to prevent multiple clicks
        self.use_live_usbl_button.setEnabled(False)
        
        def fetch_usbl_worker():
            try:
                # Create USBL reader
                usbl_reader = USBLReader(
                    host=self.config.USBL_IP,
                    port=self.config.USBL_PORT,
                    timeout=5
                )
                
                # Connect to USBL
                self._update_result("Connecting to USBL...")
                if not usbl_reader.connect():
                    self._update_result("Failed to connect to USBL system.", error=True)
                    return
                
                self._update_result("Connected to USBL system.")
                
                try:
                    # Read USBL data
                    self._update_result(f"Reading USBL data...")
                    usbl_data = usbl_reader.read_data(num_samples=2, timeout=10)
                    
                    if not usbl_data:
                        self._update_result("Failed to read USBL data.", error=True)
                        return
                    
                    # Update the test fields with the USBL data
                    self._update_test_fields(usbl_data.x, usbl_data.y, usbl_data.heading)
                    
                    self._update_result(f"USBL data received: x={usbl_data.x:.2f}m, y={usbl_data.y:.2f}m, heading={usbl_data.heading:.2f}°")
                    
                finally:
                    # Always disconnect
                    usbl_reader.disconnect()
            except Exception as e:
                self._update_result(f"Error fetching USBL data: {str(e)}", error=True)
            finally:
                # Re-enable the button
                self.use_live_usbl_button.setEnabled(True)
        
        # Start the worker thread
        threading.Thread(target=fetch_usbl_worker, daemon=True).start()

    def _update_test_fields(self, x, y, heading):
        """Update the test fields with the given values."""
        self.test_x_edit.setText(f"{x:.2f}")
        self.test_y_edit.setText(f"{y:.2f}")
        self.test_heading_edit.setText(f"{heading:.2f}")

    def _on_use_config_values(self):
        """Use the values from the configuration for the reference position."""
        try:
            self._update_config_from_ui()
            self.test_ref_lat_edit.setText(str(self.config.DOCKING_LAT))
            self.test_ref_lon_edit.setText(str(self.config.DOCKING_LON))
        except ValueError:
            return

    def _on_calculate_position(self):
        """Calculate the absolute position based on the test inputs."""
        self.result_display.clear()
        
        try:
            # Get the values from the fields
            x = float(self.test_x_edit.text())
            y = float(self.test_y_edit.text())
            heading = float(self.test_heading_edit.text())
            ref_lat = float(self.test_ref_lat_edit.text())
            ref_lon = float(self.test_ref_lon_edit.text())
            
            # Calculate the position
            try:
                lat, lon = CoordinateConverter.relative_to_absolute(ref_lat, ref_lon, x, y)
                
                # Display the result
                self.result_display.append("<b>Blueye Position:</b><br>")
                self.result_display.append(f"<b>Input:</b><br>")
                self.result_display.append(f"X: {x:.2f} meters<br>")
                self.result_display.append(f"Y: {y:.2f} meters<br>")
                self.result_display.append(f"Heading: {heading:.2f} degrees<br>")
                self.result_display.append(f"Reference Latitude: {ref_lat:.6f}<br>")
                self.result_display.append(f"Reference Longitude: {ref_lon:.6f}<br><br>")
                
                self.result_display.append(f"<b>Output:</b><br>")
                self.result_display.append(f"Calculated Latitude: <b>{lat:.8f}</b><br>")
                self.result_display.append(f"Calculated Longitude: <b>{lon:.8f}</b><br>")
                
                # Calculate distance from reference
                distance = CoordinateConverter.calculate_distance(ref_lat, ref_lon, lat, lon)
                self.result_display.append(f"<br>Drone Distance from reference: <b>{distance:.2f} meters</b><br>")
                
                # Display angle
                angle = math.degrees(math.atan2(x, y))
                if angle < 0:
                    angle += 360
                self.result_display.append(f"Angle from reference: <b>{angle:.2f} degrees</b>")
                
            except Exception as e:
                self.result_display.append(f"<span style='color:red'>Error in calculation: {str(e)}</span>")
        
        except ValueError as e:
            self.result_display.append(f"<span style='color:red'>Invalid input: {str(e)}</span>")
            self.result_display.append("<span style='color:red'>Please ensure all fields contain valid numbers.</span>")

    def _update_result(self, message, error=False):
        """Update the result display with a message."""
        if error:
            self.result_display.append(f"<span style='color:red'>{message}</span>")
        else:
            self.result_display.append(message)
        
        # Auto-scroll to bottom
        cursor = self.result_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.result_display.setTextCursor(cursor)
    
    def _load_config_to_ui(self):
        """Load configuration values into the UI elements."""
        # Connection Settings
        self.drone_ip_edit.setText(self.config.DRONE_IP)
        self.drone_timeout_spin.setValue(self.config.DRONE_CONNECT_TIMEOUT)
        
        self.usbl_ip_edit.setText(self.config.USBL_IP)
        self.usbl_port_spin.setValue(self.config.USBL_PORT)
        self.usbl_samples_spin.setValue(self.config.USBL_SAMPLES)
        
        # Mission Settings
        self.docking_lat_edit.setText(str(self.config.DOCKING_LAT))
        self.docking_lon_edit.setText(str(self.config.DOCKING_LON))
        self.docking_depth_spin.setValue(self.config.DOCKING_DEPTH)
        
        self.approach_speed_spin.setValue(self.config.APPROACH_SPEED)
        self.descent_speed_spin.setValue(self.config.DESCENT_SPEED)
        
        # Advanced Settings
        self.max_duration_spin.setValue(self.config.MAX_MISSION_DURATION)
        self.acceptance_radius_spin.setValue(self.config.ACCEPTANCE_RADIUS)
        self.approach_depth_offset_spin.setValue(self.config.APPROACH_DEPTH_OFFSET)
    
    def _update_config_from_ui(self):
        """Update configuration object from UI values."""
        # Create a new config with overrides
        try:
            config_overrides = {
                'DRONE_IP': self.drone_ip_edit.text(),
                'DRONE_CONNECT_TIMEOUT': self.drone_timeout_spin.value(),
                
                'USBL_IP': self.usbl_ip_edit.text(),
                'USBL_PORT': self.usbl_port_spin.value(),
                'USBL_SAMPLES': self.usbl_samples_spin.value(),
                
                'DOCKING_LAT': float(self.docking_lat_edit.text()),
                'DOCKING_LON': float(self.docking_lon_edit.text()),
                'DOCKING_DEPTH': self.docking_depth_spin.value(),
                
                'APPROACH_SPEED': self.approach_speed_spin.value(),
                'DESCENT_SPEED': self.descent_speed_spin.value(),
                
                'MAX_MISSION_DURATION': self.max_duration_spin.value(),
                'ACCEPTANCE_RADIUS': self.acceptance_radius_spin.value(),
                'APPROACH_DEPTH_OFFSET': self.approach_depth_offset_spin.value(),
            }
            
            self.config = Config(**config_overrides)
            return self.config
        except ValueError as e:
            QMessageBox.critical(self, "Invalid Input", f"Please check your inputs: {str(e)}")
            raise
    
    def _on_use_usbl_changed(self, state):
        """Handle USBL checkbox state changes."""
        enabled = (state == Qt.Checked)
        self.usbl_ip_edit.setEnabled(enabled)
        self.usbl_port_spin.setEnabled(enabled)
        self.usbl_samples_spin.setEnabled(enabled)
        self.test_usbl_button.setEnabled(enabled)
    
    def _on_test_usbl(self):
        """Test USBL connection and readings."""
        # Update config from UI
        try:
            self._update_config_from_ui()
        except ValueError:
            return
        
        self._append_status("<b>Testing USBL connection...</b>", False)
        
        # Disable test button to prevent multiple clicks
        self.test_usbl_button.setEnabled(False)
        
        def test_usbl_worker():
            try:
                # Create USBL reader
                usbl_reader = USBLReader(
                    host=self.config.USBL_IP,
                    port=self.config.USBL_PORT,
                    timeout=5  # Use a shorter timeout for testing
                )
                
                # Connect to USBL
                self._append_status("Connecting to USBL...", False)
                if not usbl_reader.connect():
                    self._append_status("Failed to connect to USBL system.", True)
                    return
                
                self._append_status("Connected to USBL system.", False)
                
                try:
                    # Read USBL data
                    self._append_status(f"Reading USBL data...", False)
                    usbl_data = usbl_reader.read_data(num_samples=2, timeout=10)
                    
                    if not usbl_data:
                        self._append_status("Failed to read USBL data.", True)
                        return
                    
                    # Display USBL data
                    self._append_status(f"USBL data received:", False)
                    self._append_status(f"  X: {usbl_data.x:.2f} meters", False)
                    self._append_status(f"  Y: {usbl_data.y:.2f} meters", False)
                    self._append_status(f"  Heading: {usbl_data.heading:.2f} degrees", False)
                    
                    try:
                        # Convert to absolute coordinates
                        lat, lon = CoordinateConverter.relative_to_absolute(
                            self.config.DOCKING_LAT,
                            self.config.DOCKING_LON,
                            usbl_data.x,
                            usbl_data.y
                        )
                        
                        self._append_status(f"Converted coordinates:", False)
                        self._append_status(f"  Latitude: {lat:.6f}", False)
                        self._append_status(f"  Longitude: {lon:.6f}", False)
                    except Exception as e:
                        self._append_status(f"Error converting coordinates: {str(e)}", True)
                    
                    self._append_status("USBL test completed successfully.", False)
                    
                finally:
                    # Always disconnect
                    usbl_reader.disconnect()
                    self._append_status("Disconnected from USBL system.", False)
            
            except Exception as e:
                self._append_status(f"Error during USBL test: {str(e)}", True)
            
            finally:
                # Re-enable the test button from the main thread
                self.test_usbl_button.setEnabled(True)
        
        # Start the worker thread
        threading.Thread(target=test_usbl_worker, daemon=True).start()
    
    def _on_save_config(self):
        """Save current configuration to a file."""
        # Update config from UI
        try:
            self._update_config_from_ui()
        except ValueError:
            return
        
        # Get save path
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Configuration", str(Path.home()), "JSON Files (*.json)"
        )
        
        if not path:
            return
        
        try:
            # Create a dict of config values
            config_dict = {
                key: getattr(self.config, key)
                for key in dir(self.config)
                if not key.startswith('_') and key.isupper()
            }
            
            # Save to file
            with open(path, 'w') as f:
                json.dump(config_dict, f, indent=2)
            
            self.statusBar().showMessage(f"Configuration saved to {path}", 5000)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {str(e)}")
    
    def _on_load_config(self):
        """Load configuration from a file."""
        # Get load path
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Configuration", str(Path.home()), "JSON Files (*.json)"
        )
        
        if not path:
            return
        
        try:
            # Load from file
            with open(path, 'r') as f:
                config_dict = json.load(f)
            
            # Create new config with the loaded values
            self.config = Config(**config_dict)
            
            # Update UI
            self._load_config_to_ui()
            
            self.statusBar().showMessage(f"Configuration loaded from {path}", 5000)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load configuration: {str(e)}")
    
    def _on_reset_config(self):
        """Reset configuration to defaults."""
        # Ask for confirmation
        reply = QMessageBox.question(
            self, "Reset Configuration",
            "Are you sure you want to reset all settings to defaults?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Create new default config
            self.config = Config()
            
            # Update UI
            self._load_config_to_ui()
            
            self.statusBar().showMessage("Configuration reset to defaults", 5000)
    
    def _on_run_mission(self):
        """Start the docking mission."""
        # Update config from UI
        try:
            self._update_config_from_ui()
        except ValueError:
            return
        
        # Clear logs
        self.status_log.clear()
        self.telemetry_display.clear()
        self._append_status("<b>Starting mission...</b>", False)
        
        # Create navigation strategy
        if self.nav_strategy_combo.currentData() == "direct":
            navigation_strategy = DirectNavigation()
            self._append_status("Using Direct Navigation strategy", False)
        else:
            navigation_strategy = ThreeStageNavigation()
            self._append_status("Using Three-Stage Navigation strategy", False)
        
        # Create and start the mission worker
        self.mission_worker = MissionWorker(
            config=self.config,
            navigation_strategy=navigation_strategy,
            use_usbl=self.use_usbl_check.isChecked()
        )
        
        # Connect signals
        self.mission_worker.status_signal.connect(self._append_status)
        self.mission_worker.mission_started.connect(self._on_mission_started)
        self.mission_worker.mission_completed.connect(self._on_mission_completed)
        self.mission_worker.telemetry_signal.connect(self._on_telemetry_updated)
        
        # Start the worker
        self.mission_worker.start()
        
        # Update UI
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.config_tabs.setEnabled(False)
        
        self.statusBar().showMessage("Mission running...")
    
    def _on_stop_mission(self):
        """Stop the current mission."""
        if self.mission_worker and self.mission_worker.isRunning():
            reply = QMessageBox.question(
                self, "Stop Mission",
                "Are you sure you want to stop the current mission?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self._append_status("<b>Stopping mission...</b>", False)
                self.mission_worker.stop()
                
                # Update UI
                self.stop_button.setEnabled(False)
                self.statusBar().showMessage("Stopping mission...")
    
    def _on_mission_started(self):
        """Handler for mission started signal."""
        self.statusBar().showMessage("Mission in progress...")
    
    def _on_mission_completed(self, success, message):
        """Handler for mission completed signal."""
        if success:
            self._append_status(f"<b>Mission completed successfully</b>", False)
            self.statusBar().showMessage("Mission completed successfully")
        else:
            self._append_status(f"<b>Mission failed: {message}</b>", True)
            self.statusBar().showMessage("Mission failed")
        
        # Update UI
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.config_tabs.setEnabled(True)
        
        # Load mission logs
        self._load_mission_logs()
    
    def _on_telemetry_updated(self, telemetry_json):
        """Handler for telemetry updates."""
        try:
            # Parse JSON data
            data = json.loads(telemetry_json)
            
            # Format timestamp
            time_str = datetime.now().strftime("%H:%M:%S")
            
            # Format mission status
            status = data.get("mission_status", {})
            state = status.get("state", "Unknown")
            time_elapsed = status.get("time_elapsed", 0)
            time_remaining = status.get("estimated_time_remaining", 0)
            distance = status.get("distance_to_complete", 0)
            progress = f"{status.get('completed_instructions', 0)}/{status.get('total_instructions', 0)}"
            
            # Format telemetry data
            telemetry = data.get("telemetry", {})
            depth = telemetry.get("depth", "N/A")
            if depth is not None:
                depth = f"{depth:.1f}m"
            else:
                depth = "N/A"
            
            temperature = telemetry.get("water_temperature", "N/A")
            if temperature is not None:
                temperature = f"{temperature:.1f}°C"
            
            battery = telemetry.get("battery", "N/A")
            if battery is not None:
                battery = f"{battery:.1f}%"
            
            # Format display text
            telemetry_text = (
                f"<b>[{time_str}]</b><br>"
                f"<b>Mission State:</b> {state}<br>"
                f"<b>Progress:</b> {progress} instructions<br>"
                f"<b>Time:</b> {time_elapsed}s elapsed, ~{time_remaining}s remaining<br>"
                f"<b>Distance to Complete:</b> {distance}m<br>"
                f"<b>Depth:</b> {depth}<br>"
                f"<b>Water Temperature:</b> {temperature}<br>"
                f"<b>Battery:</b> {battery}<br>"
                f"<hr>"
            )
            
            # Add to telemetry display
            self.telemetry_display.append(telemetry_text)
            
            # Auto-scroll to bottom
            cursor = self.telemetry_display.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.telemetry_display.setTextCursor(cursor)
            
        except Exception as e:
            self._append_status(f"Error parsing telemetry data: {str(e)}", True)
    
    def _create_position_test_tab(self):
        """Create a tab for testing position calculation."""
        test_tab = QWidget()
        test_layout = QVBoxLayout(test_tab)
        
        # USBL Data Group
        usbl_group = QGroupBox("USBL Data")
        usbl_layout = QFormLayout(usbl_group)
        test_layout.addWidget(usbl_group)
        
        # Add fields for X, Y coordinates and heading
        self.test_x_edit = QLineEdit("0.0")
        usbl_layout.addRow(QLabel("X (meters):"), self.test_x_edit)
        
        self.test_y_edit = QLineEdit("0.0")
        usbl_layout.addRow(QLabel("Y (meters):"), self.test_y_edit)
        
        self.test_heading_edit = QLineEdit("0.0")
        usbl_layout.addRow(QLabel("Heading (degrees):"), self.test_heading_edit)
        
        # Add "Use Live USBL Data" button
        self.use_live_usbl_button = QPushButton("Use Live USBL Data")
        self.use_live_usbl_button.clicked.connect(self._on_use_live_usbl)
        usbl_layout.addRow(self.use_live_usbl_button)
        
        # Docking Station Reference Group
        reference_group = QGroupBox("Docking Station Reference")
        reference_layout = QFormLayout(reference_group)
        test_layout.addWidget(reference_group)
        
        # Add fields for reference latitude and longitude
        self.test_ref_lat_edit = QLineEdit(str(self.config.DOCKING_LAT))
        reference_layout.addRow(QLabel("Reference Latitude:"), self.test_ref_lat_edit)
        
        self.test_ref_lon_edit = QLineEdit(str(self.config.DOCKING_LON))
        reference_layout.addRow(QLabel("Reference Longitude:"), self.test_ref_lon_edit)
        
        # Add "Use Configuration Values" button
        self.use_config_button = QPushButton("Use Configuration Values")
        self.use_config_button.clicked.connect(self._on_use_config_values)
        reference_layout.addRow(self.use_config_button)
        
        # Calculation Group
        calc_group = QGroupBox("Position Calculation")
        calc_layout = QVBoxLayout(calc_group)
        test_layout.addWidget(calc_group)
        
        # Add Calculate button
        self.calculate_button = QPushButton("Calculate Position")
        self.calculate_button.setMinimumHeight(40)
        self.calculate_button.clicked.connect(self._on_calculate_position)
        calc_layout.addWidget(self.calculate_button)
        
        # Add result display
        self.result_display = QTextEdit()
        self.result_display.setReadOnly(True)
        self.result_display.setMinimumHeight(150)
        calc_layout.addWidget(self.result_display)
        
        # Add the tab
        self.config_tabs.addTab(test_tab, "Position Test")
    
    def _append_status(self, message, is_error=False):
        """Append a message to the status log."""
        time_str = datetime.now().strftime("%H:%M:%S")
        
        # Format message with timestamp
        if is_error:
            html = f"<span style='color:red'><b>[{time_str}]</b> {message}</span>"
        else:
            html = f"<b>[{time_str}]</b> {message}"
        
        # Append to log
        self.status_log.append(html)
        
        # Ensure the latest log entry is visible
        cursor = self.status_log.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.status_log.setTextCursor(cursor)
    
    def _load_mission_logs(self):
        """Load and display available mission logs."""
        self.mission_logs.clear()
        
        # Find all log files
        log_files = sorted(self.mission_log_path.glob("mission_*.json"), reverse=True)
        
        if not log_files:
            self.mission_logs.append("<i>No mission logs found.</i>")
            return
        
        # Display list of logs
        self.mission_logs.append("<h3>Available Mission Logs:</h3>")
        
        for i, log_file in enumerate(log_files[:10]):  # Show only the 10 most recent logs
            try:
                # Read log file
                with open(log_file, 'r') as f:
                    log_data = json.load(f)
                
                # Get start and end events
                start_event = next((e for e in log_data if e.get("event") == "mission_start"), {})
                end_event = next((e for e in log_data if e.get("event") == "mission_end"), {})
                
                # Format log entry
                timestamp = datetime.fromisoformat(start_event.get("timestamp", "")).strftime("%Y-%m-%d %H:%M:%S")
                mission_name = start_event.get("mission_name", "Unknown")
                success = end_event.get("success", False)
                reason = end_event.get("reason", "Unknown")
                
                status = "Successful" if success else "Failed"
                color = "green" if success else "red"
                
                log_entry = (
                    f"<p><b>Log {i+1}:</b> {log_file.name}<br>"
                    f"<b>Time:</b> {timestamp}<br>"
                    f"<b>Mission:</b> {mission_name}<br>"
                    f"<b>Status:</b> <span style='color:{color}'>{status}</span><br>"
                    f"<b>Reason:</b> {reason}</p>"
                    f"<hr>"
                )
                
                self.mission_logs.append(log_entry)
                
            except Exception as e:
                self.mission_logs.append(f"<p><b>Error reading log {log_file.name}:</b> {str(e)}</p><hr>")
        
        # Add note if there are more logs
        if len(log_files) > 10:
            self.mission_logs.append(f"<i>There are {len(log_files)-10} more logs not shown.</i>")


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)
    window = DockingSystemGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
