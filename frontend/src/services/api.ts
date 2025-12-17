/**
 * API Client for Shift Planner FastAPI Backend
 * 
 * This service provides typed methods for all API endpoints.
 * Never calls OpenAI directly - all AI logic is in the backend.
 */

import axios, { AxiosInstance } from 'axios';
import type {
  Company, CompanyCreate, CompanyUpdate,
  Employee, EmployeeCreate, EmployeeUpdate,
  ScheduleEntry,
  GenerateScheduleRequest, GenerateScheduleResponse,
  AnalyzeViolationsRequest, Violation,
  ExplainDecisionRequest, ExplainDecisionResponse,
  ScheduleMetrics
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      withCredentials: true,
    });
  }

  // ============================================================================
  // Health & Status
  // ============================================================================

  async healthCheck(): Promise<{ status: string; timestamp: string }> {
    const response = await this.client.get('/health');
    return response.data;
  }

  // ============================================================================
  // Companies
  // ============================================================================

  async getCompanies(): Promise<Company[]> {
    const response = await this.client.get('/api/companies');
    return response.data;
  }

  async getCompany(companyId: number): Promise<Company> {
    const response = await this.client.get(`/api/companies/${companyId}`);
    return response.data;
  }

  async createCompany(data: CompanyCreate): Promise<Company> {
    const response = await this.client.post('/api/companies', data);
    return response.data;
  }

  async updateCompany(companyId: number, data: CompanyUpdate): Promise<Company> {
    const response = await this.client.put(`/api/companies/${companyId}`, data);
    return response.data;
  }

  // ============================================================================
  // Employees
  // ============================================================================

  async getEmployees(companyId: number): Promise<Employee[]> {
    const response = await this.client.get(`/api/companies/${companyId}/employees`);
    return response.data;
  }

  async createEmployee(companyId: number, data: EmployeeCreate): Promise<Employee> {
    const response = await this.client.post(`/api/companies/${companyId}/employees`, data);
    return response.data;
  }

  async updateEmployee(companyId: number, employeeId: number, data: EmployeeUpdate): Promise<Employee> {
    const response = await this.client.put(`/api/companies/${companyId}/employees/${employeeId}`, data);
    return response.data;
  }

  async deleteEmployee(companyId: number, employeeId: number): Promise<{ message: string }> {
    const response = await this.client.delete(`/api/companies/${companyId}/employees/${employeeId}`);
    return response.data;
  }

  // ============================================================================
  // Schedule Management
  // ============================================================================

  async getSchedule(companyId: number, startDate: string, endDate: string): Promise<ScheduleEntry[]> {
    const response = await this.client.get('/api/schedule', {
      params: { company_id: companyId, start_date: startDate, end_date: endDate }
    });
    return response.data;
  }

  async saveSchedule(companyId: number, schedule: ScheduleEntry[]): Promise<{ message: string; saved_count: number }> {
    const response = await this.client.post('/api/schedule', {
      company_id: companyId,
      schedule
    });
    return response.data;
  }

  // ============================================================================
  // AI-Powered Schedule Generation (via DSPy)
  // ============================================================================

  async generateSchedule(request: GenerateScheduleRequest): Promise<GenerateScheduleResponse> {
    const response = await this.client.post('/api/schedule/generate', request);
    return response.data;
  }

  // ============================================================================
  // Reasoning & Explanations
  // ============================================================================

  async analyzeViolations(request: AnalyzeViolationsRequest): Promise<Violation[]> {
    const response = await this.client.post('/api/reasoning/analyze-violations', request);
    return response.data;
  }

  async explainDecision(request: ExplainDecisionRequest): Promise<ExplainDecisionResponse> {
    const response = await this.client.post('/api/reasoning/explain', request);
    return response.data;
  }

  // ============================================================================
  // Metrics
  // ============================================================================

  async getScheduleMetrics(companyId: number, schedule: ScheduleEntry[]): Promise<ScheduleMetrics> {
    const response = await this.client.post('/api/schedule/metrics', {
      company_id: companyId,
      schedule
    });
    return response.data;
  }
}

// Export singleton instance
export const api = new ApiClient();
export default api;
