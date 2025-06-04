from PyQt5 import QtWidgets, QtCore
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

class GraphWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(None)

        self.setWindowTitle("Signal Plot")
        self.setMinimumSize(800, 400)
        self.setWindowFlags(QtCore.Qt.Window)

        self.signals = {}  # key: signal name, value: (timestamps list, values list)
        self.active_signals = set()
        self.lines = {}  # signal name -> Line2D object
        self.time_window = 20  # default to 20 seconds
        self.frozen = False

        self.layout = QtWidgets.QVBoxLayout(self)

        # Top control panel: signal buttons + time window + freeze
        top_controls = QtWidgets.QHBoxLayout()
        self.layout.addLayout(top_controls)

        self.button_layout = QtWidgets.QHBoxLayout()
        top_controls.addLayout(self.button_layout)

        # Time window buttons
        self.time_buttons = QtWidgets.QHBoxLayout()
        for secs in [10, 20, 30, 45, 60]:
            btn = QtWidgets.QPushButton(f"{secs}s")
            btn.clicked.connect(lambda _, s=secs: self.set_time_window(s))
            self.time_buttons.addWidget(btn)
        top_controls.addLayout(self.time_buttons)

        # Freeze button
        self.freeze_button = QtWidgets.QPushButton("Freeze")
        self.freeze_button.setCheckable(True)
        self.freeze_button.toggled.connect(self.toggle_freeze)
        top_controls.addWidget(self.freeze_button)

        self.canvas = FigureCanvas(plt.Figure())
        self.ax = self.canvas.figure.subplots()
        self.layout.addWidget(self.canvas)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.refresh_plot)
        self.timer.start(250)

    def set_time_window(self, seconds):
        self.time_window = seconds

    def toggle_freeze(self, checked):
        self.frozen = checked

    def receive_new_data(self, timestamp, can_id, msg_name, data, decoded_signals):
        if self.frozen:
            return

        t = timestamp
        for sig, val in decoded_signals.items():
            if sig.lower().startswith("err") or sig.lower().startswith("life"):
                continue
            if sig not in self.signals:
                self.signals[sig] = ([], [])
                self.add_button_for_signal(sig)
            times, values = self.signals[sig]
            times.append(t)
            values.append(val)

            # Keep only the last N seconds of data
            while times and (t - times[0]) > self.time_window:
                times.pop(0)
                values.pop(0)

    def add_button_for_signal(self, signal):
        btn = QtWidgets.QPushButton(signal)
        btn.setCheckable(True)
        btn.toggled.connect(lambda checked, sig=signal: self.toggle_signal(sig, checked))
        self.button_layout.addWidget(btn)

    def toggle_signal(self, signal, enabled):
        if enabled:
            self.active_signals.add(signal)
            if signal not in self.lines:
                line, = self.ax.plot([], [], label=signal)
                self.lines[signal] = line
        else:
            self.active_signals.discard(signal)
            if signal in self.lines:
                line = self.lines.pop(signal)
                line.remove()

    def refresh_plot(self):
        if self.frozen:
            return

        for sig in self.active_signals:
            times, values = self.signals.get(sig, ([], []))
            if times and values:
                relative_times = [t - times[0] for t in times]
                self.lines[sig].set_data(relative_times, values)

        self.ax.relim()
        self.ax.autoscale_view()

        if self.active_signals:
            self.ax.legend(loc='upper right')

        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Value")
        self.canvas.draw()
