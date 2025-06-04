import os
import sys
import can
import time
import cantools
import threading
import subprocess
from datetime import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QTableWidgetItem, QLabel
from PyQt5.QtCore import pyqtSignal
from pynput import keyboard
import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import pygame
from pygame import joystick

from graph_window import GraphWindow  # this is a new file we will create

# Fix scaling (tweak to your liking)
os.environ["QT_SCALE_FACTOR"] = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"

# Optional: enforce a neutral look (similar to sudo look)
os.environ["QT_QPA_PLATFORMTHEME"] = "fusion"

joystick_enabled = True
prev_buttons = [0] * 13

# Load DBC file
dbc = cantools.database.load_file("EZkontrol_CAN.dbc")

# CAN IDs
VCU_CMD_ID = 0x0C01EFD0
MCU_HANDSHAKE_ID = 0x1801D0EF

# Control values
phase_current = 0
speed = 0
run_command = 1
control_mode = 1
life_signal = 0

# Run the shell script to set up CAN interface
try:
    subprocess.run(["bash", "init-can-hat_500.sh"], check=True)
except subprocess.CalledProcessError as e:
    print(f"Error setting up CAN interface: {e}")

# CAN bus setup
bus = can.interface.Bus(interface='socketcan', channel='can0', receive_own_messages=True)

# Handshake
print("Waiting for handshake from MCU...")
while True:
    message = bus.recv(timeout=10)
    if message and message.arbitration_id == MCU_HANDSHAKE_ID and list(message.data) == [0x55]*8:
        print("Received handshake from MCU. Sending acknowledgment...")
        break

bus.send(can.Message(arbitration_id=VCU_CMD_ID, is_extended_id=True, data=[0xAA]*8))
time.sleep(0.5)

class FocusableSpinBox(QtWidgets.QSpinBox):
    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self.clearFocus()
        else:
            super().keyPressEvent(event)
    
    def focusInEvent(self, event):
        super().focusInEvent(event)
        QtCore.QTimer.singleShot(0, self.selectAll)

# GUI Class
class CANMonitor(QtWidgets.QWidget):
    
    new_message = pyqtSignal(float, str, str, bytes, dict)

    # Methods for control panel
    def toggle_keyboard_control(self):
        self.keyboard_enabled = not self.keyboard_enabled
        self.toggle_button.setChecked(self.keyboard_enabled)
        self.update_toggle_button_style()
    
    def toggle_joystick_control(self):
        self.joystick_enabled = not self.joystick_enabled
        self.joystick_button.setChecked(self.joystick_enabled)
        self.update_joystick_button_style()

    def update_joystick_button_style(self):
        if self.joystick_enabled:
            self.joystick_button.setStyleSheet("background-color: lightblue")
        else:
            self.joystick_button.setStyleSheet("")
    
    def poll_joystick(self):
        if self.joystick_enabled:
            on_joystick_input()
            if hasattr(self, 'sync_inputs'):
                self.sync_inputs()

    def update_toggle_button_style(self):
        if self.keyboard_enabled:
            self.toggle_button.setStyleSheet("background-color: lightgreen")
        else:
            self.toggle_button.setStyleSheet("")

    def update_phase_current(self, value):
        global phase_current
        phase_current = value

    def update_speed(self, value):
        global speed
        speed = value

    def reset_input(self, which):
        global phase_current, speed
        if which == "phase":
            phase_current = 0
        elif which == "speed":
            speed = 0
        elif which == "both":
            phase_current = 0
            speed = 0
        self.sync_inputs()

    def set_preset(self, current_val, speed_val):
        global phase_current, speed
        phase_current = current_val
        speed = speed_val
        self.sync_inputs()

    def sync_inputs(self):
        self.phase_input.blockSignals(True)
        self.speed_input.blockSignals(True)
        self.phase_input.setValue(phase_current)
        self.speed_input.setValue(speed)
        self.phase_input.blockSignals(False)
        self.speed_input.blockSignals(False)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.MouseButtonPress:
            if not (self.phase_input.geometry().contains(self.mapFromGlobal(QtGui.QCursor.pos())) or
                    self.speed_input.geometry().contains(self.mapFromGlobal(QtGui.QCursor.pos()))):
                self.phase_input.clearFocus()
                self.speed_input.clearFocus()
        return super().eventFilter(obj, event)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("EZkontrol Visualizer")
        self.resize(900, 600)

        # Graph window instance placeholder
        self.graph_windows = []  # List to track all open graph windows

        self.installEventFilter(self)

        self.new_message.connect(self.display_message)

        # Table
        self.table = QtWidgets.QTableWidget(0, 4)
        
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(QtCore.Qt.NoFocus)
        self.table.setDragDropOverwriteMode(False)
        self.table.setDragDropMode(QtWidgets.QAbstractItemView.NoDragDrop)

        self.table.setHorizontalHeaderLabels(["Timestamp", "CAN ID", "Name", "Value"])
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 150)
        self.table.setColumnWidth(3, 170)
        self.row_map = {}  # Map from CAN ID and signal keys to row index
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
        self.table.verticalHeader().setVisible(False)
        self.table.setMaximumSize(542, 471)

        # # Graph setup
        # self.fig, self.ax = plt.subplots()
        # self.canvas = FigureCanvas(self.fig)
        # self.signal_values = []
        # self.time_values = []

        # # Create and store a Line2D object for efficient updates
        # self.line, = self.ax.plot([], [], label="Speed")
        # self.ax.legend()

        # # Timer for redrawing the graph more smoothly
        # self.graph_timer = QtCore.QTimer()
        # self.graph_timer.timeout.connect(self.update_graph)
        # self.graph_timer.start(250)  # Redraw every 250ms instead of 1000ms

        # Main vertical layout
        main_layout = QtWidgets.QVBoxLayout()

        # Horizontal layout for table + side widget
        content_layout = QtWidgets.QHBoxLayout()

        # Table on the left
        # Use QGroupBox to group table and label like Control Panel
        self.table_group = QtWidgets.QGroupBox("CAN Communication")
        self.table_group.setStyleSheet("QGroupBox { border: 0; margin-top: 2px; font-size: 14px; font-weight: bold; } QGroupBox::title { subcontrol-position: top center; padding: 0px; margin: 0px; }")
        #self.table_group.setStyleSheet("QGroupBox { border: 0; text-align: center;}")
        self.table_group.setMaximumSize(560, 510)
        table_group_layout = QtWidgets.QVBoxLayout()
        table_group_layout.addWidget(self.table)
        self.table_group.setLayout(table_group_layout)

        content_layout.addWidget(self.table_group)

        # Control Panel Widget
        self.control_panel = QtWidgets.QGroupBox("Control Panel")
        control_layout = QtWidgets.QVBoxLayout()

        # Keyboard control toggle button
        self.keyboard_enabled = True
        self.toggle_button = QtWidgets.QPushButton("Keyboard Ctrl")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(self.keyboard_enabled)
        self.toggle_button.clicked.connect(self.toggle_keyboard_control)
        self.update_toggle_button_style()
        control_layout.addWidget(self.toggle_button)
        
        # Joystick control toggle button
        self.joystick_enabled = True
        self.joystick_button = QtWidgets.QPushButton("Joystick Ctrl")
        self.joystick_button.setCheckable(True)
        self.joystick_button.setChecked(self.joystick_enabled)
        self.joystick_button.clicked.connect(self.toggle_joystick_control)
        self.update_joystick_button_style()
        control_layout.addWidget(self.joystick_button)
        
        # Joystick timer
        pygame.init()
        if joystick.get_count() > 0:
            joystick.init()
        else:
            print("No joystick detected.")

        self.joystick_timer = QtCore.QTimer()
        self.joystick_timer.timeout.connect(self.poll_joystick)
        self.joystick_timer.start(25) # note this limits speed increase due to delay

        # TargetPhaseCurrent input
        self.phase_label = QtWidgets.QLabel("TargetPhaseCurrent")
        self.phase_input = FocusableSpinBox()
        self.phase_input.setRange(-3200, 3200)
        self.phase_input.setValue(phase_current)
        self.phase_input.valueChanged.connect(self.update_phase_current)
        control_layout.addWidget(self.phase_label)
        control_layout.addWidget(self.phase_input)

        # TargetSpeed input
        self.speed_label = QtWidgets.QLabel("TargetSpeed")
        self.speed_input = FocusableSpinBox()
        self.speed_input.setRange(-32000, 32000)
        self.speed_input.setValue(speed)
        self.speed_input.valueChanged.connect(self.update_speed)
        control_layout.addWidget(self.speed_label)
        control_layout.addWidget(self.speed_input)

        #Reset Buttons
        reset_label = QtWidgets.QLabel("Reset:")
        control_layout.addWidget(reset_label)

        reset_buttons_layout = QtWidgets.QHBoxLayout()

        btn_reset_phase = QtWidgets.QPushButton("Phase Current")
        btn_reset_phase.clicked.connect(lambda: self.reset_input("phase"))
        reset_buttons_layout.addWidget(btn_reset_phase)

        btn_reset_speed = QtWidgets.QPushButton("Speed")
        btn_reset_speed.clicked.connect(lambda: self.reset_input("speed"))
        reset_buttons_layout.addWidget(btn_reset_speed)

        btn_reset_both = QtWidgets.QPushButton("Both")
        btn_reset_both.clicked.connect(lambda: self.reset_input("both"))
        reset_buttons_layout.addWidget(btn_reset_both)

        control_layout.addLayout(reset_buttons_layout)

        # Preset Buttons
        preset_label = QtWidgets.QLabel("Preset:")
        control_layout.addWidget(preset_label)

        preset_layout = QtWidgets.QGridLayout()

        presets = [
            ("Uphill", -200, -200),
            ("Uphill+", -300, -300),
            ("Flat", -100, -100),
            ("Downhill", 50, 50),
            ("Downhill+", 100, 100),
            ("Drive", 300, 300),
            ("Reverse", -300, -300),
            ("Brake", 0, 0),
        ]

        for i, (label, cur, spd) in enumerate(presets):
            btn = QtWidgets.QPushButton(label)
            btn.setFocusPolicy(QtCore.Qt.NoFocus)
            btn.clicked.connect(lambda _, c=cur, s=spd: self.set_preset(c, s))
            preset_layout.addWidget(btn, i // 4, i % 4)

        control_layout.addLayout(preset_layout)

        # Add the graph button
        plot_label = QtWidgets.QLabel("Plot Graph")
        self.graph_button = QtWidgets.QPushButton("Graph")
        self.graph_button.clicked.connect(self.open_graph_window)
        control_layout.addWidget(plot_label)
        control_layout.addWidget(self.graph_button)

        # No focus on arrow presses
        self.phase_input.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.speed_input.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.toggle_button.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_reset_phase.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_reset_speed.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_reset_both.setFocusPolicy(QtCore.Qt.NoFocus)
        self.graph_button.setFocusPolicy(QtCore.Qt.NoFocus)
        self.control_panel.setFocusPolicy(QtCore.Qt.NoFocus)

        self.control_panel.setLayout(control_layout)
        self.control_panel.setMaximumSize(300, 500)
        content_layout.addWidget(self.control_panel)

        # Add the horizontal content to the main layout
        main_layout.addLayout(content_layout)

        # Add canvas below / graph
        #main_layout.addWidget(self.canvas)

# Set main layout
        self.setLayout(main_layout)


        self.start_receiving()

        self.showMaximized()


    def update_graph(self):
        if self.time_values:
            self.line.set_data(self.time_values, self.signal_values)
            self.ax.relim()
            self.ax.autoscale_view()
            self.canvas.draw()
    
    def open_graph_window(self):
        # Clean up list before adding new window
        self.graph_windows = [w for w in self.graph_windows if w.isVisible()]
        
        new_window = GraphWindow(self)
        self.graph_windows.append(new_window)
        self.new_message.connect(new_window.receive_new_data)
        new_window.show()

    def start_receiving(self):
        thread = threading.Thread(target=self.receive_loop, daemon=True)
        thread.start()

    def receive_loop(self):
        while True:
            msg = bus.recv(timeout=0.05)
            if msg is None:
                continue


            #print(f"RX: {hex(msg.arbitration_id)} {msg.data.hex()}")

            try:
                decoded = dbc.decode_message(msg.arbitration_id, msg.data)
                #print(f"Decoded: {decoded}")

                msg_name = dbc.get_message_by_frame_id(msg.arbitration_id).name
                #self.display_message(msg.timestamp, hex(msg.arbitration_id).upper(), msg_name, msg.data, decoded)
                self.new_message.emit(msg.timestamp, hex(msg.arbitration_id).upper(), msg_name, bytes(msg.data), decoded)

                # used for graph on start screen
                # for signal, value in decoded.items():
                    # if signal.lower().startswith("err") or signal.lower().startswith("life"):
                        # continue
                    # if signal.lower() == "speed":
                        # self.time_values.append(time.time())
                        # self.signal_values.append(value)
                        # if len(self.time_values) > 100:
                            # self.time_values = self.time_values[-100:]
                            # self.signal_values = self.signal_values[-100:]
            except Exception as e:
                print(f"Decode failed: {e}")
                continue

    def display_message(self, timestamp, can_id, msg_name, data, decoded_signals):
        abs_time = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S.%f")[:-3]
        hex_data_str = ' '.join(f"{byte:02X}" for byte in data)

        if can_id not in self.row_map:
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, value in enumerate([abs_time, can_id, msg_name, hex_data_str]):
                item = QTableWidgetItem(value)
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.table.setItem(row, col, item)
            self.row_map[can_id] = row
        else:
            row = self.row_map[can_id]
            self.table.item(row, 0).setText(abs_time)
            self.table.item(row, 3).setText(hex_data_str)

        for col in range(4):
             self.table.item(row, col).setBackground(QtGui.QColor(240, 240, 240))  # light grey / 17, 250, 175 light lime green

        for signal, value in decoded_signals.items():
            if signal.lower().startswith("err") or signal.lower().startswith("life"):
                continue
            self.display_signal_row(can_id, signal, value)

    # --- Modified display_signal_row ---
    def display_signal_row(self, can_id, signal, value):
        key = f"{can_id}:{signal}"
        value_str = f"{value:.2f}" if isinstance(value, float) else str(value)

        if key not in self.row_map:
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, val in [(2, signal), (3, value_str)]:
                item = QTableWidgetItem(val)
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.table.setItem(row, col, item)
            self.row_map[key] = row
        else:
            row = self.row_map[key]
            self.table.item(row, 3).setText(value_str)

# Control sender thread
def to_signed_val(value, offset, scale):
    raw = int((value - offset) / scale)
    return raw & 0xFFFF

def send_controls():
    global speed, phase_current, run_command, control_mode, life_signal
    while True:
        current_raw = to_signed_val(phase_current, -3200, 0.1)
        speed_raw = to_signed_val(speed, -32000, 1.0)
        control_byte = (control_mode << 1) | run_command

        data = [
            current_raw & 0xFF,
            (current_raw >> 8) & 0xFF,
            speed_raw & 0xFF,
            (speed_raw >> 8) & 0xFF,
            control_byte,
            0x00,
            0x00,
            life_signal
        ]

        msg = can.Message(arbitration_id=VCU_CMD_ID, is_extended_id=True, data=data)
        bus.send(msg)
        life_signal = (life_signal + 1) % 256
        time.sleep(0.05)

# Keyboard controls
def on_press(key):
    app = QtWidgets.QApplication.instance()
    window = app.activeWindow()
    if not isinstance(window, CANMonitor) or not getattr(window, 'keyboard_enabled', True):
        return

    # Skip if spinbox has focus
    if window.phase_input.hasFocus() or window.speed_input.hasFocus():
        return

    global speed, phase_current, run_command, control_mode
    try:
        if key == keyboard.Key.up:
            speed += 20
        elif key == keyboard.Key.down:
            speed -= 20
        elif key == keyboard.Key.right:
            phase_current += 10
        elif key == keyboard.Key.left:
            phase_current -= 10
        elif key.char == 's':
            run_command ^= 1
        elif key.char == 'm':
            control_mode ^= 1
            #control_mode = (control_mode + 1) % 4

        if speed > 32000:
            speed = 32000
        elif speed < -32000:
            speed = -32000
        if phase_current > 3200:
            phase_current = 3200
        elif phase_current < -3200:
            phase_current = -3200

        if hasattr(window, 'sync_inputs'):
            window.sync_inputs()
    except AttributeError:
        pass
        
def on_joystick_input():
    global run_command, control_mode, speed, phase_current
    pygame.event.pump()
    if joystick.get_count() == 0:
        return

    try:
        js = joystick.Joystick(0)
        if not js.get_init():
            js.init()
    except Exception as e:
        print(f"Joystick init failed: {e}")
        return

    buttons = [js.get_button(i) for i in range(js.get_numbuttons())]
    axes = [js.get_axis(i) for i in range(js.get_numaxes())]
    
    # Debounce for X button (index 0)
    if buttons[0] and not prev_buttons[0]:  # Button down event
        run_command ^= 1

    # Debounce for Triangle button (index 3)
    if buttons[2] and not prev_buttons[2]:  # Button down event
        control_mode ^= 1
    
    #L1 decreases current
    if buttons[4]:
        phase_current -= 10
    
    #R1 increases current
    if buttons[5]:
        phase_current += 10
        
    # O resets speed
    if buttons[1]: #and not prev_buttons[1]: 
        speed = 0

    # Sqaure resets current
    if buttons[3]: #and not prev_buttons[3]: 
        phase_current = 0
    
    # Options / Pause resets current & speed
    if buttons[9]: #and not prev_buttons[9]: 
        phase_current = 0
        speed = 0

    # Update previous button states for debouncing
    prev_buttons = buttons[:]

    # R2 trigger usually axis 5
    if buttons[7]:
        r2 = (axes[5] + 1) / 2  # Normalize from -1..1 to 0..1
        speed += int(r2 * 25) # drag -3
    else:
        if speed > 0:
            speed -= 5
            if speed < 0:
                speed = 0
    
    # L2 trigger usually axis 2
    if buttons[6]:
        l2 = (axes[2] + 1) / 2
        speed -= int(l2 * 25)
    else:
        if speed < 0:
            speed += 5
            if speed > 0:
                speed = 0

    # Clamp values
    speed = max(-1000, min(1000, speed))
    phase_current = max(-1000, min(1000, phase_current))

if __name__ == '__main__':
    threading.Thread(target=send_controls, daemon=True).start()
    keyboard.Listener(on_press=on_press).start()

    app = QtWidgets.QApplication(sys.argv)
    win = CANMonitor()
    win.show()
    sys.exit(app.exec_())
