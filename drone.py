#!/usr/bin/env python3
"""
Drone connection and mission execution for the Blueye docking system.
"""

import time
import logging
from blueye.sdk import Drone
import blueye.protocol as bp


class DroneManager:
    """Class for handling drone connection and mission execution."""
    
    def __init__(self, ip="192.168.1.101", timeout=30, logger=None):
        """
        Initialize the drone manager.
        
        Args:
            ip (str): IP address of the drone
            timeout (int): Connection timeout in seconds
            logger (logging.Logger): Logger instance
        """
        self.ip = ip
        self.timeout = timeout
        self.drone = None
        self.connected = False
        self.logger = logger or logging.getLogger(__name__)
    
    def connect(self, take_control=True):
        """
        Connect to the drone and optionally take control.
        
        Args:
            take_control (bool): Whether to take control of the drone
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        self.logger.info(f"Connecting to drone at {self.ip}")
        try:
            self.drone = Drone(
                ip=self.ip,
                auto_connect=True,
                timeout=self.timeout,
            )
            
            self.logger.info(f"Connected to drone: {self.drone.serial_number}")
            self.logger.info(f"Drone software version: {self.drone.software_version}")
            
            if take_control and not self.drone.in_control:
                self.logger.info("Taking control of drone...")
                self.drone.take_control()
                self.logger.info("Control of drone acquired")
            
            self.connected = True
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to drone: {str(e)}")
            return False
    
    def disconnect(self):
        """
        Disconnect from the drone safely.
        
        Returns:
            bool: True if disconnection successful, False otherwise
        """
        if not self.drone or not self.drone.connected:
            return True
        
        self.logger.info("Disconnecting from drone")
        try:
            # Stop mission if still running
            try:
                status = self.drone.mission.get_status()
                if status and status.state and status.state.name == "MISSION_STATE_RUNNING":
                    self.logger.info("Stopping active mission")
                    self.drone.mission.stop()
                    time.sleep(1)
            except Exception as e:
                self.logger.warning(f"Error checking mission status: {str(e)}")
            
            # Disconnect
            self.drone.disconnect()
            self.logger.info("Disconnected from drone")
            self.connected = False
            return True
            
        except Exception as e:
            self.logger.error(f"Error during disconnect: {str(e)}")
            return False
    
    def get_telemetry(self):
        """
        Get current telemetry data from the drone.
        
        Returns:
            dict: Telemetry data including position, depth, etc.
        """
        if not self.drone or not self.drone.connected:
            self.logger.error("Cannot get telemetry: drone not connected")
            return None
        
        try:
            telemetry = {
                "depth": self.drone.depth,
                "pose": self.drone.pose,
                "water_temperature": self.drone.water_temperature,
                "dive_time": self.drone.dive_time,
            }
            
            # Try to get battery level if available
            try:
                telemetry["battery"] = self.drone.battery.level
            except:
                telemetry["battery"] = None
            
            return telemetry
            
        except Exception as e:
            self.logger.error(f"Error getting telemetry: {str(e)}")
            return None
    
    def run_mission(self, mission, max_duration=1800, telemetry_callback=None):
        """
        Run a mission and monitor its progress.
        
        Args:
            mission (bp.Mission): The mission to run
            max_duration (int): Maximum mission duration in seconds
            telemetry_callback (callable): Optional callback for telemetry updates
            
        Returns:
            bool: True if mission completed successfully, False otherwise
        """
        if not self.connected or not self.drone:
            self.logger.error("Drone not connected. Cannot run mission.")
            return False
        
        start_time = time.time()
        
        try:
            # Clear any existing missions
            self.logger.info("Clearing any previous missions")
            self.drone.mission.clear()
            time.sleep(1)
            
            # Send the new mission
            self.logger.info(f"Sending new mission: {mission.name}")
            self.drone.mission.send_new(mission)
            time.sleep(1)
            
            # Check if the mission was loaded successfully
            status = self.drone.mission.get_status()
            if status.state != bp.MissionState.MISSION_STATE_READY:
                self.logger.error(f"Failed to load mission. State: {status.state.name}")
                return False
            
            # Start the mission
            self.logger.info("Starting mission execution")
            self.drone.mission.run()
            
            # Monitor mission progress
            while True:
                # Check if maximum duration exceeded
                elapsed = time.time() - start_time
                if elapsed > max_duration:
                    self.logger.warning(f"Mission timeout after {elapsed:.1f} seconds")
                    self.drone.mission.stop()
                    return False
                
                # Get current mission status
                status = self.drone.mission.get_status()
                
                # Get telemetry data
                telemetry = self.get_telemetry()
                
                # Call telemetry callback if provided
                if telemetry_callback and telemetry:
                    telemetry_callback(status, telemetry)
                
                # Log current status
                state_msg = f"Mission: {status.state.name}, "
                state_msg += f"Progress: {len(status.completed_instruction_ids)}/{status.total_number_of_instructions} instructions, "
                state_msg += f"Time: {status.time_elapsed}s/{status.time_elapsed + status.estimated_time_to_complete}s"
                if telemetry and telemetry.get('depth') is not None:
                    state_msg += f", Depth: {telemetry['depth']:.1f}m"
                self.logger.info(state_msg)
                
                # Check mission state
                if status.state == bp.MissionState.MISSION_STATE_COMPLETED:
                    self.logger.info("Mission completed successfully")
                    return True
                elif status.state == bp.MissionState.MISSION_STATE_ABORTED:
                    self.logger.warning("Mission was aborted")
                    return False
                elif status.state in [
                    bp.MissionState.MISSION_STATE_FAILED_TO_LOAD_MISSION,
                    bp.MissionState.MISSION_STATE_FAILED_TO_START_MISSION
                ]:
                    self.logger.error(f"Mission failed with state: {status.state.name}")
                    return False
                
                time.sleep(2)  # Poll every 2 seconds to reduce load
                
        except Exception as e:
            self.logger.error(f"Error during mission execution: {str(e)}")
            # Try to stop the mission if there's an error
            try:
                self.drone.mission.stop()
            except:
                pass
            return False
