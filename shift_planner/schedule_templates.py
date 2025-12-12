# -*- coding: utf-8 -*-
"""
Schedule Templates Module
Provides reusable, rule-based schedule templates for recurring patterns
"""

import sqlite3
import json
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict

@dataclass
class ScheduleTemplate:
    """Schedule template with pattern definitions"""
    id: Optional[int] = None
    name: str = ""
    description: str = ""
    business_model: str = "5ήμερο"  # 5ήμερο, 6ήμερο
    pattern_type: str = "weekly"  # weekly, biweekly, monthly
    active_shifts: List[str] = None
    roles: List[str] = None
    role_coverage: Dict[str, Dict[str, int]] = None  # {role: {shift: count}}
    pattern_data: Dict[str, Any] = None  # Day-specific patterns
    rules: Dict[str, Any] = None  # Template-specific rules
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    is_active: bool = True
    
    def __post_init__(self):
        if self.active_shifts is None:
            self.active_shifts = []
        if self.roles is None:
            self.roles = []
        if self.role_coverage is None:
            self.role_coverage = {}
        if self.pattern_data is None:
            self.pattern_data = {}
        if self.rules is None:
            self.rules = {}
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        data = asdict(self)
        # Serialize lists and dicts to JSON strings for database storage
        data['active_shifts'] = json.dumps(self.active_shifts)
        data['roles'] = json.dumps(self.roles)
        data['role_coverage'] = json.dumps(self.role_coverage)
        data['pattern_data'] = json.dumps(self.pattern_data)
        data['rules'] = json.dumps(self.rules)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ScheduleTemplate':
        """Create from dictionary"""
        # Deserialize JSON strings back to objects
        if isinstance(data.get('active_shifts'), str):
            data['active_shifts'] = json.loads(data['active_shifts'])
        if isinstance(data.get('roles'), str):
            data['roles'] = json.loads(data['roles'])
        if isinstance(data.get('role_coverage'), str):
            data['role_coverage'] = json.loads(data['role_coverage'])
        if isinstance(data.get('pattern_data'), str):
            data['pattern_data'] = json.loads(data['pattern_data'])
        if isinstance(data.get('rules'), str):
            data['rules'] = json.loads(data['rules'])
        return cls(**data)


def init_templates_db(db_path: str = "shift_maker.sqlite3"):
    """Initialize templates database table"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedule_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            business_model TEXT DEFAULT '5ήμερο',
            pattern_type TEXT DEFAULT 'weekly',
            active_shifts TEXT,
            roles TEXT,
            role_coverage TEXT,
            pattern_data TEXT,
            rules TEXT,
            created_at TEXT,
            updated_at TEXT,
            created_by TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)
    
    conn.commit()
    conn.close()


def save_template(template: ScheduleTemplate, db_path: str = "shift_maker.sqlite3") -> int:
    """Save template to database"""
    # Ensure schema exists first
    init_templates_db(db_path)
    
    conn = sqlite3.connect(db_path, timeout=20.0)
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    template_dict = template.to_dict()
    
    if template.id:
        # Update existing
        template_dict['updated_at'] = now
        cursor.execute("""
            UPDATE schedule_templates
            SET name=?, description=?, business_model=?, pattern_type=?,
                active_shifts=?, roles=?, role_coverage=?, pattern_data=?,
                rules=?, updated_at=?, is_active=?
            WHERE id=?
        """, (
            template_dict['name'], template_dict['description'],
            template_dict['business_model'], template_dict['pattern_type'],
            template_dict['active_shifts'], template_dict['roles'],
            template_dict['role_coverage'], template_dict['pattern_data'],
            template_dict['rules'], template_dict['updated_at'],
            template_dict['is_active'], template.id
        ))
        template_id = template.id
    else:
        # Insert new
        template_dict['created_at'] = now
        template_dict['updated_at'] = now
        cursor.execute("""
            INSERT INTO schedule_templates
            (name, description, business_model, pattern_type, active_shifts,
             roles, role_coverage, pattern_data, rules, created_at, updated_at,
             created_by, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            template_dict['name'], template_dict['description'],
            template_dict['business_model'], template_dict['pattern_type'],
            template_dict['active_shifts'], template_dict['roles'],
            template_dict['role_coverage'], template_dict['pattern_data'],
            template_dict['rules'], template_dict['created_at'],
            template_dict['updated_at'], template_dict.get('created_by'),
            template_dict['is_active']
        ))
        template_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    return template_id


def load_template(template_id: int, db_path: str = "shift_maker.sqlite3") -> Optional[ScheduleTemplate]:
    """Load template from database"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM schedule_templates WHERE id=?
    """, (template_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return ScheduleTemplate.from_dict(dict(row))
    return None


def list_templates(
    active_only: bool = True,
    pattern_type: Optional[str] = None,
    db_path: str = "shift_maker.sqlite3"
) -> List[ScheduleTemplate]:
    """List all templates"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM schedule_templates WHERE 1=1"
    params = []
    
    if active_only:
        query += " AND is_active=1"
    
    if pattern_type:
        query += " AND pattern_type=?"
        params.append(pattern_type)
    
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [ScheduleTemplate.from_dict(dict(row)) for row in rows]


def delete_template(template_id: int, soft_delete: bool = True, db_path: str = "shift_maker.sqlite3"):
    """Delete template (soft or hard delete)"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    if soft_delete:
        cursor.execute("""
            UPDATE schedule_templates SET is_active=0, updated_at=?
            WHERE id=?
        """, (datetime.now().isoformat(), template_id))
    else:
        cursor.execute("DELETE FROM schedule_templates WHERE id=?", (template_id,))
    
    conn.commit()
    conn.close()


def apply_template_to_schedule(
    template: ScheduleTemplate,
    start_date: date,
    employees: List[Dict],
    days_count: int = 7
) -> Dict[str, Any]:
    """
    Apply template pattern to generate schedule data
    
    Returns:
        Dict with schedule structure based on template
    """
    result = {
        'template_name': template.name,
        'business_model': template.business_model,
        'active_shifts': template.active_shifts,
        'roles': template.roles,
        'role_coverage': template.role_coverage,
        'start_date': start_date.isoformat(),
        'days_count': days_count,
        'pattern_type': template.pattern_type,
        'assignments': []
    }
    
    # Generate day-by-day pattern
    current_date = start_date
    for day_num in range(days_count):
        day_name = current_date.strftime('%a')  # Mon, Tue, etc.
        
        # Get pattern for this day (if defined)
        day_pattern = template.pattern_data.get(day_name, {})
        
        # Apply role coverage for each shift
        for shift in template.active_shifts:
            for role in template.roles:
                required_count = template.role_coverage.get(role, {}).get(shift, 0)
                
                # Override with day-specific pattern if exists
                if day_pattern:
                    required_count = day_pattern.get(role, {}).get(shift, required_count)
                
                # Add assignment placeholders
                for i in range(required_count):
                    result['assignments'].append({
                        'date': current_date.isoformat(),
                        'day': day_name,
                        'shift': shift,
                        'role': role,
                        'employee_id': None,  # To be filled by scheduler
                        'employee_name': None,
                        'hours': _shift_hours(shift)
                    })
        
        current_date += timedelta(days=1)
    
    return result


def _shift_hours(shift: str) -> float:
    """Calculate hours for shift type"""
    shift_durations = {
        'morning': 8.0,
        'afternoon': 8.0,
        'evening': 8.0,
        'day': 8.0,
        'night': 8.0,
        'split': 10.0
    }
    return shift_durations.get(shift, 8.0)


def create_template_from_schedule(
    schedule_df: Any,  # pandas DataFrame
    name: str,
    description: str,
    business_model: str,
    active_shifts: List[str],
    roles: List[str]
) -> ScheduleTemplate:
    """
    Create a reusable template from an existing schedule
    
    Args:
        schedule_df: DataFrame with schedule data
        name: Template name
        description: Template description
        business_model: 5ήμερο or 6ήμερο
        active_shifts: List of shifts
        roles: List of roles
    
    Returns:
        ScheduleTemplate ready to save
    """
    import pandas as pd
    
    # Analyze schedule to extract patterns
    role_coverage = {}
    pattern_data = {}
    
    # Calculate average coverage per role/shift
    for role in roles:
        role_coverage[role] = {}
        for shift in active_shifts:
            # Count assignments for this role/shift combination
            count = 0
            if isinstance(schedule_df, pd.DataFrame):
                # Extract from DataFrame if available
                # This is a placeholder - actual implementation depends on DataFrame structure
                role_coverage[role][shift] = 1  # Default
            else:
                role_coverage[role][shift] = 1  # Default
    
    # Extract day-specific patterns (optional - for advanced templates)
    # This would analyze differences by day of week
    
    template = ScheduleTemplate(
        name=name,
        description=description,
        business_model=business_model,
        pattern_type='weekly',
        active_shifts=active_shifts,
        roles=roles,
        role_coverage=role_coverage,
        pattern_data=pattern_data,
        rules={},
        created_by=None
    )
    
    return template


# Initialize database when module is imported
try:
    init_templates_db()
except Exception as e:
    print(f"Warning: Could not initialize templates database: {e}")
