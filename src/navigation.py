#!/usr/bin/env python3
"""
Navigation strategies for the Blueye docking system.
"""

from abc import ABC, abstractmethod
import blueye.protocol as bp
from blueye.protocol.types.mission_planning import DepthZeroReference
from blueye.protocol.types.message_formats import LatLongPosition


class NavigationStrategy(ABC):
    """Abstract base class for navigation strategies."""
    
    @abstractmethod
    def create_mission(self, drone_position, target_position, config):
        """
        Create a mission based on the navigation strategy.
        
        Args:
            drone_position (dict): Current drone position with 'lat', 'lon' keys
            target_position (dict): Target position with 'lat', 'lon', 'depth' keys
            config: Configuration parameters
            
        Returns:
            bp.Mission: The created mission
        """
        pass


class ThreeStageNavigation(NavigationStrategy):
    """
    Three-stage navigation strategy:
    1. Navigate to a point directly above the target
    2. Descend to the target depth
    3. Move horizontally to the exact target position
    """
    
    def create_mission(self, drone_position, target_position, config):
        """
        Create a three-stage mission.
        
        Args:
            drone_position (dict): Current drone position with 'lat', 'lon' keys
            target_position (dict): Target position with 'lat', 'lon', 'depth' keys
            config: Configuration parameters
            
        Returns:
            bp.Mission: The created mission
        """
        # Extract position data
        drone_lat = drone_position['lat']
        drone_lon = drone_position['lon']
        target_lat = target_position['lat']
        target_lon = target_position['lon']
        target_depth = target_position['depth']
        
        # Calculate approach depth (above the target)
        approach_depth = max(5.0, target_depth - config.APPROACH_DEPTH_OFFSET)
        
        # Create the instructions for the mission
        instructions = []
        instruction_id = 1
        
        # STAGE 1: Configure auto-depth mode
        control_mode = bp.Instruction(
            id=instruction_id,
            control_mode_command=bp.ControlModeCommand(
                control_mode_vertical=bp.ControlModeVertical.CONTROL_MODE_VERTICAL_AUTO_DEPTH,
                control_mode_horizontal=bp.ControlModeHorizontal.CONTROL_MODE_HORIZONTAL_MANUAL
            ),
            auto_continue=True
        )
        instructions.append(control_mode)
        instruction_id += 1
        
        # Set initial depth to approach depth or 5m if shallower
        initial_depth_set_point = bp.DepthSetPoint(
            depth=min(approach_depth, 5.0),
            speed_to_depth=config.DESCENT_SPEED,
            depth_zero_reference=DepthZeroReference.DEPTH_ZERO_REFERENCE_SURFACE
        )
        
        goto_initial_depth = bp.Instruction(
            id=instruction_id,
            depth_set_point_command=bp.DepthSetPointCommand(
                depth_set_point=initial_depth_set_point
            ),
            auto_continue=True
        )
        instructions.append(goto_initial_depth)
        instruction_id += 1
        
        # Navigate to position above target
        above_target_wp = bp.Waypoint(
            id=instruction_id,
            name="Above Target",
            global_position=LatLongPosition(
                latitude=target_lat,
                longitude=target_lon
            ),
            circle_of_acceptance=config.ACCEPTANCE_RADIUS,
            speed_to_target=config.APPROACH_SPEED,
            depth_set_point=initial_depth_set_point
        )
        
        goto_above_target = bp.Instruction(
            id=instruction_id,
            waypoint_command=bp.WaypointCommand(
                waypoint=above_target_wp
            ),
            auto_continue=True
        )
        instructions.append(goto_above_target)
        instruction_id += 1
        
        # STAGE 2: Descend to the target depth
        final_depth_set_point = bp.DepthSetPoint(
            depth=target_depth,
            speed_to_depth=config.DESCENT_SPEED,
            depth_zero_reference=DepthZeroReference.DEPTH_ZERO_REFERENCE_SURFACE
        )
        
        goto_final_depth = bp.Instruction(
            id=instruction_id,
            depth_set_point_command=bp.DepthSetPointCommand(
                depth_set_point=final_depth_set_point
            ),
            auto_continue=True
        )
        instructions.append(goto_final_depth)
        instruction_id += 1
        
        # STAGE 3: Move to the exact target coordinates
        target_wp = bp.Waypoint(
            id=instruction_id,
            name="Target",
            global_position=LatLongPosition(
                latitude=target_lat,
                longitude=target_lon
            ),
            circle_of_acceptance=config.ACCEPTANCE_RADIUS,
            speed_to_target=config.APPROACH_SPEED,
            depth_set_point=final_depth_set_point
        )
        
        goto_target = bp.Instruction(
            id=instruction_id,
            waypoint_command=bp.WaypointCommand(
                waypoint=target_wp
            ),
            auto_continue=True
        )
        instructions.append(goto_target)
        instruction_id += 1
        
        # Create the mission
        mission = bp.Mission(
            id=1,
            name="Three-Stage Approach",
            instructions=instructions,
            default_surge_speed=config.APPROACH_SPEED,
            default_heave_speed=config.DESCENT_SPEED,
            default_circle_of_acceptance=config.ACCEPTANCE_RADIUS
        )
        
        return mission


class DirectNavigation(NavigationStrategy):
    """
    Direct navigation strategy - go straight to the target.
    This is a simpler alternative to the three-stage approach.
    """
    
    def create_mission(self, drone_position, target_position, config):
        """
        Create a direct navigation mission.
        
        Args:
            drone_position (dict): Current drone position with 'lat', 'lon' keys
            target_position (dict): Target position with 'lat', 'lon', 'depth' keys
            config: Configuration parameters
            
        Returns:
            bp.Mission: The created mission
        """
        # Extract position data
        drone_lat = drone_position['lat']
        drone_lon = drone_position['lon']
        target_lat = target_position['lat']
        target_lon = target_position['lon']
        target_depth = target_position['depth']
        
        # Create the instructions for the mission
        instructions = []
        instruction_id = 1
        
        # Set depth set point for target depth
        depth_set_point = bp.DepthSetPoint(
            depth=target_depth,
            speed_to_depth=config.DESCENT_SPEED,
            depth_zero_reference=DepthZeroReference.DEPTH_ZERO_REFERENCE_SURFACE
        )
        
        # Configure auto-depth mode
        control_mode = bp.Instruction(
            id=instruction_id,
            control_mode_command=bp.ControlModeCommand(
                control_mode_vertical=bp.ControlModeVertical.CONTROL_MODE_VERTICAL_AUTO_DEPTH,
                control_mode_horizontal=bp.ControlModeHorizontal.CONTROL_MODE_HORIZONTAL_MANUAL
            ),
            auto_continue=True
        )
        instructions.append(control_mode)
        instruction_id += 1
        
        # Add depth set point instruction
        goto_depth = bp.Instruction(
            id=instruction_id,
            depth_set_point_command=bp.DepthSetPointCommand(
                depth_set_point=depth_set_point
            ),
            auto_continue=True
        )
        instructions.append(goto_depth)
        instruction_id += 1
        
        # Create waypoint to target
        target_wp = bp.Waypoint(
            id=instruction_id,
            name="Target",
            global_position=LatLongPosition(
                latitude=target_lat,
                longitude=target_lon
            ),
            circle_of_acceptance=config.ACCEPTANCE_RADIUS,
            speed_to_target=config.APPROACH_SPEED,
            depth_set_point=depth_set_point
        )
        
        goto_target = bp.Instruction(
            id=instruction_id,
            waypoint_command=bp.WaypointCommand(
                waypoint=target_wp
            ),
            auto_continue=True
        )
        instructions.append(goto_target)
        
        # Create the mission
        mission = bp.Mission(
            id=1,
            name="Direct Approach",
            instructions=instructions,
            default_surge_speed=config.APPROACH_SPEED,
            default_heave_speed=config.DESCENT_SPEED,
            default_circle_of_acceptance=config.ACCEPTANCE_RADIUS
        )
        
        return mission
