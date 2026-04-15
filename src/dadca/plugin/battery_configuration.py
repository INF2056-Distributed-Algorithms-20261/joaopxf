from dataclasses import dataclass


@dataclass
class BatteryConfiguration:
    battery_tolerance: float = 10
    discharge_per_meter_rate: float = 0.05
    charge_per_time_rate: float = 0.10