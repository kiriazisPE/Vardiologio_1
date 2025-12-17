"""
Planner Service - Clean interface between UI and reasoning layer.

This service:
- Abstracts DSPy implementation details from UI
- Provides simple, typed interfaces
- Handles artifact loading and versioning
- Manages caching and performance
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import os

# Import reasoning modules
from reasoning.modules import load_planner, ViolationAnalyzer, DecisionExplainer
from reasoning.evaluation import score_schedule


class PlannerService:
    """
    Service for generating and analyzing shift schedules.
    
    The UI never calls DSPy directly - always goes through this service.
    """
    
    def __init__(self, version: str = "latest", reasoning_mode: str = "chain_of_thought"):
        """
        Initialize planner service.
        
        Args:
            version: Reasoning artifact version to load
            reasoning_mode: "chain_of_thought", "react", or "basic"
        """
        self.version = version
        self.reasoning_mode = reasoning_mode
        self.planner = load_planner(version=version, reasoning_mode=reasoning_mode)
        self.analyzer = ViolationAnalyzer()
        self.explainer = DecisionExplainer()
    
    def generate_weekly_schedule(
        self,
        employees: List[Dict[str, Any]],
        active_shifts: List[str],
        roles: List[str],
        constraints: Dict[str, Any],
        week_start: str,
        roles_required: Optional[Dict[str, Dict[str, int]]] = None
    ) -> Dict[str, Any]:
        """
        Generate a weekly schedule.
        
        Args:
            employees: List of employee dicts with {id, name, roles, availability}
            active_shifts: List of shift names (e.g., ["Πρωί", "Απόγευμα"])
            roles: List of role names
            constraints: Scheduling constraints dict
            week_start: Start date (YYYY-MM-DD)
            roles_required: Optional roles per shift specification
        
        Returns:
            {
                "schedule": [{date, shift, employee_id, role, hours}],
                "reasoning": "explanation...",
                "metrics": {hard_violations, soft_violations, ...},
                "recommendations": ["..."],
                "metadata": {version, timestamp, ...}
            }
        """
        # Build shifts_required from active_shifts
        from datetime import datetime as dt, timedelta
        start_date = dt.fromisoformat(week_start)
        shifts_required = {}
        
        for i in range(7):  # Full week
            date = start_date + timedelta(days=i)
            shifts_required[date.isoformat()] = active_shifts
        
        # Default roles_required if not provided
        if roles_required is None:
            roles_required = {}
            for date_str in shifts_required:
                for shift in active_shifts:
                    key = f"{date_str}_{shift}"
                    # Estimate 2 people per shift
                    roles_required[key] = {role: 1 for role in roles[:2]} if roles else {}
        
        # Generate schedule using reasoning engine
        result = self.planner(
            employees=employees,
            shifts_required=shifts_required,
            roles_required=roles_required,
            constraints=constraints,
            week_start=week_start
        )
        
        schedule = result["schedule"]
        
        # Analyze for violations
        violations_result = self.analyzer(
            schedule=schedule,
            constraints=constraints,
            employees=employees
        )
        
        # Score the schedule
        metrics = score_schedule(
            schedule=schedule,
            constraints=constraints,
            employees=employees,
            roles_required=roles_required
        )
        
        return {
            "schedule": schedule,
            "reasoning": result.get("reasoning", ""),
            "metrics": metrics,
            "violations": violations_result["violations"],
            "recommendations": violations_result["recommendations"],
            "metadata": {
                **result.get("metadata", {}),
                "version": self.version,
                "timestamp": datetime.now().isoformat(),
                "service": "PlannerService"
            }
        }
    
    def analyze_violations(
        self,
        schedule: List[Dict[str, Any]],
        constraints: Dict[str, Any],
        employees: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze a schedule for violations.
        
        Returns:
            {
                "violations": [{type, severity, employee, date, details}],
                "recommendations": [str],
                "severity_counts": {high, medium, low}
            }
        """
        return self.analyzer(
            schedule=schedule,
            constraints=constraints,
            employees=employees
        )
    
    def explain_decision(
        self,
        assignment: Dict[str, Any],
        alternatives: List[Dict[str, Any]],
        schedule_context: List[Dict[str, Any]],
        constraints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Explain why a specific assignment was made.
        
        Returns:
            {
                "explanation": str,
                "trade_offs": [str],
                "alternatives_considered": int
            }
        """
        return self.explainer(
            assignment=assignment,
            alternatives=alternatives,
            schedule_context=schedule_context,
            constraints=constraints
        )
    
    def get_version_info(self) -> Dict[str, str]:
        """Get information about the loaded reasoning artifact."""
        return {
            "version": self.version,
            "reasoning_mode": self.reasoning_mode,
            "model": os.getenv("OPENAI_MODEL", "gpt-4"),
            "service": "PlannerService v1.0.0"
        }


# Singleton instance (optional - can be replaced with dependency injection)
_planner_service: Optional[PlannerService] = None


def get_planner_service() -> PlannerService:
    """
    Get the global planner service instance.
    
    In production, this would load the versioned artifact specified in config.
    """
    global _planner_service
    
    if _planner_service is None:
        # Load version from environment or default to latest
        version = os.getenv("REASONING_VERSION", "latest")
        mode = os.getenv("REASONING_MODE", "chain_of_thought")
        _planner_service = PlannerService(version=version, reasoning_mode=mode)
    
    return _planner_service
