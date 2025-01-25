import customtkinter as ctk
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

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

class ROVPlotCanvas:
    def __init__(self, master):
        self.figure = Figure(figsize=(8, 6), dpi=100, facecolor='#2b2b2b')
        self._setup_axes()
        self._setup_canvas(master)
        self._initialize_plot()

    def _setup_axes(self):
        self.axes = self.figure.add_subplot(111, projection='3d', computed_zorder=False)
        self.axes.set_facecolor('#2b2b2b')
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

class MissionStateSection(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.pack(fill="x", padx=5, pady=5)
        self._create_mission_display()

    def _create_mission_display(self):
        ctk.CTkLabel(self, text="MISSION STATES").pack(anchor="w", padx=5, pady=5)
        for state in self.controller.mission_states.values():
            self._create_state_row(state)

    def _create_state_row(self, state):
        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(frame, text=f"{state.name}:").pack(side="left", padx=5)
        color = "green" if state.status == "Active" else "red"
        ctk.CTkLabel(frame, text=state.status, text_color=color).pack(side="left")

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
        ctk.set_appearance_mode("dark")
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
            # Trigger UI update
            self._initialize_sections()

if __name__ == "__main__":
    app = BlueyeInterface()
    app.mainloop()