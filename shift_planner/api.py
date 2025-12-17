"""
FastAPI Backend - REST API for Shift Planner

This API provides endpoints for:
- Schedule generation
- Violation analysis
- Decision explanations
- Employee management
- Company settings

The API is a thin layer over PlannerService - no business logic here.
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import os

# Import database and services
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from db import (
    init_db,
    get_all_companies, get_company, create_company, update_company,
    get_employees, add_employee, update_employee, delete_employee,
    get_schedule_range, bulk_save_week_schedule
)
from app.services.planner_service import get_planner_service

# Initialize FastAPI app
app = FastAPI(
    title="Shift Planner API",
    description="AI-powered shift scheduling with DSPy reasoning engine",
    version="2.0.0"
)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "http://localhost:5173",  # Vite dev server
        os.getenv("FRONTEND_URL", "http://localhost:3000")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    print("✅ Database initialized")
    print("✅ PlannerService loaded")


# ============================================================================
# Pydantic Models
# ============================================================================

class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    active_shifts: Optional[List[str]] = None
    roles: Optional[List[str]] = None
    rules: Optional[Dict[str, Any]] = None
    work_model: Optional[str] = None


class EmployeeCreate(BaseModel):
    name: str = Field(..., min_length=1)
    roles: List[str]
    availability: Dict[str, List[str]]


class ScheduleGenerateRequest(BaseModel):
    company_id: int
    week_start: str = Field(..., description="ISO date: YYYY-MM-DD")
    days_count: int = Field(default=7, ge=1, le=14)


class ScheduleSaveRequest(BaseModel):
    company_id: int
    assignments: List[Dict[str, Any]]


# ============================================================================
# Health & Info Endpoints
# ============================================================================

@app.get("/")
async def root():
    """API root - health check and info"""
    return {
        "service": "Shift Planner API",
        "version": "2.0.0",
        "status": "healthy",
        "architecture": "DSPy-centric with versioned reasoning artifacts",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "companies": "/api/companies",
            "employees": "/api/companies/{id}/employees",
            "schedule": "/api/schedule",
            "reasoning": "/api/reasoning"
        }
    }


@app.get("/health")
async def health_check():
    """Health check for load balancers"""
    service = get_planner_service()
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "reasoning_version": service.get_version_info()
    }


# ============================================================================
# Company Endpoints
# ============================================================================

@app.get("/api/companies")
async def list_companies():
    """Get all companies"""
    companies = get_all_companies()
    return {"companies": companies}


@app.get("/api/companies/{company_id}")
async def get_company_by_id(company_id: int):
    """Get a specific company"""
    company = get_company(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@app.post("/api/companies")
async def create_new_company(company: CompanyCreate):
    """Create a new company"""
    company_id = create_company(company.name)
    return {"id": company_id, "name": company.name}


@app.patch("/api/companies/{company_id}")
async def update_company_settings(company_id: int, updates: CompanyUpdate):
    """Update company settings"""
    company = get_company(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    update_data = updates.dict(exclude_unset=True)
    update_company(company_id, update_data)
    
    return {"id": company_id, "updated": list(update_data.keys())}


# ============================================================================
# Employee Endpoints
# ============================================================================

@app.get("/api/companies/{company_id}/employees")
async def list_employees(company_id: int):
    """Get all employees for a company"""
    company = get_company(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    employees = get_employees(company_id)
    return {"employees": employees}


@app.post("/api/companies/{company_id}/employees")
async def create_employee(company_id: int, employee: EmployeeCreate):
    """Add a new employee"""
    company = get_company(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    employee_id = add_employee(
        company_id=company_id,
        name=employee.name,
        roles=employee.roles,
        availability=employee.availability
    )
    
    return {"id": employee_id, "name": employee.name}


@app.put("/api/companies/{company_id}/employees/{employee_id}")
async def modify_employee(company_id: int, employee_id: int, employee: EmployeeCreate):
    """Update an employee"""
    update_employee(
        employee_id=employee_id,
        name=employee.name,
        roles=employee.roles,
        availability=employee.availability
    )
    
    return {"id": employee_id, "updated": True}


@app.delete("/api/companies/{company_id}/employees/{employee_id}")
async def remove_employee(company_id: int, employee_id: int):
    """Delete an employee"""
    delete_employee(employee_id)
    return {"id": employee_id, "deleted": True}


# ============================================================================
# Schedule Endpoints (Reasoning Engine)
# ============================================================================

@app.post("/api/schedule/generate")
async def generate_schedule(request: ScheduleGenerateRequest):
    """
    Generate a new schedule using AI reasoning engine.
    
    This endpoint uses the DSPy-based PlannerService to create an optimized schedule.
    """
    # Get company data
    company = get_company(request.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    employees = get_employees(request.company_id)
    if not employees:
        raise HTTPException(status_code=400, detail="No employees found for this company")
    
    # Get planner service
    service = get_planner_service()
    
    # Generate schedule
    try:
        result = service.generate_weekly_schedule(
            employees=employees,
            active_shifts=company.get("active_shifts", ["Πρωί", "Απόγευμα", "Βράδυ"]),
            roles=company.get("roles", []),
            constraints=company.get("rules", {}),
            week_start=request.week_start
        )
        
        return {
            "success": True,
            "schedule": result["schedule"],
            "reasoning": result["reasoning"],
            "metrics": result["metrics"],
            "violations": result["violations"],
            "recommendations": result["recommendations"],
            "metadata": result["metadata"]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schedule generation failed: {str(e)}")


@app.get("/api/schedule/{company_id}")
async def get_schedule(company_id: int, start_date: str, end_date: str):
    """Get schedule for a date range"""
    company = get_company(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    schedule = get_schedule_range(company_id, start_date, end_date)
    return {"schedule": schedule}


@app.post("/api/schedule/save")
async def save_schedule(request: ScheduleSaveRequest):
    """Save schedule assignments"""
    company = get_company(request.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    bulk_save_week_schedule(request.company_id, request.assignments)
    
    return {"success": True, "saved": len(request.assignments)}


@app.post("/api/schedule/analyze")
async def analyze_schedule(company_id: int, schedule: List[Dict[str, Any]]):
    """Analyze a schedule for violations"""
    company = get_company(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    employees = get_employees(company_id)
    service = get_planner_service()
    
    result = service.analyze_violations(
        schedule=schedule,
        constraints=company.get("rules", {}),
        employees=employees
    )
    
    return result


# ============================================================================
# Reasoning/Explainability Endpoints
# ============================================================================

@app.get("/api/reasoning/version")
async def get_reasoning_version():
    """Get current reasoning artifact version and metadata"""
    service = get_planner_service()
    return service.get_version_info()


@app.post("/api/reasoning/explain")
async def explain_decision(
    assignment: Dict[str, Any],
    alternatives: List[Dict[str, Any]],
    schedule_context: List[Dict[str, Any]],
    constraints: Dict[str, Any]
):
    """
    Explain why a specific scheduling decision was made.
    
    This is critical for transparency and compliance.
    """
    service = get_planner_service()
    
    result = service.explain_decision(
        assignment=assignment,
        alternatives=alternatives,
        schedule_context=schedule_context,
        constraints=constraints
    )
    
    return result


# ============================================================================
# Development/Testing Endpoints
# ============================================================================

@app.get("/api/dev/golden-datasets")
async def list_golden_datasets():
    """List available golden test datasets (dev only)"""
    if os.getenv("APP_ENV") == "prod":
        raise HTTPException(status_code=403, detail="Not available in production")
    
    golden_dir = Path(__file__).parent / "datasets" / "golden"
    datasets = [f.stem for f in golden_dir.glob("*.json")]
    
    return {"datasets": datasets}


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("APP_ENV", "dev") == "dev"
    
    print(f"🚀 Starting Shift Planner API on port {port}")
    print(f"📚 Docs available at: http://localhost:{port}/docs")
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=port,
        reload=reload,
        log_level="info"
    )
