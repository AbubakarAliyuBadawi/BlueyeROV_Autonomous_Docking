#!/usr/bin/env python3
"""
Main application module for the Blueye docking system.

This module serves as the entry point for the application, connecting all
components together to execute the docking mission.
"""

import argparse
import sys
import time

# Import modules
from config import Config
from utils import setup_logging, CoordinateConverter, USBLReader, USBLData
from navigation import ThreeStageNavigation, DirectNavigation
from drone import DroneManager
from mission import MissionManager


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run a docking mission for a Blueye drone')
    
    # Drone settings
    parser.add_argument('--drone-ip', type=str,
                        help='IP address of the Blueye drone')
    parser.add_argument('--drone-timeout', type=int,
                        help='Connection timeout for the drone in seconds')
    
    # USBL settings
    parser.add_argument('--usbl-ip', type=str,
                        help='IP address of the USBL system')
    parser.add_argument('--usbl-port', type=int,
                        help='Port number of the USBL system')
    parser.add_argument('--usbl-samples', type=int,
                        help='Number of USBL samples to average')
    
    # Docking station settings
    parser.add_argument('--docking-lat', type=float,
                        help='Docking station latitude in decimal degrees')
    parser.add_argument('--docking-lon', type=float,
                        help='Docking station longitude in decimal degrees')
    parser.add_argument('--docking-depth', type=float,
                        help='Docking station depth in meters')
    
    # Mission settings
    parser.add_argument('--timeout', type=int,
                        help='Maximum mission duration in seconds')
    parser.add_argument('--approach-speed', type=float,
                        help='Horizontal movement speed in m/s')
    parser.add_argument('--descent-speed', type=float,
                        help='Vertical movement speed in m/s')
    parser.add_argument('--direct-approach', action='store_true',
                        help='Use direct approach instead of three-stage approach')
    parser.add_argument('--no-usbl', action='store_true',
                        help='Skip USBL reading and use docking station coordinates directly')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Create config object with overrides from arguments
    config_overrides = {}
    
    # Only add non-None values to overrides
    if args.drone_ip:
        config_overrides['DRONE_IP'] = args.drone_ip
    if args.drone_timeout:
        config_overrides['DRONE_CONNECT_TIMEOUT'] = args.drone_timeout
    if args.usbl_ip:
        config_overrides['USBL_IP'] = args.usbl_ip
    if args.usbl_port:
        config_overrides['USBL_PORT'] = args.usbl_port
    if args.usbl_samples:
        config_overrides['USBL_SAMPLES'] = args.usbl_samples
    if args.docking_lat:
        config_overrides['DOCKING_LAT'] = args.docking_lat
    if args.docking_lon:
        config_overrides['DOCKING_LON'] = args.docking_lon
    if args.docking_depth:
        config_overrides['DOCKING_DEPTH'] = args.docking_depth
    if args.timeout:
        config_overrides['MAX_MISSION_DURATION'] = args.timeout
    if args.approach_speed:
        config_overrides['APPROACH_SPEED'] = args.approach_speed
    if args.descent_speed:
        config_overrides['DESCENT_SPEED'] = args.descent_speed
    
    return args, config_overrides


def get_usbl_data(config, logger):
    """
    Get USBL data from the USBL system.
    
    Args:
        config (Config): Configuration parameters
        logger: Logger instance
        
    Returns:
        USBLData: USBL data, or None if failed
    """
    # Connect to USBL and get position
    usbl_reader = USBLReader(
        host=config.USBL_IP,
        port=config.USBL_PORT,
        timeout=config.USBL_TIMEOUT,
        logger=logger
    )
    
    if not usbl_reader.connect():
        logger.error("Failed to connect to USBL. Exiting.")
        return None
    
    try:
        # Read USBL data
        usbl_data = usbl_reader.read_data(num_samples=config.USBL_SAMPLES)
        if not usbl_data:
            logger.error("Failed to read USBL data. Exiting.")
            return None
        
        return usbl_data
    finally:
        # Always disconnect from USBL
        usbl_reader.disconnect()


def main():
    """Main function."""
    # Parse arguments
    args, config_overrides = parse_arguments()
    
    # Initialize configuration
    config = Config(**config_overrides)
    
    # Setup logging
    logger = setup_logging(config.LOG_FILE, config.LOG_LEVEL)
    logger.info("Starting Blueye docking mission")
    
    # Component references for cleanup
    drone_manager = None
    
    try:
        # Get drone position from USBL if requested
        drone_position = None
        
        if not args.no_usbl:
            logger.info("Getting drone position from USBL")
            usbl_data = get_usbl_data(config, logger)
            
            if not usbl_data:
                logger.error("Could not get USBL data. Exiting.")
                return 1
            
            # Convert relative coordinates to absolute position
            drone_lat, drone_lon = CoordinateConverter.relative_to_absolute(
                config.DOCKING_LAT, config.DOCKING_LON, usbl_data.x, usbl_data.y
            )
            
            drone_position = {
                'lat': drone_lat,
                'lon': drone_lon
            }
            
            logger.info(f"Drone position: {drone_position}")
        else:
            # If USBL is not used, assume the drone is at a known position
            logger.info("Skipping USBL reading, using current drone position")
            # We'll get the drone's current position after connecting
        
        # Set up docking station position
        docking_position = {
            'lat': config.DOCKING_LAT,
            'lon': config.DOCKING_LON,
            'depth': config.DOCKING_DEPTH
        }
        
        # Connect to the drone
        drone_manager = DroneManager(
            ip=config.DRONE_IP,
            timeout=config.DRONE_CONNECT_TIMEOUT,
            logger=logger
        )
        
        if not drone_manager.connect():
            logger.error("Failed to connect to drone. Exiting.")
            return 1
        
        # If we're not using USBL, we need to get the drone's current position
        if not drone_position:
            # Get the drone's current GPS position if available
            # Note: This might not be accurate underwater
            # In a real implementation, you might use a surface GPS fix before descending
            drone_position = {
                'lat': config.DOCKING_LAT,  # Placeholder: in real scenario, get from GPS
                'lon': config.DOCKING_LON,  # Placeholder: in real scenario, get from GPS
            }
            logger.info(f"Using assumed drone position: {drone_position}")
        
        # Create navigation strategy
        if args.direct_approach:
            logger.info("Using direct navigation approach")
            navigation_strategy = DirectNavigation()
        else:
            logger.info("Using three-stage navigation approach")
            navigation_strategy = ThreeStageNavigation()
        
        # Create mission manager
        mission_manager = MissionManager(
            navigation_strategy=navigation_strategy,
            config=config,
            logger=logger
        )
        
        # Execute the mission
        success = mission_manager.execute_mission(
            drone_manager=drone_manager,
            drone_position=drone_position,
            target_position=docking_position,
            max_duration=config.MAX_MISSION_DURATION
        )
        
        logger.info(f"Mission {'completed successfully' if success else 'failed'}")
        return 0 if success else 1
        
    except KeyboardInterrupt:
        logger.info("Mission aborted by user")
        return 130  # Standard exit code for SIGINT
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return 1
        
    finally:
        # Always try to disconnect from the drone
        if drone_manager:
            drone_manager.disconnect()


if __name__ == "__main__":
    sys.exit(main())
