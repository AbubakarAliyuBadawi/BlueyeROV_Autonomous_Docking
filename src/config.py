#!/usr/bin/env python3
"""
Configuration parameters for the Blueye docking system.
"""

class Config:
    """Configuration parameters for the docking system."""
    
    # Drone connection settings
    DRONE_IP = "192.168.1.101"
    DRONE_CONNECT_TIMEOUT = 30
    
    # USBL settings
    USBL_IP = "192.168.1.189"
    USBL_PORT = 9200
    USBL_TIMEOUT = 10
    USBL_SAMPLES = 5
    
    # Docking station parameters
    DOCKING_LAT = 66.442387
    DOCKING_LON = 10.369335
    DOCKING_DEPTH = 80.0
    
    # Mission parameters
    MAX_MISSION_DURATION = 1800  # 30 minutes
    
    # Navigation parameters
    APPROACH_SPEED = 0.3        # Horizontal speed in m/s
    DESCENT_SPEED = 0.2         # Vertical speed in m/s
    ACCEPTANCE_RADIUS = 2.0     # Circle of acceptance radius in meters
    APPROACH_DEPTH_OFFSET = 10.0  # Meters above docking station for first approach
    
    # Logging
    LOG_LEVEL = "INFO"
    LOG_FILE = "docking_mission.log"
    
    def __init__(self, **kwargs):
        """
        Initialize configuration with optional overrides.
        
        Args:
            **kwargs: Overrides for any configuration parameters
        """
        # Allow overriding any config parameter through kwargs
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
