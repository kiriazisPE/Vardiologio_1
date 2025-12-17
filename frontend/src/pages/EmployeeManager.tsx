import { useState, useEffect } from 'react';
import api from '../services/api';
import type { Company, Employee, EmployeeCreate, EmployeeUpdate } from '../types';
import './EmployeeManager.css';

export default function EmployeeManager() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState<Employee | null>(null);

  useEffect(() => {
    loadCompanies();
  }, []);

  useEffect(() => {
    if (selectedCompanyId) {
      loadEmployees();
    }
  }, [selectedCompanyId]);

  const loadCompanies = async () => {
    try {
      const data = await api.getCompanies();
      setCompanies(data);
      if (data.length > 0) {
        setSelectedCompanyId(data[0].id);
      }
    } catch (error) {
      console.error('Failed to load companies:', error);
    }
  };

  const loadEmployees = async () => {
    if (!selectedCompanyId) return;
    
    setLoading(true);
    try {
      const data = await api.getEmployees(selectedCompanyId);
      setEmployees(data);
    } catch (error) {
      console.error('Failed to load employees:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedCompanyId) return;

    const formData = new FormData(e.currentTarget);
    const employeeData = {
      name: formData.get('name') as string,
      roles: (formData.get('roles') as string).split(',').map(r => r.trim()),
      max_hours_week: Number(formData.get('max_hours_week')) || undefined,
      min_hours_week: Number(formData.get('min_hours_week')) || undefined,
      max_shifts_week: Number(formData.get('max_shifts_week')) || undefined,
      min_shifts_week: Number(formData.get('min_shifts_week')) || undefined,
      preferred_days: (formData.get('preferred_days') as string).split(',').map(d => d.trim()).filter(Boolean),
      avoid_days: (formData.get('avoid_days') as string).split(',').map(d => d.trim()).filter(Boolean),
    };

    try {
      if (editingEmployee) {
        await api.updateEmployee(selectedCompanyId, editingEmployee.id, employeeData as EmployeeUpdate);
      } else {
        await api.createEmployee(selectedCompanyId, employeeData as EmployeeCreate);
      }
      
      setShowForm(false);
      setEditingEmployee(null);
      loadEmployees();
    } catch (error) {
      console.error('Failed to save employee:', error);
      alert('Failed to save employee. Check console for details.');
    }
  };

  const handleEdit = (employee: Employee) => {
    setEditingEmployee(employee);
    setShowForm(true);
  };

  const handleDelete = async (employeeId: number) => {
    if (!selectedCompanyId) return;
    if (!confirm('Are you sure you want to delete this employee?')) return;

    try {
      await api.deleteEmployee(selectedCompanyId, employeeId);
      loadEmployees();
    } catch (error) {
      console.error('Failed to delete employee:', error);
      alert('Failed to delete employee.');
    }
  };

  const handleCancel = () => {
    setShowForm(false);
    setEditingEmployee(null);
  };

  return (
    <div className="employee-manager">
      <header className="page-header">
        <div>
          <h1>👥 Employee Management</h1>
          <p>Manage your team members and their preferences</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(true)}>
          ➕ Add Employee
        </button>
      </header>

      <div className="controls-panel">
        <div className="control-group">
          <label>Company:</label>
          <select 
            value={selectedCompanyId || ''} 
            onChange={(e) => setSelectedCompanyId(Number(e.target.value))}
          >
            {companies.map(company => (
              <option key={company.id} value={company.id}>{company.name}</option>
            ))}
          </select>
        </div>
      </div>

      {showForm && (
        <div className="modal-overlay" onClick={handleCancel}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>{editingEmployee ? 'Edit Employee' : 'Add New Employee'}</h2>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label>Name *</label>
                <input 
                  type="text" 
                  name="name" 
                  required 
                  defaultValue={editingEmployee?.name}
                />
              </div>

              <div className="form-group">
                <label>Roles * (comma-separated)</label>
                <input 
                  type="text" 
                  name="roles" 
                  required 
                  placeholder="nurse, doctor"
                  defaultValue={editingEmployee?.roles.join(', ')}
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Min Hours/Week</label>
                  <input 
                    type="number" 
                    name="min_hours_week"
                    min="0"
                    defaultValue={editingEmployee?.min_hours_week}
                  />
                </div>
                <div className="form-group">
                  <label>Max Hours/Week</label>
                  <input 
                    type="number" 
                    name="max_hours_week"
                    min="0"
                    defaultValue={editingEmployee?.max_hours_week}
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Min Shifts/Week</label>
                  <input 
                    type="number" 
                    name="min_shifts_week"
                    min="0"
                    defaultValue={editingEmployee?.min_shifts_week}
                  />
                </div>
                <div className="form-group">
                  <label>Max Shifts/Week</label>
                  <input 
                    type="number" 
                    name="max_shifts_week"
                    min="0"
                    defaultValue={editingEmployee?.max_shifts_week}
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Preferred Days (comma-separated)</label>
                <input 
                  type="text" 
                  name="preferred_days"
                  placeholder="Monday, Wednesday"
                  defaultValue={editingEmployee?.preferred_days.join(', ')}
                />
              </div>

              <div className="form-group">
                <label>Avoid Days (comma-separated)</label>
                <input 
                  type="text" 
                  name="avoid_days"
                  placeholder="Saturday, Sunday"
                  defaultValue={editingEmployee?.avoid_days.join(', ')}
                />
              </div>

              <div className="form-actions">
                <button type="button" className="btn btn-secondary" onClick={handleCancel}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  {editingEmployee ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="employees-grid">
        {loading ? (
          <p>Loading employees...</p>
        ) : employees.length === 0 ? (
          <div className="empty-state">
            <p>No employees found.</p>
            <p>Add your first employee to get started.</p>
          </div>
        ) : (
          employees.map(employee => (
            <div key={employee.id} className="employee-card">
              <div className="employee-header">
                <h3>{employee.name}</h3>
                <div className="employee-actions">
                  <button className="btn-icon" onClick={() => handleEdit(employee)} title="Edit">
                    ✏️
                  </button>
                  <button className="btn-icon" onClick={() => handleDelete(employee.id)} title="Delete">
                    🗑️
                  </button>
                </div>
              </div>
              
              <div className="employee-details">
                <div className="detail-item">
                  <span className="detail-label">Roles:</span>
                  <span className="detail-value">{employee.roles.join(', ')}</span>
                </div>
                
                {(employee.min_hours_week || employee.max_hours_week) && (
                  <div className="detail-item">
                    <span className="detail-label">Hours/Week:</span>
                    <span className="detail-value">
                      {employee.min_hours_week || 0} - {employee.max_hours_week || '∞'}
                    </span>
                  </div>
                )}
                
                {(employee.min_shifts_week || employee.max_shifts_week) && (
                  <div className="detail-item">
                    <span className="detail-label">Shifts/Week:</span>
                    <span className="detail-value">
                      {employee.min_shifts_week || 0} - {employee.max_shifts_week || '∞'}
                    </span>
                  </div>
                )}
                
                {employee.preferred_days.length > 0 && (
                  <div className="detail-item">
                    <span className="detail-label">Prefers:</span>
                    <span className="detail-value">{employee.preferred_days.join(', ')}</span>
                  </div>
                )}
                
                {employee.avoid_days.length > 0 && (
                  <div className="detail-item">
                    <span className="detail-label">Avoids:</span>
                    <span className="detail-value avoid">{employee.avoid_days.join(', ')}</span>
                  </div>
                )}
              </div>
              
              <div className={`employee-status ${employee.active ? 'active' : 'inactive'}`}>
                {employee.active ? '✓ Active' : '⊘ Inactive'}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
