"""
DSPy Modules - Composable reasoning components for shift scheduling.

Modules encapsulate the actual reasoning logic using DSPy primitives.
Each module is:
- Testable against golden datasets
- Optimizable via DSPy optimizers
- Versioned as artifacts
- Deployable independently
"""

import dspy
from typing import List, Dict, Any, Optional
from .signatures import (
    GenerateWeeklySchedule,
    AnalyzeScheduleViolations,
    OptimizeAssignment,
    ExplainScheduleDecision
)


class ShiftPlanner(dspy.Module):
    """
    Main scheduling engine - generates weekly schedules with constraint satisfaction.
    
    This is the primary reasoning artifact that gets versioned and optimized.
    """
    
    def __init__(self, reasoning_mode: str = "chain_of_thought"):
        super().__init__()
        
        # Choose reasoning strategy
        if reasoning_mode == "chain_of_thought":
            self.generator = dspy.ChainOfThought(GenerateWeeklySchedule)
        elif reasoning_mode == "react":
            self.generator = dspy.ReAct(GenerateWeeklySchedule)
        else:
            self.generator = dspy.Predict(GenerateWeeklySchedule)
    
    def forward(
        self,
        employees: List[Dict[str, Any]],
        shifts_required: Dict[str, List[str]],
        roles_required: Dict[str, Dict[str, int]],
        constraints: Dict[str, Any],
        week_start: str
    ) -> Dict[str, Any]:
        """
        Generate a weekly schedule.
        
        Returns:
            {
                "schedule": [...],
                "reasoning": "...",
                "metadata": {
                    "version": "...",
                    "timestamp": "...",
                    "model": "..."
                }
            }
        """
        result = self.generator(
            employees=employees,
            shifts_required=shifts_required,
            roles_required=roles_required,
            constraints=constraints,
            week_start=week_start
        )
        
        return {
            "schedule": result.schedule,
            "reasoning": result.reasoning,
            "metadata": {
                "version": "1.0.0",
                "reasoning_mode": self.generator.__class__.__name__
            }
        }


class ViolationAnalyzer(dspy.Module):
    """
    Analyzes schedules for constraint violations and provides actionable recommendations.
    """
    
    def __init__(self):
        super().__init__()
        self.analyzer = dspy.ChainOfThought(AnalyzeScheduleViolations)
    
    def forward(
        self,
        schedule: List[Dict[str, Any]],
        constraints: Dict[str, Any],
        employees: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze schedule for violations.
        
        Returns:
            {
                "violations": [...],
                "recommendations": [...],
                "severity_counts": {
                    "high": n,
                    "medium": m,
                    "low": l
                }
            }
        """
        result = self.analyzer(
            schedule=schedule,
            constraints=constraints,
            employees=employees
        )
        
        # Count violations by severity
        severity_counts = {
            "high": sum(1 for v in result.violations if v.get("severity") == "high"),
            "medium": sum(1 for v in result.violations if v.get("severity") == "medium"),
            "low": sum(1 for v in result.violations if v.get("severity") == "low")
        }
        
        return {
            "violations": result.violations,
            "recommendations": result.recommendations,
            "severity_counts": severity_counts
        }


class AssignmentOptimizer(dspy.Module):
    """
    Optimizes individual shift assignments for fairness and constraint satisfaction.
    """
    
    def __init__(self):
        super().__init__()
        self.optimizer = dspy.ChainOfThought(OptimizeAssignment)
    
    def forward(
        self,
        shift_date: str,
        shift_name: str,
        role_needed: str,
        available_employees: List[Dict[str, Any]],
        current_schedule: List[Dict[str, Any]],
        constraints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Find the optimal employee for a single shift assignment.
        
        Returns:
            {
                "employee_id": int,
                "justification": str,
                "confidence": float
            }
        """
        result = self.optimizer(
            shift_date=shift_date,
            shift_name=shift_name,
            role_needed=role_needed,
            available_employees=available_employees,
            current_schedule=current_schedule,
            constraints=constraints
        )
        
        return {
            "employee_id": result.best_employee_id,
            "justification": result.justification,
            "confidence": 0.95  # Can be enhanced with prediction confidence
        }


class DecisionExplainer(dspy.Module):
    """
    Provides human-readable explanations for scheduling decisions.
    
    Critical for compliance, transparency, and manager trust.
    """
    
    def __init__(self):
        super().__init__()
        self.explainer = dspy.ChainOfThought(ExplainScheduleDecision)
    
    def forward(
        self,
        assignment: Dict[str, Any],
        alternatives: List[Dict[str, Any]],
        schedule_context: List[Dict[str, Any]],
        constraints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Explain a scheduling decision.
        
        Returns:
            {
                "explanation": str,
                "trade_offs": [str],
                "alternatives_considered": int
            }
        """
        result = self.explainer(
            assignment=assignment,
            alternatives=alternatives,
            schedule_context=schedule_context,
            constraints=constraints
        )
        
        return {
            "explanation": result.explanation,
            "trade_offs": result.trade_offs,
            "alternatives_considered": len(alternatives)
        }


# Module factory for loading versioned artifacts
def load_planner(version: str = "latest", reasoning_mode: str = "chain_of_thought") -> ShiftPlanner:
    """
    Load a versioned ShiftPlanner artifact.
    
    Args:
        version: Artifact version (e.g., "1.0.0", "latest")
        reasoning_mode: Reasoning strategy to use
    
    Returns:
        Configured ShiftPlanner module
    """
    # TODO: Implement artifact loading from storage
    # For now, create a new instance
    return ShiftPlanner(reasoning_mode=reasoning_mode)
