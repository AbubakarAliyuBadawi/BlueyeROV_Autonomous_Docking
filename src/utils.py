#!/usr/bin/env python3
"""
Utility functions for the Blueye docking system.
"""

import logging
import math
import socket
import struct
import sys
import time
from datetime import datetime
from pathlib import Path


def setup_logging(log_file="docking_mission.log", log_level="INFO"):
    """
    Set up logging configuration.
    
    Args:
        log_file (str): Path to the log file
        log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        logging.Logger: Configured logger
    """
    # Create log directory if needed
    log_path = Path(log_file)
    log_path.parent.mkdir(exist_ok=True, parents=True)
    
    # Set up logging level
    level = getattr(logging, log_level.upper())
    
    # Configure logging
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger("docking_system")


class CoordinateConverter:
    """Utility for converting between coordinate systems."""
    
    @staticmethod
    def relative_to_absolute(docking_lat, docking_lon, x, y):
        """
        Convert relative USBL coordinates to absolute latitude/longitude.
        
        Args:
            docking_lat (float): Docking station latitude in decimal degrees
            docking_lon (float): Docking station longitude in decimal degrees
            x (float): X-coordinate in meters (east-west displacement)
            y (float): Y-coordinate in meters (north-south displacement)
            
        Returns:
            tuple: (latitude, longitude) in decimal degrees
        """
        # Constants for Earth's radius and degree conversion
        EARTH_RADIUS = 6371000  # Earth radius in meters
        
        # Convert displacement to distance and bearing
        distance = math.sqrt(x**2 + y**2)
        
        # Calculate bearing from docking station to drone
        # Note: In this application, x is positive eastward, y is positive northward
        bearing_rad = math.atan2(x, y)  # Use atan2 for correct quadrant
        bearing_deg = math.degrees(bearing_rad)
        if bearing_deg < 0:
            bearing_deg += 360  # Convert to 0-360 range
        
        # Convert docking station coordinates to radians
        lat1_rad = math.radians(docking_lat)
        lon1_rad = math.radians(docking_lon)
        
        # Calculate new position using haversine formula (inverse)
        angular_distance = distance / EARTH_RADIUS
        
        # Calculate new latitude
        lat2_rad = math.asin(
            math.sin(lat1_rad) * math.cos(angular_distance) + 
            math.cos(lat1_rad) * math.sin(angular_distance) * math.cos(math.radians(bearing_deg))
        )
        
        # Calculate new longitude
        lon2_rad = lon1_rad + math.atan2(
            math.sin(math.radians(bearing_deg)) * math.sin(angular_distance) * math.cos(lat1_rad),
            math.cos(angular_distance) - math.sin(lat1_rad) * math.sin(lat2_rad)
        )
        
        # Convert back to decimal degrees
        lat2_deg = math.degrees(lat2_rad)
        lon2_deg = math.degrees(lon2_rad)
        
        logging.getLogger(__name__).info(f"Converted relative position ({x:.2f}m, {y:.2f}m) to lat/lon: {lat2_deg:.6f}, {lon2_deg:.6f}")
        return lat2_deg, lon2_deg
    
    @staticmethod
    def calculate_distance(lat1, lon1, lat2, lon2):
        """
        Calculate distance between two coordinates using haversine formula.
        
        Args:
            lat1 (float): First latitude in decimal degrees
            lon1 (float): First longitude in decimal degrees
            lat2 (float): Second latitude in decimal degrees
            lon2 (float): Second longitude in decimal degrees
            
        Returns:
            float: Distance in meters
        """
        # Earth's radius in meters
        R = 6371000
        
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Differences
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        # Haversine formula
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        
        return distance


class USBLData:
    """Data structure for USBL readings."""
    
    def __init__(self, x, y, heading, timestamp=None):
        """
        Initialize USBL data.
        
        Args:
            x (float): X-coordinate in meters (east-west displacement)
            y (float): Y-coordinate in meters (north-south displacement)
            heading (float): Heading in degrees
            timestamp (float): Unix timestamp
        """
        self.x = x
        self.y = y
        self.heading = heading
        self.timestamp = timestamp or time.time()
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "x": self.x,
            "y": self.y,
            "heading": self.heading,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create from dictionary."""
        return cls(
            x=data["x"],
            y=data["y"],
            heading=data["heading"],
            timestamp=data.get("timestamp")
        )


class USBLReader:
    """Class to read and parse USBL data."""
    
    def __init__(self, host, port, timeout=10, logger=None):
        """
        Initialize the USBL reader.
        
        Args:
            host (str): USBL system IP address
            port (int): USBL system port number
            timeout (int): Socket timeout in seconds
            logger (logging.Logger): Logger instance
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.socket = None
        self.logger = logger or logging.getLogger(__name__)
    
    def connect(self):
        """
        Connect to the USBL system.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.host, self.port))
            self.logger.info(f"Connected to USBL system at {self.host}:{self.port}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to USBL: {str(e)}")
            return False
    
    def read_data(self, num_samples=5, timeout=30):
        """
        Read and average multiple USBL data samples.
        
        Args:
            num_samples (int): Number of samples to read and average
            timeout (int): Maximum time to wait for samples in seconds
            
        Returns:
            USBLData: Averaged USBL data, or None if failed
        """
        if not self.socket:
            self.logger.error("Not connected to USBL system")
            return None
        
        try:
            start_time = time.time()
            samples = []
            sample_count = 0
            
            self.logger.info(f"Reading {num_samples} USBL samples...")
            
            while sample_count < num_samples and (time.time() - start_time) < timeout:
                data = self.socket.recv(1024)
                if not data:
                    time.sleep(0.1)
                    continue
                
                # Find the start of USBL data packet
                hex_byte_start = data.find(b'E')
                if hex_byte_start == -1:
                    continue
                    
                hex_byte_start_real = data[hex_byte_start+1:].find(b'E') + hex_byte_start + 2
                if hex_byte_start_real != -1 and len(data) > hex_byte_start_real + 5:
                    try:
                        x, y, heading = struct.unpack('<hhB', data[hex_byte_start_real:hex_byte_start_real+5])
                        # Convert from decimeters to meters
                        x_meters = x / 10.0
                        y_meters = y / 10.0
                        samples.append((x_meters, y_meters, heading))
                        sample_count += 1
                        self.logger.info(f"USBL sample {sample_count}: x={x_meters:.2f}m, y={y_meters:.2f}m, heading={heading}°")
                    except struct.error:
                        self.logger.warning("Failed to unpack USBL data")
                
                time.sleep(0.1)
            
            if not samples:
                self.logger.error("No valid USBL samples obtained")
                return None
            
            # Calculate averages
            avg_x = sum(s[0] for s in samples) / len(samples)
            avg_y = sum(s[1] for s in samples) / len(samples)
            avg_heading = sum(s[2] for s in samples) / len(samples)
            
            self.logger.info(f"Average USBL data: x={avg_x:.2f}m, y={avg_y:.2f}m, heading={avg_heading:.2f}°")
            return USBLData(avg_x, avg_y, avg_heading)
            
        except Exception as e:
            self.logger.error(f"Error reading USBL data: {str(e)}")
            return None
    
    def disconnect(self):
        """Disconnect from the USBL system."""
        if self.socket:
            self.socket.close()
            self.socket = None
            self.logger.info("Disconnected from USBL system")
