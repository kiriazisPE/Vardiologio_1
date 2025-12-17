/**
 * TypeScript types matching FastAPI Pydantic models
 */

export interface Company {
  id: number;
  name: string;
  active_shifts: string[];
  roles: string[];
  rules: Record<string, any>;
  work_model: string;
  created_at?: string;
}

export interface Employee {
  id: number;
  company_id: number;
  name: string;
  roles: string[];
  max_hours_week?: number;
  min_hours_week?: number;
  max_shifts_week?: number;
  min_shifts_week?: number;
  preferred_days: string[];
  avoid_days: string[];
  preferences: Record<string, any>;
  active: boolean;
  created_at?: string;
}

export interface ScheduleEntry {
  id?: number;
  employee_id: number;
  shift_name: string;
  date: string;
  created_by?: string;
  created_at?: string;
}

export interface GenerateScheduleRequest {
  company_id: number;
  start_date: string;
  num_days: number;
  reasoning_version?: string;
}

export interface GenerateScheduleResponse {
  schedule: ScheduleEntry[];
  violations: Violation[];
  metrics: ScheduleMetrics;
  reasoning?: string;
}

export interface Violation {
  type: "hard" | "soft";
  severity: "critical" | "warning" | "info";
  employee_id?: number;
  employee_name?: string;
  shift?: string;
  date?: string;
  message: string;
  constraint?: string;
}

export interface ScheduleMetrics {
  total_shifts: number;
  shifts_per_employee: Record<string, number>;
  hours_per_employee: Record<string, number>;
  coverage_percentage: number;
  fairness_score: number;
  hard_violations: number;
  soft_violations: number;
}

export interface AnalyzeViolationsRequest {
  company_id: number;
  schedule: ScheduleEntry[];
}

export interface ExplainDecisionRequest {
  company_id: number;
  employee_id: number;
  shift_name: string;
  date: string;
  schedule_context: ScheduleEntry[];
}

export interface ExplainDecisionResponse {
  explanation: string;
  factors: string[];
  confidence: number;
}

export interface CompanyCreate {
  name: string;
}

export interface CompanyUpdate {
  name?: string;
  active_shifts?: string[];
  roles?: string[];
  rules?: Record<string, any>;
  work_model?: string;
}

export interface EmployeeCreate {
  name: string;
  roles: string[];
  max_hours_week?: number;
  min_hours_week?: number;
  max_shifts_week?: number;
  min_shifts_week?: number;
  preferred_days?: string[];
  avoid_days?: string[];
  preferences?: Record<string, any>;
}

export interface EmployeeUpdate {
  name?: string;
  roles?: string[];
  max_hours_week?: number;
  min_hours_week?: number;
  max_shifts_week?: number;
  min_shifts_week?: number;
  preferred_days?: string[];
  avoid_days?: string[];
  preferences?: Record<string, any>;
  active?: boolean;
}
