#!/usr/bin/env python3
# Battery Tray for Waveshare UPS HAT on Raspberry Pi
# Displays battery SOC, voltage, and current in system tray.
# Installs dependencies on first run. Use --install-autostart for boot.

import sys
import time
import os
import subprocess
import argparse

def install_dependencies():
    print("Installing dependencies...")
    if os.geteuid() != 0:
        print("Needs sudo for installation.")
        subprocess.run(["sudo", sys.executable] + sys.argv)
        sys.exit(0)
    subprocess.run(["apt-get", "update"], check=True)
    subprocess.run([
        "apt-get", "install", "-y",
        "python3", "python3-pip", "python3-pyqt5", "i2c-tools", "p7zip", "git"
    ], check=True)
    subprocess.run(["pip3", "install", "smbus2"], check=True)
    i2c_status = subprocess.run(["raspi-config", "nonint", "get_i2c"], capture_output=True, text=True)
    if i2c_status.stdout.strip() != "0":
        print("Enabling I2C and rebooting...")
        subprocess.run(["raspi-config", "nonint", "do_i2c", "0"], check=True)
        subprocess.run(["reboot"], check=True)
    print("Setup complete.")

try:
    from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu
    from PyQt5.QtGui import QIcon
    import smbus2 as smbus
except ImportError:
    install_dependencies()
    from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu
    from PyQt5.QtGui import QIcon
    import smbus2 as smbus

if "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":0"

INA219_ADDRESS = 0x42  # Updated to match your UPS HAT
INA219_REG_CONFIG = 0x00
INA219_REG_SHUNTVOLTAGE = 0x01
INA219_REG_BUSVOLTAGE = 0x02
INA219_REG_POWER = 0x03
INA219_REG_CURRENT = 0x04
INA219_REG_CALIBRATION = 0x05

CONFIG_VALUE = 0x199F
CALIBRATION_VALUE = 4096

class INA219:
    def __init__(self, i2c_bus=1, addr=INA219_ADDRESS):
        self.bus = smbus.SMBus(i2c_bus)
        self.addr = addr
        self._cal_value = CALIBRATION_VALUE
        self._current_lsb = 0
        self._power_lsb = 0
        self.set_calibration()

    def set_calibration(self):
        self._current_lsb = 0.1  # 100uA per bit
        self._power_lsb = 2  # 2mW per bit
        self.bus.write_word_data(self.addr, INA219_REG_CALIBRATION, self._cal_value)
        self.bus.write_word_data(self.addr, INA219_REG_CONFIG, CONFIG_VALUE)

    def read_word(self, reg):
        high = self.bus.read_byte_data(self.addr, reg)
        low = self.bus.read_byte_data(self.addr, reg + 1)
        return (high << 8) + low

    def get_bus_voltage(self):
        raw = self.read_word(INA219_REG_BUSVOLTAGE)
        return (raw >> 3) * 0.004  # 4mV per bit

    def get_current(self):
        raw = self.read_word(INA219_REG_CURRENT)
        if raw > 32767:
            raw -= 65536
        return raw * self._current_lsb

    def get_power(self):
        raw = self.read_word(INA219_REG_POWER)
        return raw * self._power_lsb

    def get_capacity(self):
        voltage = self.get_bus_voltage()
        if voltage >= 4.2:
            return 100
        elif voltage <= 3.0:
            return 0
        else:
            return int(((voltage - 3.0) / (4.2 - 3.0)) * 100)

class BatteryTray:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.tray = QSystemTrayIcon()
        self.ina219 = INA219()
        self.update_icon()
        self.tray.show()
        menu = QMenu()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quit)
        self.tray.setContextMenu(menu)
        self.timer = self.app.startTimer(5000)
        self.app.timerEvent = self.update_icon

    def update_icon(self, event=None):
        capacity = self.ina219.get_capacity()
        voltage = self.ina219.get_bus_voltage()
        current = self.ina219.get_current()
        if capacity > 75:
            icon = QIcon.fromTheme("battery-full")
        elif capacity > 50:
            icon = QIcon.fromTheme("battery-good")
        elif capacity > 25:
            icon = QIcon.fromTheme("battery-low")
        else:
            icon = QIcon.fromTheme("battery-caution")
        self.tray.setIcon(icon)
        self.tray.setToolTip(f"Battery: {capacity}% | {voltage:.2f}V | {current:.2f}mA")
        if capacity < 5:
            self.tray.showMessage("Low Battery", "Shutting down...", QSystemTrayIcon.Warning)
            time.sleep(5)
            os.system("sudo shutdown -h now")

    def quit(self):
        self.app.quit()

    def run(self):
        sys.exit(self.app.exec_())

def install_autostart():
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
    parser = argparse.ArgumentParser(description="Battery Tray for UPS HAT")
    parser.add_argument("--install-autostart", action="store_true", help="Run at boot")
    args = parser.parse_args()
    if args.install_autostart:
        install_autostart()
    else:
        tray = BatteryTray()
        tray.run()
