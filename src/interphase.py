import customtkinter as ctk
import tkinter as tk
from typing import Optional
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import math

class ThrusterDisplay(tk.Canvas):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(bg='#2b2b2b')
        self.draw_circular_display()

    def draw_circular_display(self):
        # Draw outer circle
        self.create_oval(10, 10, 290, 290, outline='white')
        
        # Draw degree markers
        center_x, center_y = 150, 150
        radius = 140
        for degree in [0, 90, 180, 270]:
            angle = math.radians(degree)
            x1 = center_x + (radius - 10) * math.cos(angle)
            y1 = center_y - (radius - 10) * math.sin(angle)
            x2 = center_x + radius * math.cos(angle)
            y2 = center_y - radius * math.sin(angle)
            self.create_line(x1, y1, x2, y2, fill='white')
            # Add degree text
            text_x = center_x + (radius + 20) * math.cos(angle)
            text_y = center_y - (radius + 20) * math.sin(angle)
            self.create_text(text_x, text_y, text=str(degree), fill='white')

        # Draw ROV image (simplified rectangle for now)
        self.create_rectangle(120, 120, 180, 180, fill='gray')
        
        # Draw thruster indicators
        self.create_rectangle(90, 140, 110, 160, outline='white')  # Left
        self.create_rectangle(190, 140, 210, 160, outline='white')  # Right
        self.create_rectangle(140, 90, 160, 110, outline='white')   # Top
        self.create_rectangle(140, 190, 160, 210, outline='white')  # Bottom

class BlueyeInterface(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configure window
        self.title("Blueye Control System")
        self.geometry("1200x800")
        
        # Create main container
        self.main_container = ctk.CTkFrame(self)
        self.main_container.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Create tab view
        self.tab_view = ctk.CTkTabview(self.main_container)
        self.tab_view.pack(fill="x", padx=5, pady=5)
        
        # Add tabs
        self.tab_view.add("Control System")
        self.tab_view.add("Parameter Tuning")
        self.tab_view.add("System Log")
        self.tab_view.add("Altitude Tuning")
        
        # Create left panel
        self.left_panel = ctk.CTkFrame(self.tab_view.tab("Control System"))
        self.left_panel.pack(side="left", fill="y", padx=5, pady=5)
        
        # Create center panel
        self.center_panel = ctk.CTkFrame(self.tab_view.tab("Control System"))
        self.center_panel.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        # Create right panel
        self.right_panel = ctk.CTkFrame(self.tab_view.tab("Control System"))
        self.right_panel.pack(side="right", fill="y", padx=5, pady=5)
        
        self.create_left_panel()
        self.create_center_panel()
        self.create_right_panel()

    def create_left_panel(self):
        buttons = [
            "START CONTROL SYSTEM",
            "START LOGGING",
            "CONFIGURE",
            "UDP SNIFFER",
            "SYNCHRONIZE",
            "HELP",
            "EXIT"
        ]
        
        for button_text in buttons:
            btn = ctk.CTkButton(self.left_panel, text=button_text)
            btn.pack(fill="x", padx=5, pady=2)
            
        # Add Thruster Forces display
        self.thruster_label = ctk.CTkLabel(self.left_panel, text="Thruster Forces")
        self.thruster_label.pack(pady=5)
        
        self.thruster_display = ThrusterDisplay(self.left_panel, width=300, height=300)
        self.thruster_display.pack(pady=5)

    def create_center_panel(self):
        # Title
        title_label = ctk.CTkLabel(self.center_panel, text="Blueye Control System", font=("Arial", 20))
        title_label.pack(pady=10)
        
        # Control Modes section
        modes_frame = ctk.CTkFrame(self.center_panel)
        modes_frame.pack(fill="x", pady=10)
        
        modes_label = ctk.CTkLabel(modes_frame, text="Control Modes")
        modes_label.pack()
        
        # Status indicators
        indicators_frame = ctk.CTkFrame(modes_frame)
        indicators_frame.pack(fill="x", pady=10)
        
        # Create two columns of indicators
        left_indicators = ctk.CTkFrame(indicators_frame)
        left_indicators.pack(side="left", expand=True)
        
        right_indicators = ctk.CTkFrame(indicators_frame)
        right_indicators.pack(side="right", expand=True)
        
        # Left column indicators
        self.create_indicator(left_indicators, "Waypoint Control")
        self.create_indicator(left_indicators, "Altitude Hold")
        
        # Right column indicators
        self.create_indicator(right_indicators, "Dynamic Positioning")
        self.create_indicator(right_indicators, "Depth Hold")
        
        # Create the 3D plot
        self.create_3d_plot()

    def create_right_panel(self):
        # Emergency Stop Button
        emergency_stop = ctk.CTkButton(self.right_panel, text="EMERGENCY\nSTOP", 
                                     fg_color="darkred", hover_color="red",
                                     height=100)
        emergency_stop.pack(fill="x", padx=5, pady=10)
        
        # Sensor Status
        sensor_frame = ctk.CTkFrame(self.right_panel)
        sensor_frame.pack(fill="x", padx=5, pady=10)
        
        sensor_label = ctk.CTkLabel(sensor_frame, text="Sensor Status")
        sensor_label.pack()
        
        sensors = ["DVL", "IMU", "DEPTH", "USBL"]
        for sensor in sensors:
            self.create_indicator(sensor_frame, sensor)
        
        # Waypoint Control
        waypoint_frame = ctk.CTkFrame(self.right_panel)
        waypoint_frame.pack(fill="x", padx=5, pady=10)
        
        # X, Y coordinates entry
        coord_frame = ctk.CTkFrame(waypoint_frame)
        coord_frame.pack(fill="x", pady=5)
        
        ctk.CTkEntry(coord_frame, placeholder_text="X").pack(side="left", padx=2)
        ctk.CTkEntry(coord_frame, placeholder_text="Y").pack(side="left", padx=2)
        ctk.CTkButton(coord_frame, text="Go", width=50).pack(side="left", padx=2)
        
        # Additional controls
        altitude_frame = ctk.CTkFrame(waypoint_frame)
        altitude_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(altitude_frame, text="Altitude (m):").pack(side="left")
        ctk.CTkEntry(altitude_frame, width=70).pack(side="left", padx=5)
        
        velocity_frame = ctk.CTkFrame(waypoint_frame)
        velocity_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(velocity_frame, text="Velocity (m/s):").pack(side="left")
        ctk.CTkEntry(velocity_frame, width=70).pack(side="left", padx=5)
        
        # Waypoint buttons
        button_frame = ctk.CTkFrame(waypoint_frame)
        button_frame.pack(fill="x", pady=5)
        
        ctk.CTkButton(button_frame, text="Send waypoints").pack(side="left", padx=2, expand=True)
        ctk.CTkButton(button_frame, text="Clear waypoints").pack(side="left", padx=2, expand=True)

    def create_indicator(self, parent, label):
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", padx=5, pady=2)
        
        label = ctk.CTkLabel(frame, text=label)
        label.pack(side="left", padx=5)
        
        # Create a red circle indicator
        canvas = tk.Canvas(frame, width=20, height=20, bg='#2b2b2b', highlightthickness=0)
        canvas.pack(side="right", padx=5)
        canvas.create_oval(2, 2, 18, 18, fill='red')

    def create_3d_plot(self):
        plot_frame = ctk.CTkFrame(self.center_panel)
        plot_frame.pack(fill="both", expand=True, pady=10)
        
        self.figure = Figure(figsize=(8, 6), dpi=100, facecolor='#2b2b2b')
        self.axes = self.figure.add_subplot(111, projection='3d', computed_zorder=False)
        self.axes.set_facecolor('#2b2b2b')
        
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        self.canvas.draw()
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill="both", expand=True)
        
        # Set up the plot
        self.axes.set_xlabel('X')
        self.axes.set_ylabel('Y')
        self.axes.set_zlabel('Z')
        self.axes.set_title('ROV Position')
        
        # Example data points
        x = [0, 10, 20]
        y = [0, 15, 5]
        z = [0, 5, 10]
        
        self.axes.plot3D(x, y, z, 'blue')
        self.axes.scatter3D(x, y, z, c='red')
        
        self.axes.grid(True)
        self.axes.view_init(elev=20, azim=45)

if __name__ == "__main__":
    app = BlueyeInterface()
    app.mainloop()