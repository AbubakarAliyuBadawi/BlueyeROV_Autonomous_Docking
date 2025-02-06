import customtkinter as ctk
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import math
import tkinter as tk

class MissionState:
    def __init__(self, name, status="Inactive"):
        self.name = name
        self.status = status

class ROVController:
    def __init__(self):
        self.mission_states = {
            "UNDOCK": MissionState("UNDOCK"),
            "INSPECT_PIPELINE": MissionState("INSPECT_PIPELINE"),
            "RETURN_TO_DOCK": MissionState("RETURN_TO_DOCK")
        }
        self.current_state = None
        self.emergency_mode = False

    def start_mission(self):
        """Start the mission with the first state"""
        self.current_state = "UNDOCK"
        self.mission_states["UNDOCK"].status = "Active"

    def advance_state(self):
        """Advance to the next mission state"""
        states_order = ["UNDOCK", "INSPECT_PIPELINE", "RETURN_TO_DOCK"]
        if self.current_state in states_order:
            current_index = states_order.index(self.current_state)
            self.mission_states[self.current_state].status = "Inactive"
            
            if current_index < len(states_order) - 1:
                self.current_state = states_order[current_index + 1]
                self.mission_states[self.current_state].status = "Active"
                return True
        return False

    def trigger_emergency(self):
        """Trigger emergency return sequence"""
        self.emergency_mode = True
        for state in self.mission_states.values():
            state.status = "Inactive"

class ROVPlotCanvas:
    def __init__(self, master):
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self._setup_axes()
        self._setup_canvas(master)
        self._initialize_plot()

    def _setup_axes(self):
        self.axes = self.figure.add_subplot(111, projection='3d', computed_zorder=False)
        self._set_labels()
        self._set_limits()

    def _set_limits(self):
        self.axes.set_xlim([-100, 100])
        self.axes.set_ylim([-100, 100])
        self.axes.set_zlim(100, 85)

    def _set_labels(self):
        self.axes.set_xlabel('X [m]')
        self.axes.set_ylabel('Y [m]')
        self.axes.set_zlabel('Depth [m]')
        self.axes.set_title('ROV Position and Waypoints')

    def _setup_canvas(self, master):
        self.canvas = FigureCanvasTkAgg(self.figure, master=master)
        self.canvas.draw()
        self.canvas_widget = self.canvas.get_tk_widget()

    def _initialize_plot(self):
        self.path_line, = self.axes.plot3D([], [], [], 'b-', label='Blueye Path', linewidth=2, zorder=1)
        self.current_pos, = self.axes.plot3D([], [], [], 'yo', label='Blueye Position', markersize=10, zorder=3)
        
        waypoints = np.array([
            [-8.5, 8.54, 95.3],    # Docking station
            [-18.0, -25.0, 90.0],  # Pipeline point 1
            [20.0, 55.0, 90.0]     # Pipeline point 2
        ])
        
        self.axes.scatter([waypoints[0, 0]], [waypoints[0, 1]], [waypoints[0, 2]],
                         c='r', marker='s', s=100, label='Docking Station', zorder=2)
        self.axes.scatter(waypoints[1:, 0], waypoints[1:, 1], waypoints[1:, 2],
                         c='g', marker='s', s=100, label='Pipeline', zorder=2)
        
        self.axes.view_init(elev=25, azim=45)
        self.axes.grid(True, zorder=0)
        self.axes.legend()

class CircularMissionDisplay(ctk.CTkCanvas):
    def __init__(self, parent, controller, **kwargs):
        super().__init__(parent, **kwargs)
        self.controller = controller
        self.configure(highlightthickness=0)
        self.pack(fill="both", expand=True, padx=5, pady=5)
        self.bind('<Configure>', self._on_resize)
        
    def _on_resize(self, event):
        self.update_display()
        
    def update_display(self):
        self.delete("all")  # Clear canvas
        
        # Calculate dimensions
        width = self.winfo_width()
        height = self.winfo_height()
        center_x = width / 2
        center_y = height / 2
        radius = min(width, height) / 3
        
        # Draw title
        self.create_text(center_x, center_y - 10, 
                        text="Mission 1",
                        fill="white",
                        font=("Arial", 16, "bold"))
        
        # Draw connecting circle
        self.create_oval(center_x - radius - 20, center_y - radius - 20,
                        center_x + radius + 20, center_y + radius + 20,
                        outline="#334155", dash=(4, 4))
        
        # Calculate and draw states
        states = list(self.controller.mission_states.items())
        for i, (name, state) in enumerate(states):
            # Calculate position on circle
            angle = (i * 2 * math.pi / len(states)) - math.pi/2
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            
            # Draw connecting lines
            # next_i = (i + 1) % len(states)
            # next_angle = (next_i * 2 * math.pi / len(states)) - math.pi/2
            # next_x = center_x + radius * math.cos(next_angle)
            # next_y = center_y + radius * math.sin(next_angle)
            
            # self.create_line(x, y, next_x, next_y,
            #                fill="#475569", width=2)
            
            # Draw state circle
            color = "#22c55e" if state.status == "Active" else "#ef4444"
            self.create_oval(x - 25, y - 25, x + 25, y + 25,
                           fill=color, outline="#475569", width=2)
            
            # Draw outer ring
            self.create_oval(x - 30, y - 30, x + 30, y + 30,
                           outline=color, width=2, dash=(4, 4))
            
            # Draw state name
            self.create_text(x, y + 45,
                           text=name.replace("_", " "),
                           fill="white",
                           font=("Arial", 10))
            
            # Draw state status
            self.create_text(x, y + 60,
                           text=state.status,
                           fill=color,
                           font=("Arial", 8))

class MissionStateSection(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.pack(fill="both", expand=True, padx=5, pady=5)
        self._create_mission_display()

    def _create_mission_display(self):
        # Title
        title_frame = ctk.CTkFrame(self)
        title_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(
            title_frame,
            text="MISSION CONTROL PANEL",
            font=("Arial", 20, "bold")
        ).pack(anchor="center")

        # Circular mission display
        self.mission_display = CircularMissionDisplay(
            self,
            self.controller,
            width=300,
            height=300
        )

        # Control buttons
        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.pack(fill="x", padx=5, pady=5)
        
        # Start button
        self.start_button = ctk.CTkButton(
            self.button_frame,
            text="Start Mission",
            command=self._start_mission
        )
        self.start_button.pack(pady=5)
        
        # Next State button
        self.next_state_button = ctk.CTkButton(
            self.button_frame,
            text="Next State",
            command=self._advance_state
        )
        self.next_state_button.pack(pady=5)
        
        # Emergency button
        self.emergency_button = ctk.CTkButton(
            self.button_frame,
            text="Emergency Return",
            fg_color="red",
            hover_color="#8B0000",
            command=self._trigger_emergency
        )
        self.emergency_button.pack(pady=5)

    def _start_mission(self):
        self.controller.start_mission()
        self.mission_display.update_display()
        
    def _advance_state(self):
        self.controller.advance_state()
        self.mission_display.update_display()
        
    def _trigger_emergency(self):
        self.controller.trigger_emergency()
        self.mission_display.update_display()

class BlueyeInterface(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.controller = ROVController()
        self._setup_window()
        self._create_layout()
        self._initialize_sections()

    def _setup_window(self):
        self.title("Blueye Mission Interface")
        self.geometry("1200x800")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

    def _create_layout(self):
        self.left_frame = ctk.CTkFrame(self)
        self.right_frame = ctk.CTkFrame(self)
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

    def _initialize_sections(self):
        self.mission_states = MissionStateSection(self.left_frame, self.controller)
        self.plot_canvas = ROVPlotCanvas(self.right_frame)
        self.plot_canvas.canvas_widget.pack(fill="both", expand=True, padx=5, pady=5)

    def update_mission_state(self, state_name, status):
        if state_name in self.controller.mission_states:
            self.controller.mission_states[state_name].status = status
            self.mission_states.mission_display.update_display()

if __name__ == "__main__":
    app = BlueyeInterface()
    app.mainloop()