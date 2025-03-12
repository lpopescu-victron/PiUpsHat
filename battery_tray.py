#!/usr/bin/python3
import sys
import time
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt5.QtGui import QIcon
import smbus2 as smbus
import os

# INA219 I2C address (default is 0x40, adjust if needed)
INA219_ADDRESS = 0x40

# INA219 Register addresses
INA219_REG_CONFIG = 0x00
INA219_REG_SHUNTVOLTAGE = 0x01
INA219_REG_BUSVOLTAGE = 0x02
INA219_REG_POWER = 0x03
INA219_REG_CURRENT = 0x04
INA219_REG_CALIBRATION = 0x05

# Configuration settings
CONFIG_VALUE = 0x199F  # Default from Waveshare, adjust if needed
CALIBRATION_VALUE = 4096  # Default calibration

class INA219:
    def __init__(self, i2c_bus=1, addr=INA219_ADDRESS):
        self.bus = smbus.SMBus(i2c_bus)
        self.addr = addr
        self._cal_value = CALIBRATION_VALUE
        self._current_lsb = 0
        self._power_lsb = 0
        self.set_calibration()

    def set_calibration(self):
        self._current_lsb = 0.1  # Current LSB = 100uA per bit
        self._power_lsb = 2  # Power LSB = 2mW per bit
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
        if raw > 32767:  # Handle negative values
            raw -= 65536
        return raw * self._current_lsb

    def get_power(self):
        raw = self.read_word(INA219_REG_POWER)
        return raw * self._power_lsb

    def get_capacity(self):
        # Simplified: Assume 100% at 4.2V, 0% at 3.0V (adjust for your battery)
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

        # Menu for right-click
        menu = QMenu()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quit)
        self.tray.setContextMenu(menu)

        # Update every 5 seconds
        self.timer = self.app.startTimer(5000)
        self.app.timerEvent = self.update_icon

    def update_icon(self, event=None):
        capacity = self.ina219.get_capacity()
        voltage = self.ina219.get_bus_voltage()
        current = self.ina219.get_current()

        # Set icon based on capacity (you can replace with custom icons)
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

        # Optional: Shutdown at low battery
        if capacity < 5:
            self.tray.showMessage("Low Battery", "Shutting down...", QSystemTrayIcon.Warning)
            time.sleep(5)
            os.system("sudo shutdown -h now")

    def quit(self):
        self.app.quit()

    def run(self):
        sys.exit(self.app.exec_())

if __name__ == "__main__":
    tray = BatteryTray()
    tray.run()
