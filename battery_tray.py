#!/usr/bin/env python3
# Battery Tray for Waveshare UPS HAT on Raspberry Pi
# Displays battery SOC in system tray and runs at boot (Wayland).

import sys
import time
import os
import subprocess

print("Starting script...")

def install_dependencies():
    print("Installing dependencies...")
    if os.geteuid() != 0:
        print("Needs sudo for installation.")
        subprocess.run(["sudo", sys.executable] + sys.argv)
        sys.exit(0)
    subprocess.run(["apt-get", "update"], check=True)
    subprocess.run([
        "apt-get", "install", "-y",
        "python3", "python3-pip", "python3-pyqt5", "i2c-tools", "p7zip", "git", "tango-icon-theme"
    ], check=True)
    subprocess.run(["pip3", "install", "smbus2"], check=True)
    i2c_status = subprocess.run(["raspi-config", "nonint", "get_i2c"], capture_output=True, text=True)
    if i2c_status.stdout.strip() != "0":
        print("Enabling I2C and rebooting...")
        subprocess.run(["raspi-config", "nonint", "do_i2c", "0"], check=True)
        subprocess.run(["reboot"], check=True)
    subprocess.run(["usermod", "-aG", "i2c", "pi"], check=True)
    print("Setup complete. Reboot might be needed for I2C permissions.")

try:
    print("Importing PyQt5 and smbus2...")
    from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu
    from PyQt5.QtGui import QIcon
    import smbus2 as smbus
except ImportError:
    install_dependencies()
    print("Retrying imports after installation...")
    from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu
    from PyQt5.QtGui import QIcon
    import smbus2 as smbus

# Use Wayland backend
os.environ["QT_QPA_PLATFORM"] = "wayland"
os.environ["QT_LOGGING_RULES"] = "*.debug=true"  # Enable Qt debug output
if "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":0"  # Fallback, though Wayland might ignore this
print(f"DISPLAY set to: {os.environ['DISPLAY']}, Platform: {os.environ['QT_QPA_PLATFORM']}")

INA219_ADDRESS = 0x42
INA219_REG_CONFIG = 0x00
INA219_REG_BUSVOLTAGE = 0x02
INA219_REG_CALIBRATION = 0x05

CONFIG_VALUE = 0x19FF
CALIBRATION_VALUE = 4096

class INA219:
    def __init__(self, i2c_bus=1, addr=INA219_ADDRESS):
        print(f"Initializing INA219 on bus {i2c_bus}, address {hex(addr)}")
        self.bus = smbus.SMBus(i2c_bus)
        self.addr = addr
        self._cal_value = CALIBRATION_VALUE
        self.set_calibration()
        time.sleep(0.5)

    def set_calibration(self):
        print("Setting calibration...")
        self.bus.write_word_data(self.addr, INA219_REG_CALIBRATION, self._cal_value)
        self.bus.write_word_data(self.addr, INA219_REG_CONFIG, CONFIG_VALUE)
        print("Calibration set")

    def read_word(self, reg):
        high = self.bus.read_byte_data(self.addr, reg)
        low = self.bus.read_byte_data(self.addr, reg + 1)
        return (high << 8) + low

    def get_bus_voltage(self):
        raw = self.read_word(INA219_REG_BUSVOLTAGE)
        voltage = (raw >> 3) * 0.004
        return voltage

    def get_capacity(self):
        voltage = self.get_bus_voltage()
        capacity = (voltage - 6) / 2.4 * 100
        if capacity > 100:
            capacity = 100
        if capacity < 0:
            capacity = 0
        print(f"Voltage: {voltage:.2f}V, Capacity: {capacity:.1f}%")
        return capacity

class BatteryTray:
    def __init__(self):
        print("Initializing BatteryTray...")
        try:
            self.app = QApplication(sys.argv)
            print("QApplication initialized")
        except Exception as e:
            print(f"QApplication failed: {e}")
            raise
        self.tray = QSystemTrayIcon()
        self.ina219 = INA219()
        self.update_icon()
        self.tray.show()
        print("Tray shown")
        menu = QMenu()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quit)
        self.tray.setContextMenu(menu)
        self.timer = self.app.startTimer(5000)
        self.app.timerEvent = self.update_icon

    def update_icon(self, event=None):
        print("Updating icon...")
        capacity = self.ina219.get_capacity()
        if capacity > 75:
            icon = QIcon.fromTheme("battery-full")
        elif capacity > 50:
            icon = QIcon.fromTheme("battery-good")
        elif capacity > 25:
            icon = QIcon.fromTheme("battery-low")
        else:
            icon = QIcon.fromTheme("battery-caution")
        if not icon.isNull():
            self.tray.setIcon(icon)
            print("Icon set")
        else:
            self.tray.setIcon(QIcon.fromTheme("battery-missing"))
            print("Warning: Using fallback icon")
        self.tray.setToolTip(f"Battery: {capacity:.1f}%")

    def quit(self):
        self.app.quit()

    def run(self):
        print("Running application...")
        sys.exit(self.app.exec_())

def setup_autostart():
    script_path = os.path.abspath(__file__)
    autostart_dir = os.path.expanduser("~/.config/lxsession/LXDE-pi")
    autostart_file = os.path.join(autostart_dir, "autostart")
    if not os.path.exists(autostart_dir):
        os.makedirs(autostart_dir)
    entry = f"@python3 {script_path}"
    if os.path.exists(autostart_file):
        with open(autostart_file, "r") as f:
            if entry in f.read():
                print("Autostart already configured.")
                return
    with open(autostart_file, "a") as f:
        f.write(f"{entry}\n")
    print(f"Autostart enabled: {script_path}")

if __name__ == "__main__":
    setup_autostart()
    tray = BatteryTray()
    tray.run()
