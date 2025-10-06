from dataclasses import dataclass, field
from datetime import date
from typing import List, Dict, Optional, Union
import json
import sqlite3

@dataclass
class RoleSettings:
    """
    Per-role configuration for scheduling.
    Attributes:
        role (str): Role name.
        day_required (int): Number required for day shift.
        night_required (int): Number required for night shift.
        priority (int): Priority level (1=critical, 2=high, etc.).
        min_experience_months (int): Minimum experience required.
        max_consecutive_shifts (int): Max consecutive shifts allowed.
        min_rest_between_shifts (float): Minimum rest hours between shifts.
        cost_weight (float): (Deprecated) Cost weight, not used in cost-free version.
        skill_requirements (List[str]): List of required skills.
    """
    role: str
    day_required: int = 1
    night_required: int = 1
    priority: int = 1  # 1=critical, 2=high, 3=normal, 4=low
    min_experience_months: int = 0
    max_consecutive_shifts: int = 5
    min_rest_between_shifts: float = 8.0
    cost_weight: float = 1.0
    skill_requirements: List[str] = field(default_factory=list)
    
@dataclass
@dataclass
class ShiftSettings:
    """
    Per-shift type configuration.
    Attributes:
        shift_type (str): Type of shift (day, night, etc.).
        start_hour (int): Shift start hour.
        duration_hours (float): Duration of the shift in hours.
        break_duration_minutes (int): Break duration in minutes.
        max_employees (int): Maximum employees per shift.
        min_employees (int): Minimum employees per shift.
        overtime_multiplier (float): Overtime pay multiplier (not used in cost-free version).
        night_differential (float): Night shift pay differential (not used in cost-free version).
        weekend_differential (float): Weekend pay differential (not used in cost-free version).
    """
    shift_type: str  # day, night, morning, evening, etc.
    start_hour: int = 8
    duration_hours: float = 8.0
    break_duration_minutes: int = 30
    max_employees: int = 10
    min_employees: int = 1
    overtime_multiplier: float = 1.5
    night_differential: float = 0.0
    weekend_differential: float = 0.1
    
@dataclass
class DaySettings:
    """
    Per-day configuration for scheduling.
    Attributes:
        day (str): Day of the week.
        is_business_day (bool): Whether this is a business day.
        role_multipliers (Dict[str, float]): Multipliers for roles (not used in cost-free version).
        shift_adjustments (Dict[str, Dict[str, Union[int, float]]]): Adjustments for shifts.
    """
    day: str  # Monday, Tuesday, etc.
    is_business_day: bool = True
    role_multipliers: Dict[str, float] = field(default_factory=dict)  # role -> multiplier
    shift_adjustments: Dict[str, Dict[str, Union[int, float]]] = field(default_factory=dict)  # shift -> {setting: value}
    special_requirements: List[str] = field(default_factory=list)
    rush_hours: List[Dict[str, Union[int, str]]] = field(default_factory=list)  # [{"start": 8, "end": 10, "extra_staff": 2}]

@dataclass
class BusinessSettings:
    """Enhanced business configuration for shift scheduling."""
    id: int = 1
    name: str = "My Business"
    planning_start: date = field(default_factory=date.today)
    planning_days: int = 7
    
    # Enhanced shift configurations
    shift_types: List[ShiftSettings] = field(default_factory=lambda: [
        ShiftSettings("day", 8, 8.0, 30, 10, 1, 1.5, 0.0, 0.1),
        ShiftSettings("night", 20, 8.0, 30, 8, 1, 1.5, 0.15, 0.2)
    ])
    
    # Enhanced role configurations
    role_settings: List[RoleSettings] = field(default_factory=lambda: [
        RoleSettings("Manager", 1, 1, 1, 12, 3, 10.0, 1.5, ["leadership", "customer_service"]),
        RoleSettings("Barista", 2, 1, 2, 3, 5, 8.0, 1.0, ["coffee_making", "customer_service"]),
        RoleSettings("Cashier", 1, 1, 2, 1, 5, 8.0, 0.8, ["pos_systems", "customer_service"])
    ])
    
    # Enhanced day configurations
    day_settings: List[DaySettings] = field(default_factory=lambda: [
        DaySettings("Monday", True, {"Manager": 1.0, "Barista": 1.2, "Cashier": 1.0}, 
                   {"day": {"min_employees": 3}, "night": {"min_employees": 2}}, 
                   ["deep_cleaning"], [{"start": 7, "end": 9, "extra_staff": 1}]),
        DaySettings("Tuesday", True, {"Manager": 1.0, "Barista": 1.0, "Cashier": 1.0}, 
                   {"day": {"min_employees": 2}, "night": {"min_employees": 1}}, [], []),
        DaySettings("Wednesday", True, {"Manager": 1.0, "Barista": 1.1, "Cashier": 1.0}, 
                   {"day": {"min_employees": 3}, "night": {"min_employees": 2}}, [], 
                   [{"start": 12, "end": 14, "extra_staff": 1}]),
        DaySettings("Thursday", True, {"Manager": 1.0, "Barista": 1.1, "Cashier": 1.0}, 
                   {"day": {"min_employees": 3}, "night": {"min_employees": 2}}, [], 
                   [{"start": 17, "end": 19, "extra_staff": 1}]),
        DaySettings("Friday", True, {"Manager": 1.2, "Barista": 1.4, "Cashier": 1.2}, 
                   {"day": {"min_employees": 4}, "night": {"min_employees": 3}}, ["inventory"], 
                   [{"start": 16, "end": 20, "extra_staff": 2}]),
        DaySettings("Saturday", True, {"Manager": 1.1, "Barista": 1.5, "Cashier": 1.3}, 
                   {"day": {"min_employees": 5}, "night": {"min_employees": 3}}, [], 
                   [{"start": 8, "end": 12, "extra_staff": 2}, {"start": 18, "end": 22, "extra_staff": 1}]),
        DaySettings("Sunday", True, {"Manager": 1.0, "Barista": 1.2, "Cashier": 1.1}, 
                   {"day": {"min_employees": 3}, "night": {"min_employees": 2}}, ["weekly_reports"], 
                   [{"start": 10, "end": 14, "extra_staff": 1}])
    ])
    
    # Legacy compatibility
    day_shift_start_hour: int = 8
    day_shift_length: float = 8.0
    night_shift_start_hour: int = 20
    night_shift_length: float = 8.0
    min_rest_hours: float = 11.0
    max_hours_per_week: float = 40.0
    min_hours_per_week: float = 0.0
    max_consecutive_days: int = 6
    allow_overtime: bool = True
    overtime_penalty: float = 50.0
    preference_penalty: float = 2.0
    unfilled_slot_penalty: float = 100.0
    
    # Compatibility fields
    roles_coverage: List[Dict[str, Optional[Union[int, str]]]] = field(default_factory=lambda: [
        {"role": "Manager", "day_required": 1, "night_required": 1},
        {"role": "Barista", "day_required": 2, "night_required": 1},
        {"role": "Cashier", "day_required": 1, "night_required": 1}
    ])
    daily_roles_coverage: Dict[str, Dict[str, Dict[str, int]]] = field(default_factory=lambda: {
        "Monday": {
            "Manager": {"day": 1, "night": 1},
            "Barista": {"day": 2, "night": 1},
            "Cashier": {"day": 1, "night": 1}
        },
        "Tuesday": {
            "Manager": {"day": 1, "night": 1},
            "Barista": {"day": 2, "night": 1},
            "Cashier": {"day": 1, "night": 1}
        },
        "Wednesday": {
            "Manager": {"day": 1, "night": 1},
            "Barista": {"day": 2, "night": 1},
            "Cashier": {"day": 1, "night": 1}
        },
        "Thursday": {
            "Manager": {"day": 1, "night": 1},
            "Barista": {"day": 2, "night": 1},
            "Cashier": {"day": 1, "night": 1}
        },
        "Friday": {
            "Manager": {"day": 1, "night": 1},
            "Barista": {"day": 3, "night": 2},
            "Cashier": {"day": 2, "night": 1}
        },
        "Saturday": {
            "Manager": {"day": 1, "night": 1},
            "Barista": {"day": 3, "night": 2},
            "Cashier": {"day": 2, "night": 1}
        },
        "Sunday": {
            "Manager": {"day": 1, "night": 1},
            "Barista": {"day": 2, "night": 1},
            "Cashier": {"day": 1, "night": 1}
        }
    })

    def to_json(self) -> str:
        """Convert to JSON string for database storage."""
        d = {}
        for key, value in self.__dict__.items():
            if key == "planning_start":
                d[key] = value.isoformat()
            elif isinstance(value, list) and len(value) > 0 and hasattr(value[0], '__dict__'):
                # Handle lists of dataclass objects like shift_types
                d[key] = [item.__dict__ for item in value]
            elif hasattr(value, '__dict__'):
                # Handle single dataclass objects
                d[key] = value.__dict__
            else:
                d[key] = value
        return json.dumps(d)

    @staticmethod
    def from_row(row: sqlite3.Row) -> "BusinessSettings":
        """Create BusinessSettings from database row."""
        d = json.loads(row["json"])
        if isinstance(d["planning_start"], str):
            d["planning_start"] = date.fromisoformat(d["planning_start"])
        
        # Reconstruct ShiftSettings objects from dictionaries
        if "shift_types" in d and isinstance(d["shift_types"], list):
            d["shift_types"] = [ShiftSettings(**shift_dict) for shift_dict in d["shift_types"]]
        
        # Reconstruct RoleSettings objects from dictionaries  
        if "role_settings" in d and isinstance(d["role_settings"], list):
            d["role_settings"] = [RoleSettings(**role_dict) for role_dict in d["role_settings"]]
        
        # Reconstruct DaySettings objects from dictionaries
        if "day_settings" in d and isinstance(d["day_settings"], list):
            d["day_settings"] = [DaySettings(**day_dict) for day_dict in d["day_settings"]]
        
        return BusinessSettings(**d)