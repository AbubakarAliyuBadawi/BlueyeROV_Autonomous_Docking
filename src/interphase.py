import customtkinter as ctk
import tkinter as tk
from typing import Optional
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

class ROVPlotCanvas:
    def __init__(self, master):
        self.figure = Figure(figsize=(8, 6), dpi=100, facecolor='#2b2b2b')
        self.axes = self.figure.add_subplot(111, projection='3d', computed_zorder=False)
        self.axes.set_facecolor('#2b2b2b')  # Set background color to match dark theme
        
        self.canvas = FigureCanvasTkAgg(self.figure, master=master)
        self.canvas.draw()
        
        # Set fixed view limits
        self.x_limits = [-100, 100]
        self.y_limits = [-100, 100]
        self.z_limits = [85, 100]
        
        self.axes.set_xlabel('X [m]')
        self.axes.set_ylabel('Y [m]')
        self.axes.set_zlabel('Depth [m]')
        self.axes.set_title('ROV Position and Waypoints')
        
        # Initialize plot elements
        self.path_line, = self.axes.plot3D([], [], [], 'b-', label='Blueye Path', linewidth=2, zorder=1)
        self.current_pos, = self.axes.plot3D([], [], [], 'yo', label='Blueye Position', markersize=10, zorder=3)
        
        # Plot waypoints
        waypoints = np.array([
            [-8.5, 8.54, 95.3],    # Docking station
            [-18.0, -25.0, 90.0],  # Pipeline point 1
            [20.0, 55.0, 90.0]     # Pipeline point 2
        ])
        
        # Docking station
        self.axes.scatter([waypoints[0, 0]], [waypoints[0, 1]], [waypoints[0, 2]],
                         c='r', marker='s', s=100, label='Docking Station', zorder=2)
        
        # Pipeline points
        self.axes.scatter(waypoints[1:, 0], waypoints[1:, 1], waypoints[1:, 2],
                         c='g', marker='s', s=100, label='Pipeline', zorder=2)
        
        self.axes.set_xlim(self.x_limits)
        self.axes.set_ylim(self.y_limits)
        self.axes.set_zlim(self.z_limits[1], self.z_limits[0])
        
        self.axes.view_init(elev=25, azim=45)
        self.axes.grid(True, zorder=0)
        self.axes.legend()
        
        self.canvas_widget = self.canvas.get_tk_widget()

class BlueyeInterface(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configure window
        self.title("Blueye Interface")
        self.geometry("1200x800")
        
        # Configure grid layout for the main window
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Set appearance mode to dark
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Create main frames
        self.left_frame = ctk.CTkFrame(self)
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        # Create sections
        self.create_sensors_section()
        # self.create_map_section()
        self.create_position_section()
        self.create_velocity_section()
        self.create_selectors_section()
        self.create_controllers_section()
        self.create_modes_section()        
        self.create_map_section()

    def create_map_section(self):
        # Create a dedicated frame for the map at the bottom of left_frame
        map_frame = ctk.CTkFrame(self.right_frame)
        map_frame.pack(fill="both", expand=True, padx=5, pady=5, side="bottom")
        
        # Create the plot canvas
        self.plot_canvas = ROVPlotCanvas(map_frame)
        self.plot_canvas.canvas_widget.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Configure frame to expand properly
        map_frame.pack_propagate(False)  # Prevent frame from shrinking
        map_frame.configure(height=500)  # Set a fixed height for the map

    def create_sensors_section(self):
        sensors_frame = ctk.CTkFrame(self.left_frame)
        sensors_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(sensors_frame, text="SENSORS").pack(anchor="w", padx=5, pady=5)
        
        sensors = {
            "IMU:": "Active",
            "DVL:": "Active",
            "BAR:": "Active",
            "STATUS:": "Inactive"
        }
        
        for sensor, status in sensors.items():
            frame = ctk.CTkFrame(sensors_frame)
            frame.pack(fill="x", padx=5, pady=2)
            ctk.CTkLabel(frame, text=sensor).pack(side="left", padx=5)
            color = "green" if status == "Active" else "red" if status == "Inactive" else "white"
            ctk.CTkLabel(frame, text=status, text_color=color).pack(side="left")

    def create_position_section(self):
        position_frame = ctk.CTkFrame(self.left_frame)
        position_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(position_frame, text="POSITION").pack(anchor="w", padx=5, pady=5)
        
        positions = {
            "X:": "61.48",
            "Y:": "7.66",
            "Z:": "0.0341",
            "Yaw:": "319.38"
        }
        
        for pos, value in positions.items():
            frame = ctk.CTkFrame(position_frame)
            frame.pack(fill="x", padx=5, pady=2)
            ctk.CTkLabel(frame, text=pos).pack(side="left", padx=5)
            ctk.CTkLabel(frame, text=value).pack(side="left")

    def create_velocity_section(self):
        velocity_frame = ctk.CTkFrame(self.left_frame)
        velocity_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(velocity_frame, text="VELOCITY").pack(anchor="w", padx=5, pady=5)
        
        velocities = {
            "U:": "-0.0517",
            "R:": "0.0038"
        }
        
        for vel, value in velocities.items():
            frame = ctk.CTkFrame(velocity_frame)
            frame.pack(fill="x", padx=5, pady=2)
            ctk.CTkLabel(frame, text=vel).pack(side="left", padx=5)
            ctk.CTkLabel(frame, text=value).pack(side="left")

    def create_selectors_section(self):
        selectors_frame = ctk.CTkFrame(self.left_frame)
        selectors_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(selectors_frame, text="SELECTORS").pack(anchor="w", padx=5, pady=5)
        
        # Observer dropdown
        observer_frame = ctk.CTkFrame(selectors_frame)
        observer_frame.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(observer_frame, text="Observer:").pack(side="left", padx=5)
        ctk.CTkOptionMenu(observer_frame, values=["Coupled"], width=120).pack(side="left", padx=5)
        
        # Control Mode dropdown
        control_frame = ctk.CTkFrame(selectors_frame)
        control_frame.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(control_frame, text="Control Mode:").pack(side="left", padx=5)
        ctk.CTkOptionMenu(control_frame, values=["Velocity"], width=120).pack(side="left", padx=5)

    def create_controllers_section(self):
        controllers_frame = ctk.CTkFrame(self.left_frame)
        controllers_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(controllers_frame, text="CONTROLLERS").pack(anchor="w", padx=5, pady=5)
        
        controllers = [
            "Surge", "Sway", "Yaw"
        ]
        
        for controller in controllers:
            frame = ctk.CTkFrame(controllers_frame)
            frame.pack(fill="x", padx=5, pady=2)
            ctk.CTkLabel(frame, text=controller).pack(side="left", padx=5)
            slider = ctk.CTkSlider(frame)
            slider.pack(side="left", padx=5, fill="x", expand=True)
            value = "180.0" if controller == "Yaw" else "0.0"
            ctk.CTkLabel(frame, text=value).pack(side="right", padx=5)
        
        # Add START and STOP buttons
        button_frame = ctk.CTkFrame(controllers_frame)
        button_frame.pack(fill="x", padx=5, pady=10)
        
        ctk.CTkButton(button_frame, text="START", fg_color="green").pack(side="left", padx=5, expand=True)
        ctk.CTkButton(button_frame, text="STOP", fg_color="red").pack(side="right", padx=5, expand=True)

    def create_modes_section(self):
        modes_frame = ctk.CTkFrame(self.right_frame)
        modes_frame.pack(fill="x", padx=5, pady=5)
        
        modes = ["STATION KEEP", "ROTATE", "ASCEND", "DESCEND"]
        
        for mode in modes:
            button = ctk.CTkButton(modes_frame, text=mode, fg_color="blue")
            button.pack(fill="x", padx=5, pady=5)
            
            if mode in ["ASCEND", "DESCEND"]:
                frame = ctk.CTkFrame(modes_frame)
                frame.pack(fill="x", padx=5, pady=2)
                slider = ctk.CTkSlider(frame)
                slider.pack(side="left", padx=5, fill="x", expand=True)
                ctk.CTkLabel(frame, text="0.2").pack(side="right", padx=5)

if __name__ == "__main__":
    app = BlueyeInterface()
    app.mainloop()