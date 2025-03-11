#!/usr/bin/env python3
"""
Mission planning and logging for the Blueye docking system.
"""

import json
import logging
from datetime import datetime
from pathlib import Path


class MissionManager:
    """Class for building, executing, and logging missions."""
    
    def __init__(self, navigation_strategy, config, logger=None):
        """
        Initialize the mission manager.
        
        Args:
            navigation_strategy: The navigation strategy to use
            config: Configuration parameters
            logger: Logger instance
        """
        self.navigation_strategy = navigation_strategy
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        # Set up mission logging
        self.log_dir = Path("mission_logs")
        self.log_dir.mkdir(exist_ok=True, parents=True)
        self.mission_data = []
        self.mission_start_time = None
    
    def build_mission(self, drone_position, target_position):
        """
        Build a mission using the navigation strategy.
        
        Args:
            drone_position (dict): Current drone position with 'lat', 'lon' keys
            target_position (dict): Target position with 'lat', 'lon', 'depth' keys
            
        Returns:
            Mission: The created mission
        """
        self.logger.info(f"Building mission from {drone_position} to {target_position}")
        return self.navigation_strategy.create_mission(
            drone_position=drone_position,
            target_position=target_position,
            config=self.config
        )
    
    def start_mission_logging(self, mission_name, drone_info=None, target_info=None):
        """
        Start logging a new mission.
        
        Args:
            mission_name (str): Name of the mission
            drone_info (dict): Information about the drone
            target_info (dict): Information about the target
        """
        self.mission_start_time = datetime.now()
        self.mission_data = []
        
        # Record mission start
        self.mission_data.append({
            "timestamp": self.mission_start_time.isoformat(),
            "event": "mission_start",
            "mission_name": mission_name,
            "drone_info": drone_info,
            "target_info": target_info
        })
        
        self.logger.info(f"Started logging mission: {mission_name}")
    
    def log_telemetry(self, mission_status, telemetry):
        """
        Callback function for logging telemetry during mission.
        
        Args:
            mission_status: Current mission status
            telemetry (dict): Telemetry data
        """
        if not self.mission_start_time:
            self.logger.warning("Cannot log telemetry: no active mission")
            return
        
        # Create telemetry record
        record = {
            "timestamp": datetime.now().isoformat(),
            "event": "telemetry",
            "mission_status": {
                "state": mission_status.state.name,
                "time_elapsed": mission_status.time_elapsed,
                "estimated_time_to_complete": mission_status.estimated_time_to_complete,
                "distance_to_complete": mission_status.distance_to_complete,
                "completed_instructions": len(mission_status.completed_instruction_ids),
                "total_instructions": mission_status.total_number_of_instructions
            },
            "telemetry": telemetry
        }
        
        self.mission_data.append(record)
    
    def end_mission_logging(self, success, reason=None):
        """
        End the mission logging and save to file.
        
        Args:
            success (bool): Whether the mission was successful
            reason (str): Reason for mission end
            
        Returns:
            str: Path to the saved log file
        """
        if not self.mission_start_time:
            self.logger.warning("Cannot end mission logging: no active mission")
            return None
        
        # Record mission end
        self.mission_data.append({
            "timestamp": datetime.now().isoformat(),
            "event": "mission_end",
            "success": success,
            "reason": reason
        })
        
        # Generate filename with timestamp
        timestamp = self.mission_start_time.strftime("%Y%m%d_%H%M%S")
        status = "success" if success else "failed"
        filename = f"mission_{timestamp}_{status}.json"
        file_path = self.log_dir / filename
        
        # Save log file
        with open(file_path, 'w') as f:
            json.dump(self.mission_data, f, indent=2)
        
        self.logger.info(f"Mission log saved to {file_path}")
        return str(file_path)
    
    def execute_mission(self, drone_manager, drone_position, target_position, max_duration=None):
        """
        Execute a complete mission.
        
        Args:
            drone_manager: The drone manager instance
            drone_position (dict): Current drone position
            target_position (dict): Target position
            max_duration (int): Maximum mission duration in seconds
            
        Returns:
            bool: True if mission completed successfully, False otherwise
        """
        if not max_duration:
            max_duration = self.config.MAX_MISSION_DURATION
        
        # Build the mission
        mission = self.build_mission(
            drone_position=drone_position,
            target_position=target_position
        )
        
        # Start mission logging
        self.start_mission_logging(
            mission_name=mission.name,
            drone_info={"position": drone_position},
            target_info=target_position
        )
        
        # Execute the mission with telemetry callback
        success = drone_manager.run_mission(
            mission=mission,
            max_duration=max_duration,
            telemetry_callback=self.log_telemetry
        )
        
        # End mission logging
        reason = "Completed successfully" if success else "Failed or aborted"
        self.end_mission_logging(
            success=success,
            reason=reason
        )
        
        return success
