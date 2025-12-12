# -*- coding: utf-8 -*-
"""
AI-Powered Intelligent Scheduler using OpenAI API
Enhances schedule generation with ML-based optimization and conflict resolution.
Enhanced with DSPy Signatures for structured, predictable outputs.
"""

import os
import json
from typing import Dict, List, Tuple, Any
import pandas as pd
import datetime as dt
from openai import OpenAI

from constants import DAYS, SHIFT_TIMES

# Initialize OpenAI client
client = None
try:
    api_key = os.getenv("OpenAI_API_KEY")
    if api_key:
        client = OpenAI(api_key=api_key)
except Exception as e:
    print(f"OpenAI initialization failed: {e}")

# Initialize DSPy for structured outputs
DSPY_AVAILABLE = False
try:
    from dspy_signatures import (
        initialize_dspy,
        ShiftPlannerModule,
        AvailabilityAnalyzerModule,
        ViolationDetectorModule,
        SuggestionGeneratorModule,
        ComprehensiveSchedulerModule,
        ShiftPerDay,
        EmployeeAvailability,
        Violation,
        Suggestion
    )
    
    # Initialize DSPy if API key is available
    if client:
        try:
            initialize_dspy()
            DSPY_AVAILABLE = True
            print("✓ DSPy initialized for structured scheduling")
        except Exception as e:
            print(f"DSPy initialization warning: {e}")
except ImportError as e:
    print(f"DSPy signatures not available: {e}")


def _shift_len(shift: str) -> int:
    """Return shift duration in hours."""
    s, e = SHIFT_TIMES.get(shift, (9, 17))
    return (24 - s + e) if e < s else (e - s)


def analyze_schedule_with_ai(
    employees: List[dict],
    active_shifts: List[str],
    roles: List[str],
    rules: Dict,
    role_settings: Dict,
    days_count: int,
    work_model: str = "5ήμερο"
) -> Dict[str, Any]:
    """
    Use AI to analyze staffing requirements and provide optimization suggestions.
    
    Returns a dictionary with:
    - staffing_insights: AI analysis of staffing needs
    - optimization_tips: Suggestions for better scheduling
    - predicted_conflicts: Potential scheduling conflicts
    - recommended_actions: Actions to improve the schedule
    """
    if not client:
        return {
            "error": "OpenAI API not configured",
            "staffing_insights": "AI analysis unavailable",
            "optimization_tips": [],
            "predicted_conflicts": [],
            "recommended_actions": []
        }
    
    try:
        # Prepare context for AI
        employee_summary = {
            "total_employees": len(employees),
            "employees": [
                {
                    "name": e["name"],
                    "roles": e.get("roles", []),
                    "availability": e.get("availability", [])
                } for e in employees
            ]
        }
        
        role_summary = {
            role: {
                "min_per_shift": role_settings.get(role, {}).get("min_per_shift", 1),
                "max_per_shift": role_settings.get(role, {}).get("max_per_shift", 5),
                "priority": role_settings.get(role, {}).get("priority", 5),
                "preferred_shifts": role_settings.get(role, {}).get("preferred_shifts", [])
            } for role in roles
        }
        
        prompt = f"""Analyze this shift scheduling scenario and provide insights:

BUSINESS MODEL: {work_model}
SCHEDULE DURATION: {days_count} days
SHIFTS: {', '.join(active_shifts)}
ROLES: {', '.join(roles)}

EMPLOYEES:
{json.dumps(employee_summary, indent=2)}

ROLE REQUIREMENTS:
{json.dumps(role_summary, indent=2)}

RULES:
- Max daily hours: {rules.get('max_daily_hours_5days', 8)}h
- Weekly hours cap: {rules.get('weekly_hours_5days', 40)}h
- Min daily rest: {rules.get('min_daily_rest', 11)}h
- Max consecutive days: {rules.get('max_consecutive_days', 6)}

Provide:
1. Staffing analysis (are there enough employees for all roles?)
2. Potential bottlenecks (which roles/shifts might be understaffed?)
3. Optimization suggestions (how to improve coverage and fairness)
4. Predicted conflicts (scheduling challenges to watch for)
5. Recommended actions (specific steps to improve the schedule)

Format your response as JSON with these keys:
{{
  "staffing_insights": "brief analysis",
  "optimization_tips": ["tip1", "tip2", ...],
  "predicted_conflicts": ["conflict1", "conflict2", ...],
  "recommended_actions": ["action1", "action2", ...],
  "coverage_score": 0-100
}}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert workforce scheduling analyst. Provide concise, actionable insights in JSON format."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
        
    except Exception as e:
        print(f"AI analysis error: {e}")
        return {
            "error": str(e),
            "staffing_insights": "Analysis failed",
            "optimization_tips": [],
            "predicted_conflicts": [],
            "recommended_actions": []
        }


def optimize_employee_assignments_with_ai(
    date: dt.date,
    shift: str,
    role: str,
    available_employees: List[dict],
    current_schedule: pd.DataFrame,
    rules: Dict,
    work_model: str = "5ήμερο"
) -> List[str]:
    """
    Use AI to intelligently select the best employees for a specific shift/role.
    
    Returns list of employee names in priority order.
    """
    if not client or not available_employees:
        # Fallback: simple load-based sorting
        return [e["name"] for e in available_employees[:3]]
    
    try:
        # Compute workload for each employee
        employee_stats = []
        for emp in available_employees:
            name = emp["name"]
            emp_sched = current_schedule[current_schedule["Υπάλληλος"] == name]
            
            day_hours = emp_sched[emp_sched["Ημερομηνία"] == str(date)]["Ώρες"].sum() if not emp_sched.empty else 0
            
            week = date.isocalendar().week
            week_hours = 0
            for _, row in emp_sched.iterrows():
                row_date = pd.to_datetime(row["Ημερομηνία"]).date()
                if row_date.isocalendar().week == week:
                    week_hours += row["Ώρες"]
            
            employee_stats.append({
                "name": name,
                "roles": emp.get("roles", []),
                "day_hours": int(day_hours),
                "week_hours": int(week_hours),
                "total_shifts": len(emp_sched)
            })
        
        prompt = f"""Select the best employee(s) for this shift assignment:

DATE: {date.strftime('%Y-%m-%d')} ({DAYS[date.weekday()]})
SHIFT: {shift}
ROLE: {role}
WORK MODEL: {work_model}

AVAILABLE EMPLOYEES:
{json.dumps(employee_stats, indent=2)}

CONSTRAINTS:
- Max daily hours: {rules.get('max_daily_hours_5days', 8)}h
- Weekly hours cap: {rules.get('weekly_hours_5days', 40)}h
- Shift duration: {_shift_len(shift)}h

Select 1-3 employees prioritizing:
1. Workload balance (prefer employees with fewer hours)
2. Fairness (distribute shifts evenly)
3. Avoiding burnout (don't overload anyone)
4. Role expertise (if roles list indicates specialization)

Return JSON: {{"selected": ["name1", "name2", ...], "reasoning": "brief explanation"}}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a fair and efficient workforce scheduler. Select employees to balance workload."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=200,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return result.get("selected", [available_employees[0]["name"]])
        
    except Exception as e:
        print(f"AI employee selection error: {e}")
        # Fallback
        return [available_employees[0]["name"]]


def resolve_conflicts_with_ai(
    violations_df: pd.DataFrame,
    schedule_df: pd.DataFrame,
    employees: List[dict],
    active_shifts: List[str],
    roles: List[str],
    rules: Dict
) -> Dict[str, Any]:
    """
    Use AI to suggest specific fixes for schedule violations.
    
    Returns:
    - suggested_swaps: List of employee swap suggestions
    - suggested_removals: Shifts to remove to fix violations
    - alternative_assignments: Better assignment suggestions
    """
    if not client or violations_df.empty:
        return {
            "suggested_swaps": [],
            "suggested_removals": [],
            "alternative_assignments": []
        }
    
    try:
        # Summarize violations
        violation_summary = violations_df.groupby(["Rule", "Severity"]).size().reset_index(name="count")
        
        top_violations = violations_df.head(10).to_dict('records')
        
        prompt = f"""Analyze these scheduling violations and suggest fixes:

VIOLATION SUMMARY:
{violation_summary.to_string()}

TOP VIOLATIONS:
{json.dumps(top_violations, indent=2, default=str)}

AVAILABLE SHIFTS: {', '.join(active_shifts)}
AVAILABLE ROLES: {', '.join(roles)}

Suggest specific actions to resolve violations:
1. Employee swaps (who can switch with whom)
2. Shift removals (which assignments to delete)
3. Alternative assignments (better shift/role combinations)

Return JSON:
{{
  "suggested_swaps": [
    {{"employee1": "name", "employee2": "name", "date": "YYYY-MM-DD", "shift": "shift", "reason": "why"}}
  ],
  "suggested_removals": [
    {{"employee": "name", "date": "YYYY-MM-DD", "shift": "shift", "reason": "why"}}
  ],
  "alternative_assignments": [
    {{"employee": "name", "date": "YYYY-MM-DD", "shift": "shift", "role": "role", "reason": "why"}}
  ],
  "priority_fixes": ["action1", "action2"]
}}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at resolving workforce scheduling conflicts. Provide specific, actionable fixes."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=800,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
        
    except Exception as e:
        print(f"AI conflict resolution error: {e}")
        return {
            "suggested_swaps": [],
            "suggested_removals": [],
            "alternative_assignments": [],
            "error": str(e)
        }


def get_ai_scheduling_advice(
    context: str,
    question: str
) -> str:
    """
    Get general scheduling advice from AI.
    
    Args:
        context: Current scheduling situation
        question: Specific question to ask
    
    Returns:
        AI response as string
    """
    if not client:
        return "AI assistant not available. Please configure OpenAI API key."
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful workforce scheduling expert. Provide practical, actionable advice."},
                {"role": "user", "content": f"Context: {context}\n\nQuestion: {question}"}
            ],
            temperature=0.7,
            max_tokens=300
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"Error getting AI advice: {str(e)}"


# ============================================================================
# DSPy-based Structured Functions
# ============================================================================

def get_shifts_per_day_structured(
    business_model: str,
    start_date: dt.date,
    days_count: int,
    active_shifts: List[str],
    roles: List[str],
    role_requirements: Dict[str, Dict[str, int]],
    special_requirements: str = ""
) -> List[Dict[str, Any]]:
    """
    Get structured shifts per day using DSPy Signatures.
    
    Args:
        business_model: Work model (e.g., "5ήμερο")
        start_date: Starting date
        days_count: Number of days to plan
        active_shifts: List of shift types
        roles: List of roles
        role_requirements: Dict mapping roles to shift requirements
        special_requirements: Any special requirements
    
    Returns:
        List of dicts with shifts per day (structured output)
    """
    if not DSPY_AVAILABLE:
        return _fallback_shifts_per_day(start_date, days_count, active_shifts, roles, role_requirements)
    
    try:
        planner = ShiftPlannerModule()
        
        result = planner.forward(
            business_model=business_model,
            start_date=start_date.strftime("%Y-%m-%d"),
            days_count=days_count,
            active_shifts=",".join(active_shifts),
            roles=",".join(roles),
            role_requirements=json.dumps(role_requirements),
            special_requirements=special_requirements
        )
        
        # Parse structured output
        shifts_data = json.loads(result.shifts_per_day)
        return shifts_data
        
    except Exception as e:
        print(f"DSPy shifts planning error: {e}")
        return _fallback_shifts_per_day(start_date, days_count, active_shifts, roles, role_requirements)


def get_employee_availability_structured(
    employees: List[dict],
    schedule_start: dt.date,
    schedule_days: int,
    current_schedule: pd.DataFrame,
    work_rules: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Get structured employee availability using DSPy Signatures.
    
    Args:
        employees: List of employee dicts
        schedule_start: Schedule start date
        schedule_days: Number of days in schedule
        current_schedule: Current schedule DataFrame
        work_rules: Work rules and constraints
    
    Returns:
        List of dicts with employee availability (structured output)
    """
    if not DSPY_AVAILABLE:
        return _fallback_employee_availability(employees, current_schedule, work_rules)
    
    try:
        analyzer = AvailabilityAnalyzerModule()
        
        # Convert DataFrame to JSON if needed
        schedule_json = current_schedule.to_json(orient='records') if not current_schedule.empty else "[]"
        
        result = analyzer.forward(
            employees_data=json.dumps(employees),
            schedule_start=schedule_start.strftime("%Y-%m-%d"),
            schedule_days=schedule_days,
            current_schedule=schedule_json,
            work_rules=json.dumps(work_rules)
        )
        
        # Parse structured output
        availability_data = json.loads(result.employee_availability)
        return availability_data
        
    except Exception as e:
        print(f"DSPy availability analysis error: {e}")
        return _fallback_employee_availability(employees, current_schedule, work_rules)


def get_violations_structured(
    schedule_df: pd.DataFrame,
    employees: List[dict],
    work_rules: Dict[str, Any],
    role_requirements: Dict[str, Any],
    business_constraints: str = ""
) -> List[Dict[str, Any]]:
    """
    Get structured violations using DSPy Signatures.
    
    Args:
        schedule_df: Current schedule DataFrame
        employees: List of employee dicts
        work_rules: Work rules to check
        role_requirements: Role-specific requirements
        business_constraints: Additional constraints
    
    Returns:
        List of Violation dicts (structured output)
    """
    if not DSPY_AVAILABLE:
        return _fallback_violations(schedule_df, work_rules)
    
    try:
        detector = ViolationDetectorModule()
        
        schedule_json = schedule_df.to_json(orient='records') if not schedule_df.empty else "[]"
        
        result = detector.forward(
            schedule_data=schedule_json,
            employees=json.dumps(employees),
            work_rules=json.dumps(work_rules),
            role_requirements=json.dumps(role_requirements),
            business_constraints=business_constraints
        )
        
        # Parse structured output
        violations_data = json.loads(result.violations)
        return violations_data
        
    except Exception as e:
        print(f"DSPy violation detection error: {e}")
        return _fallback_violations(schedule_df, work_rules)


def get_suggestions_structured(
    schedule_df: pd.DataFrame,
    violations: List[Dict[str, Any]],
    employees: List[dict],
    roles: List[str],
    active_shifts: List[str],
    optimization_goals: str = "minimize violations, balance workload, ensure fairness"
) -> List[Dict[str, Any]]:
    """
    Get structured optimization suggestions using DSPy Signatures.
    
    Args:
        schedule_df: Current schedule DataFrame
        violations: List of violation dicts
        employees: List of employee dicts
        roles: Available roles
        active_shifts: Active shift types
        optimization_goals: Goals for optimization
    
    Returns:
        List of Suggestion dicts (structured output)
    """
    if not DSPY_AVAILABLE:
        return _fallback_suggestions(violations, employees)
    
    try:
        generator = SuggestionGeneratorModule()
        
        schedule_json = schedule_df.to_json(orient='records') if not schedule_df.empty else "[]"
        
        result = generator.forward(
            schedule_data=schedule_json,
            violations=json.dumps(violations),
            employees=json.dumps(employees),
            roles=",".join(roles),
            active_shifts=",".join(active_shifts),
            optimization_goals=optimization_goals
        )
        
        # Parse structured output
        suggestions_data = json.loads(result.suggestions)
        return suggestions_data
        
    except Exception as e:
        print(f"DSPy suggestion generation error: {e}")
        return _fallback_suggestions(violations, employees)


def get_comprehensive_analysis_structured(
    business_settings: Dict[str, Any],
    employees: List[dict],
    schedule_params: Dict[str, Any],
    current_schedule: pd.DataFrame,
    work_rules: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get comprehensive schedule analysis using DSPy Signatures.
    
    Returns all four key outputs:
    - shifts_per_day: Structured daily shift requirements
    - employee_availability: Structured availability data
    - violations: Structured violation list
    - suggestions: Structured optimization suggestions
    
    Args:
        business_settings: Business configuration
        employees: List of employee dicts
        schedule_params: Schedule parameters (dates, shifts, roles)
        current_schedule: Current schedule DataFrame
        work_rules: Work rules and constraints
    
    Returns:
        Dict with all four structured outputs plus overall score
    """
    if not DSPY_AVAILABLE:
        return _fallback_comprehensive_analysis(
            employees, schedule_params, current_schedule, work_rules
        )
    
    try:
        scheduler = ComprehensiveSchedulerModule()
        
        schedule_json = current_schedule.to_json(orient='records') if not current_schedule.empty else "[]"
        
        result = scheduler.forward(
            business_context=json.dumps(business_settings),
            employees_data=json.dumps(employees),
            schedule_parameters=json.dumps(schedule_params),
            current_schedule=schedule_json,
            work_rules=json.dumps(work_rules)
        )
        
        # Parse all structured outputs
        analysis = {
            "shifts_per_day": json.loads(result.shifts_analysis),
            "employee_availability": json.loads(result.employee_availability),
            "violations": json.loads(result.violations),
            "suggestions": json.loads(result.suggestions),
            "overall_score": result.overall_score
        }
        
        return analysis
        
    except Exception as e:
        print(f"DSPy comprehensive analysis error: {e}")
        return _fallback_comprehensive_analysis(
            employees, schedule_params, current_schedule, work_rules
        )


# ============================================================================
# Fallback Functions (when DSPy unavailable)
# ============================================================================

def _fallback_shifts_per_day(start_date, days_count, active_shifts, roles, role_requirements):
    """Fallback for shifts per day when DSPy unavailable."""
    shifts_list = []
    for i in range(days_count):
        current_date = start_date + dt.timedelta(days=i)
        day_shifts = []
        
        for shift in active_shifts:
            for role in roles:
                required = role_requirements.get(role, {}).get(shift, 1)
                day_shifts.append({
                    "shift_type": shift,
                    "role": role,
                    "required_count": required
                })
        
        shifts_list.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "day_name": DAYS[current_date.weekday()],
            "shifts": day_shifts,
            "total_staff_needed": sum(s["required_count"] for s in day_shifts),
            "is_weekend": current_date.weekday() >= 5
        })
    
    return shifts_list


def _fallback_employee_availability(employees, current_schedule, work_rules):
    """Fallback for employee availability when DSPy unavailable."""
    availability_list = []
    
    for emp in employees:
        name = emp["name"]
        emp_sched = current_schedule[current_schedule["Υπάλληλος"] == name] if not current_schedule.empty else pd.DataFrame()
        
        current_hours = emp_sched["Ώρες"].sum() if not emp_sched.empty else 0
        
        availability_list.append({
            "name": name,
            "roles": emp.get("roles", []),
            "available_dates": emp.get("availability", []),
            "preferred_shifts": emp.get("preferred_shifts", []),
            "max_weekly_hours": work_rules.get("weekly_hours_5days", 40),
            "current_weekly_hours": float(current_hours),
            "unavailable_dates": emp.get("unavailable", [])
        })
    
    return availability_list


def _fallback_violations(schedule_df, work_rules):
    """Fallback for violations when DSPy unavailable."""
    violations = []
    
    if schedule_df.empty:
        return violations
    
    # Check for basic violations
    for employee in schedule_df["Υπάλληλος"].unique():
        emp_sched = schedule_df[schedule_df["Υπάλληλος"] == employee]
        total_hours = emp_sched["Ώρες"].sum()
        max_hours = work_rules.get("weekly_hours_5days", 40)
        
        if total_hours > max_hours:
            violations.append({
                "violation_type": "MAX_HOURS_EXCEEDED",
                "severity": "HIGH",
                "employee": employee,
                "description": f"{employee} scheduled for {total_hours}h, exceeds max {max_hours}h",
                "rule_violated": "max_weekly_hours",
                "current_value": float(total_hours),
                "max_allowed": float(max_hours)
            })
    
    return violations


def _fallback_suggestions(violations, employees):
    """Fallback for suggestions when DSPy unavailable."""
    suggestions = []
    
    for v in violations:
        if v.get("violation_type") == "MAX_HOURS_EXCEEDED":
            suggestions.append({
                "suggestion_type": "REDUCE_HOURS",
                "priority": "HIGH",
                "employee": v.get("employee"),
                "description": f"Reduce hours for {v.get('employee')} to stay within limits",
                "expected_benefit": "Resolves overtime violation",
                "impact_score": 80.0
            })
    
    return suggestions


def _fallback_comprehensive_analysis(employees, schedule_params, current_schedule, work_rules):
    """Fallback for comprehensive analysis when DSPy unavailable."""
    start_date = schedule_params.get("start_date", dt.date.today())
    days_count = schedule_params.get("days_count", 7)
    active_shifts = schedule_params.get("active_shifts", ["day", "night"])
    roles = schedule_params.get("roles", [])
    role_requirements = schedule_params.get("role_requirements", {})
    
    return {
        "shifts_per_day": _fallback_shifts_per_day(start_date, days_count, active_shifts, roles, role_requirements),
        "employee_availability": _fallback_employee_availability(employees, current_schedule, work_rules),
        "violations": _fallback_violations(current_schedule, work_rules),
        "suggestions": [],
        "overall_score": "70 - Basic scheduling without optimization"
    }
