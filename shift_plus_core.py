#!/usr/bin/env python3
"""
Advanced Scheduling Core Engine for Shift Plus
Implements hybrid AI + MILP + Greedy scheduling algorithms with importance weighting
"""

from __future__ import annotations
from typing import List, Dict, Union, Optional, Any, Tuple
import json
import pandas as pd
import os
import sqlite3
from datetime import date, timedelta
from dataclasses import dataclass, field
from dotenv import load_dotenv
import openai
import logging
from collections import defaultdict
import random

# Try to import optimization libraries
try:
    import pulp
    MILP_AVAILABLE = True
except ImportError:
    MILP_AVAILABLE = False
    logging.warning("PuLP not available. MILP optimization disabled.")

# Import the save_business_settings function
from common.business_settings import BusinessSettings

logger = logging.getLogger(__name__)

# Type aliases for better type hints
EmployeeDict = Dict[str, Union[int, str, float, List[str], None]]
RoleCoverage = Dict[str, Union[str, int]]
ShiftSlot = Dict[str, Union[str, date]]
ScheduleAssignment = Dict[str, Optional[int]]

@dataclass
class CustomShiftRequirement:
    """Custom shift requirement for specific date/shift/role combinations."""
    date: str
    shift_type: str  # "day" or "night"
    role: str
    required_count: int
    reason: str = ""
    
@dataclass
class ShiftCustomization:
    """Container for all custom shift requirements."""
    custom_requirements: List[CustomShiftRequirement] = field(default_factory=list)
    
    def add_requirement(self, date: str, shift_type: str, role: str, count: int, reason: str = ""):
        """Add a custom requirement."""
        # Remove existing requirement for same date/shift/role if exists
        self.custom_requirements = [
            req for req in self.custom_requirements 
            if not (req.date == date and req.shift_type == shift_type and req.role == role)
        ]
        self.custom_requirements.append(
            CustomShiftRequirement(date, shift_type, role, count, reason)
        )
    
    def get_requirement(self, date: str, shift_type: str, role: str) -> Optional[int]:
        """Get custom requirement count for specific date/shift/role."""
        for req in self.custom_requirements:
            if req.date == date and req.shift_type == shift_type and req.role == role:
                return req.required_count
        return None

def _default_days() -> List[str]:
    """Default factory for days_available."""
    return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].copy()

@dataclass
class Employee:
    """Employee information for shift scheduling."""
    id: Optional[int]
    name: str
    role: str
    preferred_shift: str = "any"
    days_available: List[str] = field(default_factory=_default_days)
    max_hours_per_week: float = 40.0
    min_hours_per_week: float = 0.0
    importance: float = 1.0

    def to_dict(self) -> EmployeeDict:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "preferred_shift": self.preferred_shift,
            "days_available": json.dumps(self.days_available),
            "max_hours_per_week": self.max_hours_per_week,
            "min_hours_per_week": self.min_hours_per_week,
            "importance": self.importance
        }

@dataclass
class SchedulingResult:
    """Result container for scheduling operations"""
    schedule_df: pd.DataFrame
    algorithm_used: str
    success: bool
    violations: List[Dict[str, Any]]
    optimization_score: float
    execution_time: float
    metadata: Dict[str, Any]

class HybridScheduler:
    """
    Advanced hybrid scheduler combining AI, MILP optimization, and Greedy heuristics.
    
    Features:
    - Employee importance weighting
    - Multi-constraint optimization
    - Fallback algorithm chain
    - Real-time violation detection
    """
    
    def __init__(self, business_settings: Any, employees: List[Employee]):
        self.bs = business_settings
        self.employees = employees
        self.logger = logging.getLogger(f"{__name__}.HybridScheduler")
        
    def generate_schedule(self, 
                         shift_slots: List[Dict[str, Any]], 
                         strategy: str = "hybrid") -> SchedulingResult:
        """
        Generate optimal schedule using specified strategy.
        
        Args:
            shift_slots: List of shift requirements with date, role, shift_type
            strategy: "hybrid", "ai", "milp", "greedy", or "auto"
            
        Returns:
            SchedulingResult with schedule and metadata
        """
        start_time = pd.Timestamp.now()
        
        if strategy == "hybrid" or strategy == "auto":
            return self._hybrid_scheduling(shift_slots, start_time)
        elif strategy == "ai" and openai_available:
            return self._ai_scheduling(shift_slots, start_time)
        elif strategy == "milp" and MILP_AVAILABLE:
            return self._milp_scheduling(shift_slots, start_time)
        elif strategy == "greedy":
            return self._greedy_scheduling(shift_slots, start_time)
        else:
            # Fallback to greedy if requested strategy unavailable
            self.logger.warning(f"Strategy '{strategy}' unavailable, falling back to greedy")
            return self._greedy_scheduling(shift_slots, start_time)
    
    def _hybrid_scheduling(self, shift_slots: List[Dict[str, Any]], start_time) -> SchedulingResult:
        """Hybrid approach: AI for initial draft, MILP for optimization, Greedy for fixes"""
        self.logger.info("Starting hybrid scheduling approach")
        
        try:
            # Phase 1: AI generates initial schedule if available
            if openai_available:
                ai_result = self._ai_scheduling(shift_slots, start_time, phase="initial")
                if ai_result.success and not ai_result.schedule_df.empty:
                    initial_schedule = ai_result.schedule_df
                    self.logger.info("AI generated initial schedule successfully")
                else:
                    initial_schedule = self._generate_empty_schedule(shift_slots)
            else:
                initial_schedule = self._generate_empty_schedule(shift_slots)
            
            # Phase 2: MILP optimization if available
            if MILP_AVAILABLE:
                milp_result = self._milp_scheduling(shift_slots, start_time, 
                                                 initial_schedule=initial_schedule)
                if milp_result.success:
                    optimized_schedule = milp_result.schedule_df
                    self.logger.info("MILP optimization completed successfully")
                else:
                    optimized_schedule = initial_schedule
            else:
                optimized_schedule = initial_schedule
            
            # Phase 3: Greedy refinement for unfilled slots
            final_result = self._greedy_scheduling(shift_slots, start_time, 
                                                 base_schedule=optimized_schedule)
            
            # Calculate hybrid metrics
            execution_time = (pd.Timestamp.now() - start_time).total_seconds()
            violations = self._validate_schedule(final_result.schedule_df)
            
            return SchedulingResult(
                schedule_df=final_result.schedule_df,
                algorithm_used="hybrid",
                success=True,
                violations=violations,
                optimization_score=self._calculate_optimization_score(final_result.schedule_df),
                execution_time=execution_time,
                metadata={
                    "phases_used": ["AI" if openai_available else None, 
                                  "MILP" if MILP_AVAILABLE else None, 
                                  "Greedy"],
                    "unfilled_slots": len(final_result.schedule_df[
                        final_result.schedule_df['employee_id'].isna()
                    ])
                }
            )
            
        except Exception as e:
            self.logger.error(f"Hybrid scheduling failed: {e}")
            # Fallback to greedy
            return self._greedy_scheduling(shift_slots, start_time)
    
    def _ai_scheduling(self, shift_slots: List[Dict[str, Any]], start_time, 
                      phase: str = "standalone", initial_schedule: pd.DataFrame = None) -> SchedulingResult:
        """AI-powered scheduling using LLM with importance weighting"""
        if not openai_available:
            return SchedulingResult(
                schedule_df=pd.DataFrame(),
                algorithm_used="ai",
                success=False,
                violations=[],
                optimization_score=0.0,
                execution_time=0.0,
                metadata={"error": "AI not available"}
            )
        
        try:
            # Prepare employee data with importance scores and unavailability info
            employees_data = []
            # Get date range for the scheduling period
            dates = [pd.to_datetime(slot['date']).strftime('%Y-%m-%d') for slot in shift_slots]
            start_date = min(dates) if dates else pd.Timestamp.now().strftime('%Y-%m-%d')
            end_date = max(dates) if dates else pd.Timestamp.now().strftime('%Y-%m-%d')
            
            for emp in self.employees:
                # Get unavailability periods for this employee
                unavailable_periods = []
                if emp.id is not None:
                    unavailable_periods = get_employee_unavailability_for_period(emp.id, start_date, end_date)
                
                emp_dict = {
                    "id": emp.id,
                    "name": emp.name,
                    "role": emp.role,
                    "max_hours": emp.max_hours_per_week,
                    "importance": getattr(emp, 'importance', 1.0),
                    "preferred_shift": emp.preferred_shift,
                    "days_available": emp.days_available,
                    "unavailable_periods": unavailable_periods
                }
                employees_data.append(emp_dict)
            
            # Create AI prompt with business context
            prompt = self._create_ai_prompt(shift_slots, employees_data, phase)
            
            # Call OpenAI API
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert workforce scheduling assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.1
            )
            
            content = response["choices"][0]["message"]["content"]
            schedule_df = self._parse_ai_response(content, shift_slots)
            
            execution_time = (pd.Timestamp.now() - start_time).total_seconds()
            violations = self._validate_schedule(schedule_df)
            
            return SchedulingResult(
                schedule_df=schedule_df,
                algorithm_used="ai",
                success=not schedule_df.empty,
                violations=violations,
                optimization_score=self._calculate_optimization_score(schedule_df),
                execution_time=execution_time,
                metadata={"phase": phase, "tokens_used": response.get("usage", {})}
            )
            
        except Exception as e:
            self.logger.error(f"AI scheduling failed: {e}")
            return SchedulingResult(
                schedule_df=pd.DataFrame(),
                algorithm_used="ai",
                success=False,
                violations=[],
                optimization_score=0.0,
                execution_time=0.0,
                metadata={"error": str(e)}
            )
    
    def _milp_scheduling(self, shift_slots: List[Dict[str, Any]], start_time,
                        initial_schedule: pd.DataFrame = None) -> SchedulingResult:
        """MILP optimization for mathematically optimal scheduling"""
        if not MILP_AVAILABLE:
            return SchedulingResult(
                schedule_df=pd.DataFrame(),
                algorithm_used="milp",
                success=False,
                violations=[],
                optimization_score=0.0,
                execution_time=0.0,
                metadata={"error": "MILP not available"}
            )
        
        # For now, fallback to greedy until MILP is fully implemented
        return self._greedy_scheduling(shift_slots, start_time)
    
    def _greedy_scheduling(self, shift_slots: List[Dict[str, Any]], start_time,
                          base_schedule: pd.DataFrame = None) -> SchedulingResult:
        """Greedy heuristic with importance weighting and constraint awareness"""
        try:
            # Initialize schedule
            if base_schedule is not None and not base_schedule.empty:
                schedule_data = base_schedule.to_dict('records')
            else:
                schedule_data = []
                for slot in shift_slots:
                    schedule_data.append({
                        'slot_id': slot['slot_id'],
                        'date': slot['date'],
                        'shift_type': slot['shift_type'],
                        'role': slot['role'],
                        'employee_id': None,
                        'employee_name': ''
                    })
            
            # Track employee assignments and hours
            employee_hours = defaultdict(float)
            employee_days = defaultdict(set)
            
            # Fill unfilled slots using greedy approach
            for i, slot_data in enumerate(schedule_data):
                if slot_data['employee_id'] is not None:
                    continue  # Already assigned
                
                # Find best employee for this slot
                best_employee = self._find_best_employee_for_slot(
                    slot_data, employee_hours, employee_days
                )
                
                if best_employee:
                    schedule_data[i]['employee_id'] = best_employee.id
                    schedule_data[i]['employee_name'] = best_employee.name
                    
                    # Update tracking
                    shift_hours = self._get_shift_hours(slot_data['shift_type'])
                    employee_hours[best_employee.id] += shift_hours
                    employee_days[best_employee.id].add(slot_data['date'])
            
            schedule_df = pd.DataFrame(schedule_data)
            
            execution_time = (pd.Timestamp.now() - start_time).total_seconds()
            violations = self._validate_schedule(schedule_df)
            
            return SchedulingResult(
                schedule_df=schedule_df,
                algorithm_used="greedy",
                success=True,
                violations=violations,
                optimization_score=self._calculate_optimization_score(schedule_df),
                execution_time=execution_time,
                metadata={
                    "assignments_made": len(schedule_df[schedule_df['employee_id'].notna()]),
                    "unfilled_slots": len(schedule_df[schedule_df['employee_id'].isna()])
                }
            )
            
        except Exception as e:
            self.logger.error(f"Greedy scheduling failed: {e}")
            return SchedulingResult(
                schedule_df=pd.DataFrame(),
                algorithm_used="greedy",
                success=False,
                violations=[],
                optimization_score=0.0,
                execution_time=0.0,
                metadata={"error": str(e)}
            )
    
    def _find_best_employee_for_slot(self, slot_data: Dict[str, Any], 
                                   employee_hours: Dict[int, float],
                                   employee_days: Dict[int, set]) -> Optional[Employee]:
        """Find the best employee for a slot using importance weighting"""
        candidates = []
        
        for emp in self.employees:
            # Check basic eligibility
            if not self._can_work_slot_dict(emp, slot_data):
                continue
                
            # Check constraints
            shift_hours = self._get_shift_hours(slot_data['shift_type'])
            if employee_hours[emp.id] + shift_hours > emp.max_hours_per_week:
                continue
                
            # Calculate score based on importance and preferences
            importance = getattr(emp, 'importance', 1.0)
            if isinstance(importance, (int, float)):
                importance = float(importance)
            else:
                importance = 1.0
            
            # Preference bonus
            preference_bonus = 0
            if emp.preferred_shift == slot_data['shift_type'] or emp.preferred_shift == 'any':
                preference_bonus = 0.5
                
            # Workload balance (prefer less worked employees)
            max_hours = max([emp.max_hours_per_week for emp in self.employees])
            workload_factor = 1 - (employee_hours[emp.id] / max_hours) if max_hours > 0 else 1
            
            score = importance + preference_bonus + (workload_factor * 0.3)
            
            candidates.append((emp, score))
        
        if not candidates:
            return None
            
        # Sort by score (highest first) and return best
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]
    
    def _can_work_slot_dict(self, employee: Employee, slot_data: Dict[str, Any]) -> bool:
        """Check if employee can work a slot from dict data"""
        try:
            # Check role match
            if employee.role != slot_data['role']:
                return False
                
            # Check day availability
            slot_date = pd.to_datetime(slot_data['date'])
            day_name = slot_date.strftime('%a')
            if day_name not in employee.days_available:
                return False
                
            # Check employee unavailability (sick leave, etc.)
            if employee.id is not None:
                slot_date_str = slot_date.strftime('%Y-%m-%d')
                if not is_employee_available_on_date(employee.id, slot_date_str):
                    return False
                
            return True
        except:
            return False
    
    def _get_shift_hours(self, shift_type: str) -> float:
        """Get hours for a shift type"""
        shift_hours_map = {
            'day': 8.0,
            'evening': 6.0,
            'night': 8.0
        }
        return shift_hours_map.get(shift_type, 8.0)
    
    def _validate_schedule(self, schedule_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Validate schedule and return violations"""
        violations = []
        
        if schedule_df.empty:
            return [{"type": "error", "message": "Schedule is empty"}]
        
        # Check for unfilled slots
        unfilled = schedule_df[schedule_df['employee_id'].isna()]
        if not unfilled.empty:
            for _, row in unfilled.iterrows():
                violations.append({
                    "type": "warning",
                    "level": "moderate",
                    "message": f"Unfilled slot: {row['role']} on {row['date']} ({row['shift_type']})",
                    "slot_id": row.get('slot_id', ''),
                    "category": "unfilled"
                })
        
        # Check employee hour constraints
        if 'employee_id' in schedule_df.columns:
            emp_hours = defaultdict(float)
            for _, row in schedule_df[schedule_df['employee_id'].notna()].iterrows():
                shift_hours = self._get_shift_hours(row['shift_type'])
                emp_hours[row['employee_id']] += shift_hours
            
            for emp in self.employees:
                if emp_hours[emp.id] > emp.max_hours_per_week:
                    violations.append({
                        "type": "error",
                        "level": "critical",
                        "message": f"{emp.name} scheduled for {emp_hours[emp.id]:.1f}h (max: {emp.max_hours_per_week}h)",
                        "employee_id": emp.id,
                        "category": "overtime"
                    })
        
        return violations
    
    def _calculate_optimization_score(self, schedule_df: pd.DataFrame) -> float:
        """Calculate optimization score (0-100)"""
        if schedule_df.empty:
            return 0.0
        
        total_slots = len(schedule_df)
        filled_slots = len(schedule_df[schedule_df['employee_id'].notna()])
        
        # Base score from fill rate
        fill_rate = filled_slots / total_slots if total_slots > 0 else 0
        score = fill_rate * 70  # Up to 70 points for filling slots
        
        # Bonus points for preference matching and importance weighting
        preference_bonus = 0
        importance_bonus = 0
        
        for _, row in schedule_df[schedule_df['employee_id'].notna()].iterrows():
            emp = next((e for e in self.employees if e.id == row['employee_id']), None)
            if emp:
                # Preference bonus
                if emp.preferred_shift in [row['shift_type'], 'any']:
                    preference_bonus += 1
                
                # Importance bonus
                importance = getattr(emp, 'importance', 1.0)
                if isinstance(importance, (int, float)):
                    importance_bonus += float(importance)
        
        if filled_slots > 0:
            score += (preference_bonus / filled_slots) * 15  # Up to 15 points
            score += min((importance_bonus / filled_slots), 2.0) * 7.5  # Up to 15 points
        
        return min(score, 100.0)
    
    def _generate_empty_schedule(self, shift_slots: List[Dict[str, Any]]) -> pd.DataFrame:
        """Generate empty schedule template"""
        schedule_data = []
        for slot in shift_slots:
            schedule_data.append({
                'slot_id': slot['slot_id'],
                'date': slot['date'],
                'shift_type': slot['shift_type'],
                'role': slot['role'],
                'employee_id': None,
                'employee_name': ''
            })
        return pd.DataFrame(schedule_data)
    
    def _create_ai_prompt(self, shift_slots: List[Dict[str, Any]], 
                         employees_data: List[Dict[str, Any]], phase: str) -> str:
        """Create detailed AI prompt for scheduling"""
        prompt = f"""
Create an optimal work schedule considering employee importance scores and constraints.

EMPLOYEES (with importance scores):
{json.dumps(employees_data[:10], indent=2, default=str)}

SHIFT REQUIREMENTS:
{json.dumps(shift_slots[:20], indent=2, default=str)}

BUSINESS RULES:
- Employees cannot exceed their max_hours_per_week
- Employees can only work on their available days
- Employees CANNOT work during their unavailable_periods (sick leave, vacation, etc.)
- Higher importance employees should be prioritized for assignments
- Match employee roles to shift requirements
- Prefer employees' preferred shifts when possible

Please return a JSON array of assignments in this format:
[{{"slot_id": "slot_123", "employee_id": 1, "employee_name": "John Doe"}}, ...]

Only include assignments where you're confident about the match.
Focus on high-importance employees first.
"""
        return prompt
    
    def _parse_ai_response(self, content: str, shift_slots: List[Dict[str, Any]]) -> pd.DataFrame:
        """Parse AI response into schedule DataFrame"""
        try:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                assignments = json.loads(json_match.group())
            else:
                # Fallback parsing logic
                assignments = []
            
            # Create schedule DataFrame
            schedule_data = []
            assignment_dict = {a.get('slot_id'): a for a in assignments if isinstance(a, dict)}
            
            for slot in shift_slots:
                slot_id = slot['slot_id']
                assignment = assignment_dict.get(slot_id, {})
                
                schedule_data.append({
                    'slot_id': slot_id,
                    'date': slot['date'],
                    'shift_type': slot['shift_type'],
                    'role': slot['role'],
                    'employee_id': assignment.get('employee_id'),
                    'employee_name': assignment.get('employee_name', '')
                })
            
            return pd.DataFrame(schedule_data)
            
        except Exception as e:
            self.logger.error(f"Failed to parse AI response: {e}")
            return self._generate_empty_schedule(shift_slots)

def create_hybrid_scheduler(business_settings: Any, employees: List[Employee]) -> HybridScheduler:
    """Factory function to create hybrid scheduler"""
    return HybridScheduler(business_settings, employees)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Try multiple sources for API key
AI_API_KEY = None

# 1. Try Streamlit secrets first (for cloud deployment)
try:
    import streamlit as st
    AI_API_KEY = st.secrets.get("AI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
except:
    pass

# 2. Fall back to environment variables
if not AI_API_KEY:
    AI_API_KEY = os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY")

# Initialize OpenAI
openai_available = False
if AI_API_KEY:
    try:
        import openai
        openai.api_key = AI_API_KEY
        openai_available = True
        logger.debug("OpenAI initialized successfully")
    except Exception as init_err:
        logger.error("OpenAI initialization error: %s", init_err)
        openai_available = False
else:
    logger.warning("No OpenAI API key found")

# Database configuration
DB_PATH = "shift_maker.sqlite3"

def is_employee_available_on_date(employee_id: int, check_date: str) -> bool:
    """Check if an employee is available on a specific date (not marked as unavailable/sick)"""
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count FROM employee_unavailability 
            WHERE employee_id = ? AND start_date <= ? AND end_date >= ?
        """, (employee_id, check_date, check_date))
        result = cursor.fetchone()
        return result['count'] == 0  # Available if no unavailability records found
    except Exception as e:
        logger.error(f"Error checking employee availability: {e}")
        return True  # Default to available if there's an error
    finally:
        conn.close()

def get_employee_unavailability_for_period(employee_id: int, start_date: str, end_date: str) -> List[Dict[str, str]]:
    """Get all unavailability periods for an employee within a date range"""
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT start_date, end_date, reason FROM employee_unavailability 
            WHERE employee_id = ? AND (
                (start_date <= ? AND end_date >= ?) OR
                (start_date <= ? AND end_date >= ?) OR
                (start_date >= ? AND start_date <= ?)
            )
            ORDER BY start_date
        """, (employee_id, start_date, start_date, end_date, end_date, start_date, end_date))
        results = cursor.fetchall()
        return [{'start_date': row['start_date'], 'end_date': row['end_date'], 'reason': row['reason']} for row in results]
    except Exception as e:
        logger.error(f"Error getting employee unavailability: {e}")
        return []
    finally:
        conn.close()

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS business_settings (id INTEGER PRIMARY KEY CHECK (id = 1), json TEXT NOT NULL);")
    cur.execute("""CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        preferred_shift TEXT NOT NULL,
        days_available TEXT NOT NULL,
        max_hours_per_week REAL NOT NULL,
        min_hours_per_week REAL NOT NULL
    );""")
    cur.execute("""CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_key TEXT NOT NULL,
        slot_id TEXT NOT NULL,
        date TEXT NOT NULL,
        shift_type TEXT NOT NULL,
        role TEXT NOT NULL,
        employee_id INTEGER,
        employee_name TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(plan_key, slot_id)
    );""")
    cur.execute("""CREATE TABLE IF NOT EXISTS shift_customizations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        shift_type TEXT NOT NULL,
        role TEXT NOT NULL,
        count INTEGER NOT NULL,
        reason TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(date, shift_type, role)
    );""")
    conn.commit()
    conn.close()

def load_business_settings() -> BusinessSettings:
    """Load BusinessSettings from DB, or return defaults if none stored."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT json FROM business_settings WHERE id = 1"
        ).fetchone()
        if row:
            return BusinessSettings.from_row(row)
    except sqlite3.DatabaseError as db_err:
        logger.error("Failed to load business settings: %s", db_err)
        raise
    finally:
        conn.close()
    return BusinessSettings()

def save_business_settings(bs: BusinessSettings) -> None:
    """Persist BusinessSettings into DB (upsert)."""
    conn = get_conn()
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS business_settings (id INTEGER PRIMARY KEY, json TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO business_settings (id, json) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET json = excluded.json",
            (bs.to_json(),),
        )
        conn.commit()
    finally:
        conn.close()

def save_shift_customization(customization: ShiftCustomization) -> None:
    """Save shift customization to database."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Clear existing data and insert new requirements
        cur.execute("DELETE FROM shift_customizations")
        
        for req in customization.custom_requirements:
            cur.execute("""
                INSERT INTO shift_customizations 
                (date, shift_type, role, count, reason) 
                VALUES (?, ?, ?, ?, ?)
            """, (req.date, req.shift_type, req.role, req.required_count, req.reason))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Error saving shift customization: %s", e)

def load_shift_customization() -> ShiftCustomization:
    """Load shift customization from database."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        results = cur.execute("""
            SELECT date, shift_type, role, count, reason 
            FROM shift_customizations 
            ORDER BY id
        """).fetchall()
        conn.close()
        
        customization = ShiftCustomization()
        for row in results:
            customization.add_requirement(
                row[0],  # date
                row[1],  # shift_type
                row[2],  # role
                row[3],  # count
                row[4] if row[4] else ""  # reason
            )
        return customization
    except Exception as e:
        logger.error("Error loading shift customization: %s", e)
    
    # Return empty customization if nothing found
    return ShiftCustomization()

def build_shift_slots(bs: BusinessSettings, customization: Optional[ShiftCustomization] = None) -> List[ShiftSlot]:
    """Build shift slots for the planning period, respecting custom requirements and daily roles coverage."""
    slots = []
    
    # Get day names mapping
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    for i in range(bs.planning_days):
        day = bs.planning_start + timedelta(days=i)
        day_str = str(day)
        
        # Get the day of week name (Monday, Tuesday, etc.)
        day_of_week = day_names[day.weekday()]
        
        # Determine which role coverage to use
        if (hasattr(bs, 'daily_roles_coverage') and 
            bs.daily_roles_coverage and 
            day_of_week in bs.daily_roles_coverage and
            bs.daily_roles_coverage[day_of_week]):  # Check that day coverage is not empty
            # Use day-specific role coverage
            day_roles_coverage = bs.daily_roles_coverage[day_of_week]
            
            for role_name, requirements in day_roles_coverage.items():
                # Day shift requirements
                day_required = requirements.get("day", 0) or 0
                if customization:
                    custom_day = customization.get_requirement(day_str, "day", role_name)
                    if custom_day is not None:
                        day_required = custom_day
                
                for slot_num in range(day_required):
                    slots.append({
                        "date": day,
                        "shift_type": "day",
                        "role": role_name,
                        "slot_id": f"{day_str}_day_{role_name}_{slot_num}"
                    })
                
                # Evening shift requirements
                evening_required = requirements.get("evening", 0) or 0
                if customization:
                    custom_evening = customization.get_requirement(day_str, "evening", role_name)
                    if custom_evening is not None:
                        evening_required = custom_evening
                
                for slot_num in range(evening_required):
                    slots.append({
                        "date": day,
                        "shift_type": "evening",
                        "role": role_name,
                        "slot_id": f"{day_str}_evening_{role_name}_{slot_num}"
                    })
                
                # Night shift requirements
                night_required = requirements.get("night", 0) or 0
                if customization:
                    custom_night = customization.get_requirement(day_str, "night", role_name)
                    if custom_night is not None:
                        night_required = custom_night
                        
                for slot_num in range(night_required):
                    slots.append({
                        "date": day,
                        "shift_type": "night",
                        "role": role_name,
                        "slot_id": f"{day_str}_night_{role_name}_{slot_num}"
                    })
        else:
            # Fallback to general role coverage (original logic)
            for role in bs.roles_coverage:
                role_name = str(role["role"])
                
                # Day shift requirements
                day_required = role.get("day_required", 0) or 0
                if customization:
                    custom_day = customization.get_requirement(day_str, "day", role_name)
                    if custom_day is not None:
                        day_required = custom_day
                
                for slot_num in range(day_required):
                    slots.append({
                        "date": day,
                        "shift_type": "day",
                        "role": role_name,
                        "slot_id": f"{day_str}_day_{role_name}_{slot_num}"
                    })
                
                # Evening shift requirements (if available in role data)
                evening_required = role.get("evening_required", 0) or 0
                if customization:
                    custom_evening = customization.get_requirement(day_str, "evening", role_name)
                    if custom_evening is not None:
                        evening_required = custom_evening
                
                for slot_num in range(evening_required):
                    slots.append({
                        "date": day,
                        "shift_type": "evening",
                        "role": role_name,
                        "slot_id": f"{day_str}_evening_{role_name}_{slot_num}"
                    })
                
                # Night shift requirements
                night_required = role.get("night_required", 0) or 0
                if customization:
                    custom_night = customization.get_requirement(day_str, "night", role_name)
                    if custom_night is not None:
                        night_required = custom_night
                        
                for slot_num in range(night_required):
                    slots.append({
                        "date": day,
                        "shift_type": "night",
                        "role": role_name,
                        "slot_id": f"{day_str}_night_{role_name}_{slot_num}"
                    })
    
    return slots

def insert_employee(emp: EmployeeDict) -> None:
    """Insert a new employee into the database."""
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO employees (name, role, preferred_shift, days_available, max_hours_per_week, min_hours_per_week)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                emp["name"],
                emp["role"],
                emp["preferred_shift"],
                json.dumps(emp["days_available"]),
                emp["max_hours_per_week"],
                emp["min_hours_per_week"]
            )
        )
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Failed to add employee: {e}")
    finally:
        conn.close()

def get_all_employees() -> pd.DataFrame:
    conn = get_conn()
    try:
        df = pd.read_sql_query("SELECT * FROM employees ORDER BY id", conn)
        return df
    except Exception as e:
        logger.error(f"Failed to load employees: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def employees_to_df() -> pd.DataFrame:
    return get_all_employees()

def update_employee_row(emp_id: int, emp: EmployeeDict) -> None:
    """Update an existing employee in the database."""
    conn = get_conn()
    try:
        conn.execute(
            """
            UPDATE employees SET name=?, role=?, preferred_shift=?, days_available=?, max_hours_per_week=?, min_hours_per_week=? WHERE id=?
            """,
            (
                emp["name"],
                emp["role"],
                emp["preferred_shift"],
                json.dumps(emp["days_available"]),
                emp["max_hours_per_week"],
                emp["min_hours_per_week"],
                emp_id
            )
        )
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Failed to update employee: {e}")
    finally:
        conn.close()

def delete_employee_row(emp_id: int) -> None:
    """Delete an employee from the database."""
    conn = get_conn()
    try:
        conn.execute("DELETE FROM employees WHERE id=?", (emp_id,))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Failed to delete employee: {e}")
    finally:
        conn.close()

def save_schedule_to_db(sched_df: pd.DataFrame, bs: BusinessSettings) -> None:
    """Saves the schedule DataFrame to the database for the current planning window."""
    conn = get_conn()
    try:
        # Remove existing schedule for this window
        start = bs.planning_start.isoformat()
        end = (bs.planning_start + timedelta(days=bs.planning_days - 1)).isoformat()
        conn.execute("DELETE FROM schedules WHERE date BETWEEN ? AND ?", (start, end))
        # Insert new schedule
        plan_key = f"{start}_{end}"
        for _, row in sched_df.iterrows():
            conn.execute(
                "INSERT INTO schedules (plan_key, slot_id, date, shift_type, role, employee_id, employee_name) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    plan_key,
                    row.get("slot_id", f"{row['date']}_{row['shift_type']}_{row['role']}"),
                    row["date"],
                    row["shift_type"],
                    row["role"],
                    row["employee_id"],
                    row["employee_name"]
                )
            )
        conn.commit()
    finally:
        conn.close()

def load_schedule_from_db(bs: BusinessSettings) -> pd.DataFrame:
    """Loads the schedule for the current planning window from the database."""
    conn = get_conn()
    try:
        start = bs.planning_start.isoformat()
        end = (bs.planning_start + timedelta(days=bs.planning_days - 1)).isoformat()
        df = pd.read_sql_query(
            """
            SELECT * FROM schedules
            WHERE plan_key = ?
            ORDER BY date, shift_type, role
            """,
            conn,
            params=(f"{start}_{end}",)
        )
        return df
    finally:
        conn.close()

def analyze_employee_patterns(emp_data: pd.DataFrame) -> Dict[str, Any]:
    """Analyze employee patterns and constraints for better scheduling."""
    patterns = {
        'availability_analysis': {},
        'workload_distribution': {},
        'preference_patterns': {}
    }
    
    for _, emp in emp_data.iterrows():
        emp_id = emp['id']
        
        # Parse availability
        try:
            available_days = json.loads(emp['days_available']) if isinstance(emp['days_available'], str) else emp['days_available']
        except:
            available_days = []
        
        patterns['availability_analysis'][emp_id] = {
            'available_days': available_days,
            'availability_score': len(available_days) / 7,  # 0-1 scale
            'max_hours': emp['max_hours_per_week'],
            'min_hours': emp['min_hours_per_week'],
            'flexibility': 'high' if len(available_days) >= 5 else 'medium' if len(available_days) >= 3 else 'low'
        }
        
        patterns['preference_patterns'][emp_id] = {
            'preferred_shift': emp['preferred_shift'],
            'role': emp['role']
        }
    
    return patterns

def calculate_schedule_score(schedule_df: pd.DataFrame, emp_data: pd.DataFrame, patterns: Dict[str, Any]) -> Dict[str, float]:
    """Calculate comprehensive score for a schedule."""
    if schedule_df.empty:
        return {'total_score': 0, 'preference_score': 0, 'fairness_score': 0}
    
    scores = {
        'preference_score': 0,
        'fairness_score': 0,
        'coverage_score': 0
    }
    
    # Calculate preference satisfaction
    pref_matches = 0
    total_shifts = len(schedule_df)
    
    for _, shift in schedule_df.iterrows():
        emp_id = shift['employee_id']
        if emp_id in patterns['preference_patterns']:
            emp_pref = patterns['preference_patterns'][emp_id]['preferred_shift']
            if emp_pref == 'any' or emp_pref == shift['shift_type']:
                pref_matches += 1
    
    scores['preference_score'] = pref_matches / total_shifts if total_shifts > 0 else 0

    # Calculate fairness (hour distribution)
    emp_hours = {}
    for _, shift in schedule_df.iterrows():
        emp_id = shift['employee_id']
        hours = shift.get('hours', 8)
        emp_hours[emp_id] = emp_hours.get(emp_id, 0) + hours
    
    if emp_hours:
        hour_values = list(emp_hours.values())
        fairness = 1 - (max(hour_values) - min(hour_values)) / max(hour_values) if max(hour_values) > 0 else 1
        scores['fairness_score'] = fairness
    else:
        scores['fairness_score'] = 1.0
    
    # Calculate coverage score (all required shifts covered)
    scores['coverage_score'] = 1.0  # Assume perfect coverage for now
    
    # Calculate total weighted score (removed cost_score, rebalanced weights)
    weights = {'preference_score': 0.4, 'fairness_score': 0.4, 'coverage_score': 0.2}
    scores['total_score'] = sum(scores[key] * weights[key] for key in weights)
    
    return scores

def generate_schedule_with_ai(emp_data: pd.DataFrame, shift_slots: List[Dict[str, Union[str, date]]], bs: Any, **kwargs) -> pd.DataFrame:
    """Generate a comprehensive AI-powered schedule with advanced customization options."""
    # Input validation
    if emp_data.empty or not all(col in emp_data.columns for col in ["id", "name", "max_hours_per_week"]):
        raise ValueError("Invalid employee data provided.")
    if not shift_slots or not all("date" in slot and "role" in slot for slot in shift_slots):
        raise ValueError("Invalid shift slots provided.")

    # If OpenAI is not available, return empty DataFrame
    if not openai_available:
        logger.warning("OpenAI not available, returning empty schedule")
        return pd.DataFrame()

    try:
        # Extract advanced parameters
        optimization_focus = kwargs.get("optimization_focus", "Balanced")
        generation_mode = kwargs.get("generation_mode", "Standard AI")
        constraint_level = kwargs.get("constraint_level", "Standard")
        use_advanced_rules = kwargs.get("use_advanced_rules", True)
        role_priorities = kwargs.get("role_priorities", {})
        day_specific_rules = kwargs.get("day_specific_rules", True)
        
        # Analyze employee patterns and constraints
        patterns = analyze_employee_patterns(emp_data)
        
        # Enhanced analysis for advanced mode
        if use_advanced_rules:
            patterns = enhance_pattern_analysis(patterns, emp_data, bs)
        
        logger.debug("Advanced AI Generation Parameters:")
        logger.debug("Optimization Focus: %s", optimization_focus)
        logger.debug("Generation Mode: %s", generation_mode)
        logger.debug("Constraint Level: %s", constraint_level)
        logger.debug("Use Advanced Rules: %s", use_advanced_rules)
        
        # Create optimized prompt for AI with advanced parameters
        emp_summary = []
        for _, emp in emp_data.iterrows():
            try:
                avail_days = json.loads(emp['days_available']) if isinstance(emp['days_available'], str) else emp['days_available']
            except:
                avail_days = []
            
            emp_summary.append({
                'id': emp['id'],
                'name': emp['name'],
                'role': emp['role'],
                'pref_shift': emp['preferred_shift'],
                'avail_days': avail_days,
                'max_hrs': emp['max_hours_per_week']
            })
        
        # Summarize shift requirements with advanced rules
        shift_summary = create_advanced_shift_summary(shift_slots, bs, day_specific_rules)
        
        # Create optimization-specific prompt
        optimization_prompt = create_optimization_prompt(optimization_focus, constraint_level)
        
        # Limit employee data to prevent token overflow (sample key employees from each role)
        role_samples = {}
        for _, emp in emp_data.iterrows():
            role = emp['role']
            if role not in role_samples:
                role_samples[role] = []
            if len(role_samples[role]) < 3:  # Max 3 employees per role for AI prompt
                role_samples[role].append({
                    'id': emp['id'],
                    'name': emp['name'][:15],  # Truncate name to save tokens
                    'role': role,
                    'pref_shift': emp['preferred_shift'],
                    'max_hrs': emp['max_hours_per_week']
                })
        
        # Flatten samples
        limited_employees = []
        for role_list in role_samples.values():
            limited_employees.extend(role_list)
        
        prompt = f"""Generate {generation_mode.lower()} schedule with {optimization_focus.lower()} optimization.

EMPLOYEES (Sample of {len(limited_employees)} from {len(emp_data)} total):
{json.dumps(limited_employees, default=str)}  

SHIFTS REQUIRED:
{json.dumps(shift_summary[:5], default=str)}  

OPTIMIZATION: {optimization_prompt}

CONSTRAINTS: {constraint_level} level
- Day/Night shifts: {getattr(bs, 'day_shift_length', 8)}h each
- Period: {getattr(bs, 'planning_start', 'N/A')} ({getattr(bs, 'planning_days', 7)} days)

OUTPUT: CSV only
date,role,shift_type,employee_id
2025-09-23,Manager,day,1

Generate optimal schedule for ALL {len(emp_data)} employees."""

        # Call OpenAI API with optimized prompt
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"Expert {generation_mode.lower()} workforce scheduling AI. Optimize for {optimization_focus.lower()}. Return only CSV data."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.1 if constraint_level == "Strict" else 0.3
        )

        content = response["choices"][0]["message"]["content"] if response.get("choices") else ""
        logger.debug("Advanced AI Response Content: %s", content)

        # Parse and enhance the response
        schedule_df = parse_ai_schedule_response(content, emp_data, shift_slots, bs)
        
        # Apply advanced post-processing
        if use_advanced_rules and not schedule_df.empty:
            schedule_df = apply_advanced_processing(schedule_df, emp_data, patterns, bs, kwargs)
        
        # Validate and score the schedule
        if not schedule_df.empty:
            scores = calculate_advanced_schedule_score(schedule_df, emp_data, patterns, optimization_focus)
            logger.info("Advanced schedule generated with scores: %s", scores)
            
            # Add enhanced metadata
            schedule_df.attrs['scores'] = scores
            schedule_df.attrs['patterns'] = patterns
            schedule_df.attrs['generation_params'] = kwargs
            schedule_df.attrs['optimization_focus'] = optimization_focus
        
        return schedule_df

    except Exception as e:
        logger.error("Error in advanced generate_schedule_with_ai: %s", e)
        return pd.DataFrame()

def parse_ai_schedule_response(content: str, emp_data: pd.DataFrame, shift_slots: List[Dict], bs: Any) -> pd.DataFrame:
    """Parse AI response and enhance with additional data."""
    import io
    
    try:
        # Clean the content - remove any non-CSV text
        lines = content.strip().split('\n')
        csv_lines = []
        header_found = False
        
        for line in lines:
            if 'date,role,shift_type,employee_id' in line or header_found:
                csv_lines.append(line)
                header_found = True
            elif header_found and ',' in line and not line.startswith('#'):
                csv_lines.append(line)
        
        if not csv_lines:
            logger.error("No valid CSV content found in AI response")
            return pd.DataFrame()
        
        # Parse as CSV
        csv_content = '\n'.join(csv_lines)
        df = pd.read_csv(io.StringIO(csv_content))
        
        # Validate required columns
        required_cols = ['date', 'role', 'shift_type', 'employee_id']
        if not all(col in df.columns for col in required_cols):
            logger.error("Missing required columns in AI response")
            return pd.DataFrame()
        
        # Enhance with additional data
        enhanced_rows = []
        
        for _, row in df.iterrows():
            try:
                emp_id = int(row['employee_id'])
                employee = emp_data[emp_data['id'] == emp_id]
                
                if employee.empty:
                    logger.warning("Employee ID %s not found", emp_id)
                    continue
                
                emp_row = employee.iloc[0]
                
                # Find matching slot
                matching_slot = None
                for slot in shift_slots:
                    if (str(slot['date']) == str(row['date']) and 
                        slot['role'] == row['role'] and 
                        slot['shift_type'] == row['shift_type']):
                        matching_slot = slot
                        break
                
                # Calculate hours based on shift type
                if row['shift_type'] == 'day':
                    hours = getattr(bs, 'day_shift_length', 8)
                elif row['shift_type'] == 'night':
                    hours = getattr(bs, 'night_shift_length', 8)
                else:
                    hours = 8  # Default
                
                enhanced_row = {
                    'date': row['date'],
                    'role': row['role'],
                    'shift_type': row['shift_type'],
                    'employee_id': emp_id,
                    'employee_name': emp_row['name'],
                    'hours': hours,
                    'slot_id': matching_slot['slot_id'] if matching_slot and 'slot_id' in matching_slot else f"{row['date']}_{row['role']}_{row['shift_type']}",
                    'preference_match': emp_row['preferred_shift'] in ['any', row['shift_type']]
                }
                
                enhanced_rows.append(enhanced_row)
                
            except Exception as row_error:
                logger.error("Error processing row %s: %s", row, row_error)
                continue
        
        if enhanced_rows:
            result_df = pd.DataFrame(enhanced_rows)
            logger.info("Successfully parsed and enhanced %d schedule entries", len(result_df))
            return result_df
        else:
            logger.error("No valid schedule entries after enhancement")
            return pd.DataFrame()
            
    except Exception as parse_err:
        logger.error("Failed to parse AI response: %s", parse_err)
        return pd.DataFrame()


def modify_schedule_with_ai(schedule_df: pd.DataFrame, modification_request: str, emp_data: pd.DataFrame, shift_slots: List[Dict], bs: Any) -> pd.DataFrame:
    """Process natural language schedule modification requests using AI."""
    if schedule_df.empty or not openai_available:
        logger.warning("Cannot modify schedule - empty schedule or AI not available")
        return schedule_df
    
    try:
        # Analyze current schedule
        current_scores = calculate_schedule_score(schedule_df, emp_data, analyze_employee_patterns(emp_data))
        
        # Create modification prompt
        prompt = f"""SCHEDULE MODIFICATION REQUEST: {modification_request}

CURRENT SCHEDULE:
{schedule_df.to_dict('records')}

AVAILABLE EMPLOYEES:
{emp_data.to_dict('records')}

AVAILABLE SHIFT SLOTS:
{shift_slots}

CURRENT SCHEDULE SCORES:
{current_scores}

MODIFICATION INSTRUCTIONS:
1. Understand the user's request and identify what needs to change
2. Preserve as much of the existing schedule as possible
3. Only make necessary changes to fulfill the request
4. Ensure all constraints are still met after modification
5. Maintain or improve schedule quality scores

CONSTRAINTS TO MAINTAIN:
- Employee availability (days_available)
- Maximum/minimum hours per week
- Role requirements and skills
- Shift type preferences
- Business rules and coverage

MODIFICATION TYPES TO HANDLE:
- Employee swaps ("swap John and Mary on Monday")
- Time changes ("move Sarah from day to night shift")
- Coverage adjustments ("add another barista on Friday")
- Employee requests ("give Alice Wednesday off")
- Emergency changes ("replace Tom who is sick")

OUTPUT: Return the COMPLETE modified schedule as CSV with columns: date,role,shift_type,employee_id
Include ALL shifts (modified and unchanged). Do not return partial schedules.

EXAMPLE OUTPUT:
date,role,shift_type,employee_id
2025-09-23,Barista,day,1
2025-09-23,Cook,night,2
"""

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": """You are an expert schedule modification assistant. 
                You understand natural language requests and can intelligently modify existing schedules 
                while maintaining constraints and quality. Always return complete schedules."""},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2500,
            temperature=0.1
        )
        
        content = response["choices"][0]["message"]["content"] if response.get("choices") else ""
        logger.debug("Schedule modification AI response: %s", content)
        
        # Parse the modified schedule
        modified_schedule = parse_ai_schedule_response(content, emp_data, shift_slots, bs)
        
        if not modified_schedule.empty:
            # Calculate new scores
            new_scores = calculate_schedule_score(modified_schedule, emp_data, analyze_employee_patterns(emp_data))
            modified_schedule.attrs['scores'] = new_scores
            modified_schedule.attrs['modification_request'] = modification_request
            modified_schedule.attrs['previous_scores'] = current_scores
            
            logger.info("Schedule modified. Previous scores: %s, New scores: %s", current_scores, new_scores)
            return modified_schedule
        else:
            logger.error("Failed to parse modified schedule")
            return schedule_df
            
    except Exception as e:
        logger.error("Error modifying schedule: %s", e)
        return schedule_df

def suggest_schedule_improvements(schedule_df: pd.DataFrame, emp_data: pd.DataFrame, shift_slots: List[Dict], bs: Any) -> List[str]:
    """Analyze schedule and suggest improvements."""
    if schedule_df.empty:
        return ["No schedule to analyze"]
    
    suggestions = []
    patterns = analyze_employee_patterns(emp_data)
    scores = calculate_schedule_score(schedule_df, emp_data, patterns)
    
    # Analyze preference satisfaction
    if scores['preference_score'] < 0.8:
        pref_mismatches = []
        for _, shift in schedule_df.iterrows():
            emp_id = shift['employee_id']
            if emp_id in patterns['preference_patterns']:
                emp_pref = patterns['preference_patterns'][emp_id]['preferred_shift']
                if emp_pref != 'any' and emp_pref != shift['shift_type']:
                    emp_name = shift['employee_name']
                    pref_mismatches.append(f"{emp_name} prefers {emp_pref} but assigned {shift['shift_type']} on {shift['date']}")
        
        if pref_mismatches:
            suggestions.append(f"PREFERENCE IMPROVEMENTS (Score: {scores['preference_score']:.2f}):")
            suggestions.extend(pref_mismatches[:3])  # Show top 3

    # Analyze fairness
    if scores['fairness_score'] < 0.8:
        emp_hours = {}
        for _, shift in schedule_df.iterrows():
            emp_id = shift['employee_id']
            emp_name = shift['employee_name']
            hours = shift.get('hours', 8)
            if emp_name not in emp_hours:
                emp_hours[emp_name] = 0
            emp_hours[emp_name] += hours
        
        if emp_hours:
            max_hours = max(emp_hours.values())
            min_hours = min(emp_hours.values())
            difference = max_hours - min_hours
            
            if difference > 16:  # More than 2 shifts difference
                suggestions.append(f"FAIRNESS IMPROVEMENT (Score: {scores['fairness_score']:.2f}):")
                suggestions.append(f"Hour distribution range: {min_hours}-{max_hours} hours (difference: {difference})")
                suggestions.append("Consider redistributing shifts more evenly")
    
    # Check for availability violations
    availability_violations = []
    for _, shift in schedule_df.iterrows():
        emp_id = shift['employee_id']
        if emp_id in patterns['availability_analysis']:
            available_days = patterns['availability_analysis'][emp_id]['available_days']
            shift_day = pd.to_datetime(shift['date']).strftime('%a')  # Get day abbreviation
            if shift_day not in available_days:
                availability_violations.append(f"{shift['employee_name']} scheduled on {shift['date']} but not available on {shift_day}")
    
    if availability_violations:
        suggestions.append("AVAILABILITY VIOLATIONS:")
        suggestions.extend(availability_violations)
    
    # Overall score assessment
    total_score = scores['total_score']
    if total_score > 0.85:
        suggestions.insert(0, f"✅ EXCELLENT SCHEDULE (Overall Score: {total_score:.2f})")
    elif total_score > 0.7:
        suggestions.insert(0, f"✅ GOOD SCHEDULE (Overall Score: {total_score:.2f})")
    elif total_score > 0.5:
        suggestions.insert(0, f"⚠️ FAIR SCHEDULE (Overall Score: {total_score:.2f}) - Some improvements possible")
    else:
        suggestions.insert(0, f"❌ POOR SCHEDULE (Overall Score: {total_score:.2f}) - Significant improvements needed")
    
    return suggestions if suggestions else ["Schedule appears optimal with current constraints"]

def swap_employees_in_schedule(schedule_df: pd.DataFrame, emp1_id: int, emp2_id: int, date_filter: str = None) -> pd.DataFrame:
    """Swap two employees in the schedule, optionally filtered by date."""
    if schedule_df.empty:
        return schedule_df
    
    modified_schedule = schedule_df.copy()
    
    # Find shifts for both employees
    emp1_shifts = modified_schedule[modified_schedule['employee_id'] == emp1_id]
    emp2_shifts = modified_schedule[modified_schedule['employee_id'] == emp2_id]
    
    if date_filter:
        emp1_shifts = emp1_shifts[emp1_shifts['date'] == date_filter]
        emp2_shifts = emp2_shifts[emp2_shifts['date'] == date_filter]
    
    if emp1_shifts.empty or emp2_shifts.empty:
        logger.warning("Cannot swap - one or both employees have no shifts on specified date(s)")
        return schedule_df
    
    # Perform the swap
    for idx1 in emp1_shifts.index:
        for idx2 in emp2_shifts.index:
            if (emp1_shifts.loc[idx1, 'date'] == emp2_shifts.loc[idx2, 'date'] and
                emp1_shifts.loc[idx1, 'shift_type'] == emp2_shifts.loc[idx2, 'shift_type']):
                
                # Swap employee IDs and names
                modified_schedule.loc[idx1, 'employee_id'] = emp2_id
                modified_schedule.loc[idx1, 'employee_name'] = emp2_shifts.loc[idx2, 'employee_name']
                modified_schedule.loc[idx2, 'employee_id'] = emp1_id
                modified_schedule.loc[idx2, 'employee_name'] = emp1_shifts.loc[idx1, 'employee_name']
    
    logger.info("Successfully swapped employees %d and %d", emp1_id, emp2_id)
    return modified_schedule

def calculate_overtime_and_compliance(schedule_df: pd.DataFrame, emp_data: pd.DataFrame, labor_rules: Dict[str, Any] = None) -> Dict[str, Any]:
    """Calculate overtime, labor law compliance, and related metrics."""
    if labor_rules is None:
        labor_rules = {
            'max_consecutive_days': 6,
            'min_rest_hours': 12,
            'max_daily_hours': 12,
            'overtime_threshold': 40,
            'overtime_multiplier': 1.5,
            'weekend_multiplier': 1.2,
            'night_shift_multiplier': 1.1
        }
    
    compliance_report = {
        'violations': [],
        'overtime_hours': {},
        'total_regular_hours': 0,
        'total_overtime_hours': 0,
        'compliance_score': 1.0
    }
    
    if schedule_df.empty:
        return compliance_report
    
    # Group by employee
    for emp_id in schedule_df['employee_id'].unique():
        emp_shifts = schedule_df[schedule_df['employee_id'] == emp_id].sort_values('date')
        emp_info = emp_data[emp_data['id'] == emp_id].iloc[0]
        emp_name = emp_info['name']
        
        # Calculate weekly hours and overtime
        emp_shifts['week'] = pd.to_datetime(emp_shifts['date']).dt.isocalendar().week
        
        for week in emp_shifts['week'].unique():
            week_shifts = emp_shifts[emp_shifts['week'] == week]
            total_week_hours = week_shifts['hours'].sum()
            
            if total_week_hours > labor_rules['overtime_threshold']:
                overtime_hours = total_week_hours - labor_rules['overtime_threshold']
                regular_hours = labor_rules['overtime_threshold']
                
                compliance_report['overtime_hours'][f"{emp_name}_week_{week}"] = {
                    'regular_hours': regular_hours,
                    'overtime_hours': overtime_hours
                }
                
                compliance_report['total_overtime_hours'] += overtime_hours
            else:
                compliance_report['total_regular_hours'] += total_week_hours
        
        # Check consecutive days
        emp_shifts['date_dt'] = pd.to_datetime(emp_shifts['date'])
        emp_shifts = emp_shifts.sort_values('date_dt')
        
        consecutive_days = 1
        max_consecutive = 1
        
        for i in range(1, len(emp_shifts)):
            if (emp_shifts.iloc[i]['date_dt'] - emp_shifts.iloc[i-1]['date_dt']).days == 1:
                consecutive_days += 1
                max_consecutive = max(max_consecutive, consecutive_days)
            else:
                consecutive_days = 1
        
        if max_consecutive > labor_rules['max_consecutive_days']:
            compliance_report['violations'].append(
                f"{emp_name} works {max_consecutive} consecutive days (max allowed: {labor_rules['max_consecutive_days']})"
            )
            compliance_report['compliance_score'] -= 0.1
        
        # Check daily hour limits
        for _, shift in emp_shifts.iterrows():
            daily_hours = shift['hours']
            if daily_hours > labor_rules['max_daily_hours']:
                compliance_report['violations'].append(
                    f"{emp_name} scheduled {daily_hours} hours on {shift['date']} (max: {labor_rules['max_daily_hours']})"
                )
                compliance_report['compliance_score'] -= 0.05
        
        # Check rest periods between shifts
        for i in range(1, len(emp_shifts)):
            prev_shift = emp_shifts.iloc[i-1]
            curr_shift = emp_shifts.iloc[i]
            
            # Calculate time between shifts (simplified - assumes shifts don't span midnight)
            time_between = (pd.to_datetime(curr_shift['date']) - pd.to_datetime(prev_shift['date'])).days * 24
            
            if time_between < labor_rules['min_rest_hours'] and time_between > 0:
                compliance_report['violations'].append(
                    f"{emp_name} has only {time_between} hours rest between {prev_shift['date']} and {curr_shift['date']} (min: {labor_rules['min_rest_hours']})"
                )
                compliance_report['compliance_score'] -= 0.1
    
    compliance_report['compliance_score'] = max(0, compliance_report['compliance_score'])
    return compliance_report

def apply_advanced_constraints(emp_data: pd.DataFrame, shift_slots: List[Dict], constraints: Dict[str, Any] = None) -> List[Dict]:
    """Apply advanced business constraints to shift slots."""
    if constraints is None:
        constraints = {
            'min_staff_per_shift': 1,
            'max_staff_per_shift': 5,
            'required_skills': {},
            'restricted_combinations': [],
            'preferred_pairings': [],
            'blackout_dates': [],
            'mandatory_coverage': {}
        }
    
    enhanced_slots = []
    
    for slot in shift_slots:
        enhanced_slot = slot.copy()
        
        # Add skill requirements
        role = slot['role']
        if role in constraints.get('required_skills', {}):
            enhanced_slot['required_skills'] = constraints['required_skills'][role]
        
        # Add staffing requirements
        enhanced_slot['min_staff'] = constraints.get('min_staff_per_shift', 1)
        enhanced_slot['max_staff'] = constraints.get('max_staff_per_shift', 5)
        
        # Check blackout dates
        slot_date = str(slot['date'])
        if slot_date in constraints.get('blackout_dates', []):
            enhanced_slot['blackout'] = True
            enhanced_slot['reason'] = 'Blackout date'
        
        # Add priority based on mandatory coverage
        coverage_key = f"{slot['role']}_{slot['shift_type']}"
        if coverage_key in constraints.get('mandatory_coverage', {}):
            enhanced_slot['priority'] = 'high'
            enhanced_slot['mandatory'] = True
        
        enhanced_slots.append(enhanced_slot)
    
    return enhanced_slots

def generate_schedule_alternatives(emp_data: pd.DataFrame, shift_slots: List[Dict], bs: Any, num_alternatives: int = 3) -> List[Dict[str, Any]]:
    """Generate multiple schedule alternatives with different optimization focuses."""
    alternatives = []
    
    # Alternative 1: Preference-optimized
    try:
        pref_schedule = generate_schedule_with_ai(emp_data, shift_slots, bs, optimization_focus="Employee Satisfaction")
        if not pref_schedule.empty:
            patterns = analyze_employee_patterns(emp_data)
            scores = calculate_schedule_score(pref_schedule, emp_data, patterns)
            compliance = calculate_overtime_and_compliance(pref_schedule, emp_data)
            
            alternatives.append({
                'name': 'Preference Optimized',
                'schedule': pref_schedule,
                'scores': scores,
                'compliance': compliance,
                'focus': 'Maximizes employee shift preferences and satisfaction'
            })
    except Exception as e:
        logger.error("Failed to generate preference-optimized alternative: %s", e)
    
    # Alternative 2: Fairness-optimized
    try:
        fairness_schedule = generate_schedule_with_ai(emp_data, shift_slots, bs, optimization_focus="Fair Distribution")
        if not fairness_schedule.empty:
            patterns = analyze_employee_patterns(emp_data)
            scores = calculate_schedule_score(fairness_schedule, emp_data, patterns)
            compliance = calculate_overtime_and_compliance(fairness_schedule, emp_data)
            
            alternatives.append({
                'name': 'Fairness Optimized',
                'schedule': fairness_schedule,
                'scores': scores,
                'compliance': compliance,
                'focus': 'Ensures fair distribution of shifts and hours across all employees'
            })
    except Exception as e:
        logger.error("Failed to generate fairness-optimized alternative: %s", e)
    
    # Alternative 3: Balanced approach
    try:
        balanced_schedule = generate_schedule_with_ai(emp_data, shift_slots, bs, optimization_focus="Balanced")
        if not balanced_schedule.empty:
            patterns = analyze_employee_patterns(emp_data)
            scores = calculate_schedule_score(balanced_schedule, emp_data, patterns)
            compliance = calculate_overtime_and_compliance(balanced_schedule, emp_data)
            
            alternatives.append({
                'name': 'Balanced',
                'schedule': balanced_schedule,
                'scores': scores,
                'compliance': compliance,
                'focus': 'Balances employee preferences, fairness, and coverage quality'
            })
    except Exception as e:
        logger.error("Failed to generate balanced alternative: %s", e)
    
    # Sort alternatives by total score
    alternatives.sort(key=lambda x: x['scores']['total_score'], reverse=True)
    
    return alternatives[:num_alternatives]


def validate_schedule_constraints(schedule_df: pd.DataFrame, emp_data: pd.DataFrame, shift_slots: List[Dict]) -> Dict[str, List[str]]:
    """Validate schedule against all constraints and return violations."""
    violations = {
        'availability': [],
        'hours': [],
        'coverage': [],
        'conflicts': []
    }
    
    if schedule_df.empty:
        violations['coverage'].append("Schedule is empty")
        return violations
    
    patterns = analyze_employee_patterns(emp_data)
    
    # Check availability violations
    for _, shift in schedule_df.iterrows():
        emp_id = shift['employee_id']
        if emp_id in patterns['availability_analysis']:
            available_days = patterns['availability_analysis'][emp_id]['available_days']
            shift_day = pd.to_datetime(shift['date']).strftime('%a')
            if shift_day not in available_days:
                violations['availability'].append(
                    f"{shift['employee_name']} scheduled on {shift['date']} ({shift_day}) but only available: {', '.join(available_days)}"
                )
    
    # Check hour constraints
    emp_hours = {}
    for _, shift in schedule_df.iterrows():
        emp_id = shift['employee_id']
        hours = shift.get('hours', 8)
        emp_hours[emp_id] = emp_hours.get(emp_id, 0) + hours
    
    for emp_id, total_hours in emp_hours.items():
        emp_row = emp_data[emp_data['id'] == emp_id]
        if not emp_row.empty:
            emp_info = emp_row.iloc[0]
            max_hours = emp_info['max_hours_per_week']
            min_hours = emp_info['min_hours_per_week']
            
            if total_hours > max_hours:
                violations['hours'].append(
                    f"{emp_info['name']} scheduled {total_hours} hours (exceeds max: {max_hours})"
                )
            elif total_hours < min_hours:
                violations['hours'].append(
                    f"{emp_info['name']} scheduled {total_hours} hours (below min: {min_hours})"
                )
    
    # Check coverage requirements
    required_slots = {}
    for slot in shift_slots:
        key = f"{slot['date']}_{slot['role']}_{slot['shift_type']}"
        required_slots[key] = slot
    
    scheduled_slots = set()
    for _, shift in schedule_df.iterrows():
        key = f"{shift['date']}_{shift['role']}_{shift['shift_type']}"
        scheduled_slots.add(key)
    
    missing_coverage = set(required_slots.keys()) - scheduled_slots
    for missing in missing_coverage:
        slot_info = required_slots[missing]
        violations['coverage'].append(
            f"Missing coverage: {slot_info['role']} {slot_info['shift_type']} shift on {slot_info['date']}"
        )
    
    # Check for scheduling conflicts (same employee, same time)
    emp_shifts = {}
    for _, shift in schedule_df.iterrows():
        emp_id = shift['employee_id']
        date_shift = f"{shift['date']}_{shift['shift_type']}"
        
        if emp_id not in emp_shifts:
            emp_shifts[emp_id] = []
        
        if date_shift in emp_shifts[emp_id]:
            emp_name = shift['employee_name']
            violations['conflicts'].append(
                f"{emp_name} has multiple {shift['shift_type']} shifts on {shift['date']}"
            )
        else:
            emp_shifts[emp_id].append(date_shift)
    
    return violations


if __name__ == "__main__":
    print("shift_plus_core.py loaded successfully")
    print("Testing basic functionality...")
    
    # Test database initialization
    init_db()
    print("✓ Database initialized")
    
    # Test BusinessSettings loading
    bs = load_business_settings()
    print(f"✓ BusinessSettings loaded: {type(bs)}")
    
    # Test shift slots building
    if bs.roles_coverage:
        slots = build_shift_slots(bs)
        print(f"✓ Built {len(slots)} shift slots")
    else:
        print("⚠ No roles_coverage configured, cannot build shift slots")

# Enhanced AI Supporting Functions

def enhance_pattern_analysis(patterns: Dict, emp_data: pd.DataFrame, bs: Any) -> Dict:
    """Enhance pattern analysis with advanced business rules."""
    enhanced_patterns = patterns.copy()
    
    # Add role-specific patterns
    role_patterns = {}
    for _, emp in emp_data.iterrows():
        role = emp['role']
        if role not in role_patterns:
            role_patterns[role] = {
                'count': 0,
                'avg_hours': 0,
                'skills': set()
            }
        
        role_patterns[role]['count'] += 1
        role_patterns[role]['avg_hours'] += emp['max_hours_per_week']
        
        # Add skills if available
        if hasattr(emp, 'skills') and emp['skills']:
            try:
                skills = json.loads(emp['skills']) if isinstance(emp['skills'], str) else emp['skills']
                role_patterns[role]['skills'].update(skills)
            except:
                pass
    
    # Calculate averages
    for role in role_patterns:
        if role_patterns[role]['count'] > 0:
            role_patterns[role]['avg_hours'] /= role_patterns[role]['count']
            role_patterns[role]['skills'] = list(role_patterns[role]['skills'])
    
    enhanced_patterns['role_patterns'] = role_patterns
    
    # Add business-specific patterns
    if hasattr(bs, 'role_settings') and isinstance(bs.role_settings, dict):
        enhanced_patterns['business_rules'] = {
            'role_priorities': {role: getattr(rs, 'priority_level', 1) 
                             for role, rs in bs.role_settings.items()},
            'experience_weights': {role: getattr(rs, 'experience_weight', 1.0) 
                                 for role, rs in bs.role_settings.items()}
        }
    else:
        # Fallback for basic business settings without role_settings
        enhanced_patterns['business_rules'] = {
            'role_priorities': {},
            'experience_weights': {}
        }
    
    return enhanced_patterns

def create_advanced_shift_summary(shift_slots: List[Dict], bs: Any, day_specific: bool = True) -> List[Dict]:
    """Create enhanced shift summary with advanced business rules."""
    shift_summary = []
    dates_seen = set()
    
    for slot in shift_slots:
        date_str = str(slot['date'])
        if date_str not in dates_seen:
            dates_seen.add(date_str)
            
            # Get day-specific rules
            day_info = {
                'date': date_str,
                'roles_needed': [s['role'] for s in shift_slots if str(s['date']) == date_str]
            }
            
            if day_specific and hasattr(bs, 'day_settings') and isinstance(bs.day_settings, dict):
                # Add day-specific multipliers and rules
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date() if isinstance(date_str, str) else date_str
                day_name = date_obj.strftime('%A')
                
                if day_name in bs.day_settings:
                    day_setting = bs.day_settings[day_name]
                    day_info['role_multipliers'] = getattr(day_setting, 'role_multipliers', {})
                    day_info['rush_hours'] = getattr(day_setting, 'rush_hours', [])
                    day_info['special_requirements'] = getattr(day_setting, 'special_requirements', [])
            
            shift_summary.append(day_info)
    
    return shift_summary

def create_optimization_prompt(optimization_focus: str, constraint_level: str) -> str:
    """Create optimization-specific prompt based on focus and constraint level."""
    prompts = {
        "Employee Satisfaction": "Maximize employee preferences and work-life balance. Prioritize preferred shifts and availability.",
        "Coverage Quality": "Ensure optimal staffing levels and skill distribution. Prioritize experienced staff during peak hours.",
        "Fair Distribution": "Distribute hours and preferred shifts fairly among all employees. Avoid concentration.",
        "Balanced": "Balance employee satisfaction, coverage quality, and fair distribution equally.",
    }
    
    constraint_adjustments = {
        "Flexible": "Allow minor constraint violations if they significantly improve optimization goals.",
        "Standard": "Respect all major constraints while optimizing within bounds.",
        "Strict": "Strictly enforce all constraints without exception."
    }
    
    base_prompt = prompts.get(optimization_focus, prompts["Balanced"])
    constraint_prompt = constraint_adjustments.get(constraint_level, constraint_adjustments["Standard"])
    
    return f"{base_prompt} {constraint_prompt}"

def apply_advanced_processing(schedule_df: pd.DataFrame, emp_data: pd.DataFrame, 
                            patterns: Dict, bs: Any, kwargs: Dict) -> pd.DataFrame:
    """Apply advanced post-processing to the generated schedule."""
    if schedule_df.empty:
        return schedule_df
    
    processed_df = schedule_df.copy()
    
    # Apply role priority adjustments
    optimization_focus = kwargs.get("optimization_focus", "Balanced")
    
    if optimization_focus == "Employee Satisfaction":
        # Adjust assignments to better match preferences
        processed_df = optimize_for_satisfaction(processed_df, emp_data, patterns)
    elif optimization_focus == "Coverage Quality":
        # Ensure best employees are scheduled for critical periods
        processed_df = optimize_for_coverage(processed_df, emp_data, patterns, bs)
    elif optimization_focus == "Fair Distribution":
        # Ensure fair distribution of shifts and hours
        processed_df = optimize_for_satisfaction(processed_df, emp_data, patterns)  # Reuse satisfaction logic for fairness
    
    return processed_df

def optimize_for_satisfaction(schedule_df: pd.DataFrame, emp_data: pd.DataFrame, patterns: Dict) -> pd.DataFrame:
    """Optimize schedule for employee satisfaction."""
    # Create preference lookup
    emp_prefs = dict(zip(emp_data['id'], emp_data['preferred_shift']))
    
    optimized_df = schedule_df.copy()
    
    # Try to match preferred shifts
    for idx, row in schedule_df.iterrows():
        emp_id = row['employee_id']
        preferred_shift = emp_prefs.get(emp_id, '')
        
        if preferred_shift and preferred_shift != row['shift_type']:
            # Check if we can swap with someone who prefers this shift
            same_date_shifts = schedule_df[schedule_df['date'] == row['date']]
            for _, other_row in same_date_shifts.iterrows():
                other_emp_id = other_row['employee_id']
                other_pref = emp_prefs.get(other_emp_id, '')
                
                if (other_pref == row['shift_type'] and 
                    preferred_shift == other_row['shift_type']):
                    # Swap the assignments
                    optimized_df.at[idx, 'employee_id'] = other_emp_id
                    other_idx = schedule_df.index[schedule_df['employee_id'] == other_emp_id].tolist()[0]
                    optimized_df.at[other_idx, 'employee_id'] = emp_id
                    break
    
    return optimized_df

def optimize_for_coverage(schedule_df: pd.DataFrame, emp_data: pd.DataFrame, 
                        patterns: Dict, bs: Any) -> pd.DataFrame:
    """Optimize schedule for coverage quality."""
    # Use max_hours_per_week as proxy for experience/availability
    emp_experience = dict(zip(emp_data['id'], emp_data['max_hours_per_week']))
    
    optimized_df = schedule_df.copy()
    
    # Identify rush hours and critical periods
    if hasattr(bs, 'day_settings') and isinstance(bs.day_settings, dict):
        for idx, row in schedule_df.iterrows():
            date_obj = datetime.strptime(str(row['date']), '%Y-%m-%d').date()
            day_name = date_obj.strftime('%A')
            
            if day_name in bs.day_settings:
                day_setting = bs.day_settings[day_name]
                rush_hours = getattr(day_setting, 'rush_hours', [])
                
                # If this is a rush hour period, prefer experienced employees
                if rush_hours and row['shift_type'] in ['day', 'morning']:
                    current_emp_id = row['employee_id']
                    current_exp = emp_experience.get(current_emp_id, 0)
                    
                    # Find more experienced employees for same role (using max hours as proxy)
                    same_role_emps = emp_data[emp_data['role'] == row['role']]
                    better_alternatives = same_role_emps[same_role_emps['max_hours_per_week'] > current_exp]
                    
                    if not better_alternatives.empty:
                        best_alternative = better_alternatives.iloc[-1]  # Take highest max hours (most available)
                        optimized_df.at[idx, 'employee_id'] = best_alternative['id']
    
    return optimized_df

def calculate_advanced_schedule_score(schedule_df: pd.DataFrame, emp_data: pd.DataFrame, 
                                    patterns: Dict, optimization_focus: str) -> Dict:
    """Calculate advanced scoring metrics for the generated schedule."""
    if schedule_df.empty:
        return {'total_score': 0, 'details': 'Empty schedule'}
    
    scores = {}
    
    # Base scores from original function
    base_scores = calculate_schedule_score(schedule_df, emp_data, patterns)
    scores.update(base_scores)
    
    # Advanced scoring based on optimization focus
    if optimization_focus == "Employee Satisfaction":
        scores['satisfaction_score'] = calculate_satisfaction_score(schedule_df, emp_data)
    elif optimization_focus == "Coverage Quality":
        scores['coverage_quality'] = calculate_coverage_quality_score(schedule_df, emp_data, patterns)
    elif optimization_focus == "Fair Distribution":
        scores['fairness_score'] = calculate_fairness_score(schedule_df, emp_data)
        scores['fairness_score'] = calculate_fairness_score(schedule_df, emp_data)
    
    # Calculate weighted total score
    weights = {
        "Employee Satisfaction": {'satisfaction': 0.7, 'fairness': 0.2, 'coverage': 0.1},
        "Coverage Quality": {'coverage': 0.7, 'satisfaction': 0.2, 'fairness': 0.1},
        "Fair Distribution": {'fairness': 0.6, 'satisfaction': 0.3, 'coverage': 0.1},
        "Balanced": {'coverage': 0.4, 'satisfaction': 0.3, 'fairness': 0.3}
    }
    
    focus_weights = weights.get(optimization_focus, weights["Balanced"])
    
    weighted_score = 0
    for metric, weight in focus_weights.items():
        if f"{metric}_score" in scores:
            weighted_score += scores[f"{metric}_score"] * weight
        elif f"{metric}_efficiency" in scores:
            weighted_score += scores[f"{metric}_efficiency"] * weight
        elif metric in scores:
            weighted_score += scores[metric] * weight
    
    scores['weighted_total'] = round(weighted_score, 2)
    scores['optimization_focus'] = optimization_focus
    
    return scores

def calculate_satisfaction_score(schedule_df: pd.DataFrame, emp_data: pd.DataFrame) -> float:
    """Calculate employee satisfaction score (0-100)."""
    if schedule_df.empty:
        return 0
    
    emp_prefs = dict(zip(emp_data['id'], emp_data['preferred_shift']))
    matches = 0
    total = len(schedule_df)
    
    for _, row in schedule_df.iterrows():
        emp_id = row['employee_id']
        if emp_prefs.get(emp_id) == row['shift_type']:
            matches += 1
    
    return (matches / total * 100) if total > 0 else 0

def calculate_coverage_quality_score(schedule_df: pd.DataFrame, emp_data: pd.DataFrame, patterns: Dict) -> float:
    """Calculate coverage quality score (0-100)."""
    if schedule_df.empty:
        return 0
    
    # Use max_hours_per_week as proxy for employee capacity/experience
    emp_quality = dict(zip(emp_data['id'], emp_data['max_hours_per_week']))
    
    # Calculate average quality of assigned employees
    total_quality = sum(emp_quality.get(emp_id, 0) for emp_id in schedule_df['employee_id'])
    avg_quality = total_quality / len(schedule_df)
    
    # Calculate maximum possible quality
    max_possible_quality = emp_data['max_hours_per_week'].max()
    
    if max_possible_quality == 0:
        return 100
    
    quality_score = (avg_quality / max_possible_quality) * 100
    return min(100, max(0, quality_score))

def calculate_fairness_score(schedule_df: pd.DataFrame, emp_data: pd.DataFrame) -> float:
    """Calculate fairness score based on hour distribution (0-100)."""
    if schedule_df.empty:
        return 0
    
    # Count hours per employee
    emp_hours = schedule_df['employee_id'].value_counts().to_dict()
    
    if not emp_hours:
        return 100
    
    # Calculate standard deviation of hour distribution
    hours_list = list(emp_hours.values())
    if len(hours_list) <= 1:
        return 100
    
    mean_hours = sum(hours_list) / len(hours_list)
    variance = sum((h - mean_hours) ** 2 for h in hours_list) / len(hours_list)
    std_dev = variance ** 0.5
    
    # Convert to fairness score (lower std_dev = higher fairness)
    max_possible_std = mean_hours  # Worst case: one person gets all hours
    fairness = 100 - (std_dev / max_possible_std * 100) if max_possible_std > 0 else 100
    
    return max(0, min(100, fairness))