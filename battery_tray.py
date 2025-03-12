import sys
import time
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt5.QtGui import QIcon
import smbus2 as smbus
import os

# INA219 I2C address (default 0x40, adjust via i2cdetect -y 1 if different)
INA219_ADDRESS = 0x40

# INA219 register addresses
INA219_REG_CONFIG = 0x00
INA219_REG_SHUNTVOLTAGE = 0x01
INA219_REG_BUSVOLTAGE = 0x02
INA219_REG_POWER = 0x03
INA219_REG_CURRENT = 0x04
INA219_REG_CALIBRATION = 0x05

# Configuration settings (from Waveshare demo)
CONFIG_VALUE = 0x199F  # Default config
CALIBRATION_VALUE = 4096  # Default calibration

class INA219:
    """Class to interface with INA219 sensor on UPS HAT."""
    def __init__(self, i2c_bus=1, addr=INA219_ADDRESS):
        self.bus = smbus.SMBus(i2c_bus)
        self.addr = addr
        self._cal_value = CALIBRATION_VALUE
        self._current_lsb = 0
        self._power_lsb = 0
        self.set_calibration()

    def set_calibration(self):
        """Configure INA219 calibration and settings."""
        self._current_lsb = 0.1  # Current LSB = 100uA per bit
        self._power_lsb = 2  # Power LSB = 2mW per bit
        self.bus.write_word_data(self.addr, INA219_REG_CALIBRATION, self._cal_value)
        self.bus.write_word_data(self.addr, INA219_REG_CONFIG, CONFIG_VALUE)

    def read_word(self, reg):
        """Read 16-bit word from INA219 register."""
        high = self.bus.read_byte_data(self.addr, reg)
        low = self.bus.read_byte_data(self.addr, reg + 1)
        return (high << 8) + low

    def get_bus_voltage(self):
        """Get battery voltage in volts."""
        raw = self.read_word(INA219_REG_BUSVOLTAGE)
        return (raw >> 3) * 0.004  # 4mV per bit

    def get_current(self):
        """Get current in mA."""
        raw = self.read_word(INA219_REG_CURRENT)
        if raw > 32767:  # Handle negative values
            raw -= 65536
        return raw * self._current_lsb

    def get_power(self):
        """Get power in mW."""
        raw = self.read_word(INA219_REG_POWER)
        return raw * self._power_lsb

    def get_capacity(self):
        """Estimate battery capacity (SOC) as percentage.
        Assumes 100% at 4.2V, 0% at 3.0V. Adjust for your battery."""
        voltage = self.get_bus_voltage()
        if voltage >= 4.2:
            return 100
        elif voltage <= 3.0:
            return 0
        else:
            return int(((voltage - 3.0) / (4.2 - 3.0)) * 100)

class BatteryTray:
    """System tray icon for UPS HAT battery status."""
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.tray = QSystemTrayIcon()
        self.ina219 = INA219()
        self.update_icon()
        self.tray.show()

        # Context menu for right-click
        menu = QMenu()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quit)
        self.tray.setContextMenu(menu)

        # Update every 5 seconds
        self.timer = self.app.startTimer(5000)
        self.app.timerEvent = self.update_icon

    def update_icon(self, event=None):
        """Update tray icon and tooltip with battery data."""
        capacity = self.ina219.get_capacity()
        voltage = self.ina219.get_bus_voltage()
        current = self.ina219.get_current()

        # Select icon based on capacity
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

        # Optional: Shutdown at low battery (comment out if not needed)
        if capacity < 5:
            self.tray.showMessage("Low Battery", "Shutting down...", QSystemTrayIcon.Warning)
            time.sleep(5)
            os.system("sudo shutdown -h now")

    def quit(self):
        """Exit the application."""
        self.app.quit()

    def run(self):
        """Start the application loop."""
        sys.exit(self.app.exec_())

if __name__ == "__main__":
    tray = BatteryTray()
    tray.run()
