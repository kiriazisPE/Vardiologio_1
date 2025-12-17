import { useState, useEffect } from 'react';
import api from '../services/api';
import type { Company, CompanyUpdate } from '../types';
import './CompanySettings.css';

export default function CompanySettings() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadCompanies();
  }, []);

  const loadCompanies = async () => {
    setLoading(true);
    try {
      const data = await api.getCompanies();
      setCompanies(data);
      if (data.length > 0) {
        setSelectedCompany(data[0]);
      }
    } catch (error) {
      console.error('Failed to load companies:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedCompany) return;

    const formData = new FormData(e.currentTarget);
    const updates: CompanyUpdate = {
      name: formData.get('name') as string,
      active_shifts: (formData.get('active_shifts') as string).split('\n').filter(Boolean),
      roles: (formData.get('roles') as string).split('\n').filter(Boolean),
      work_model: formData.get('work_model') as string,
    };

    setSaving(true);
    try {
      const updated = await api.updateCompany(selectedCompany.id, updates);
      setSelectedCompany(updated);
      alert('Settings saved successfully!');
      loadCompanies(); // Refresh list
    } catch (error) {
      console.error('Failed to save settings:', error);
      alert('Failed to save settings. Check console for details.');
    } finally {
      setSaving(false);
    }
  };

  const handleCompanySelect = (companyId: number) => {
    const company = companies.find(c => c.id === companyId);
    if (company) {
      setSelectedCompany(company);
    }
  };

  if (loading) {
    return <div className="company-settings"><p>Loading...</p></div>;
  }

  return (
    <div className="company-settings">
      <header className="page-header">
        <h1>⚙️ Company Settings</h1>
        <p>Configure shifts, roles, and business rules</p>
      </header>

      <div className="settings-container">
        <aside className="company-selector">
          <h3>Companies</h3>
          <ul className="company-list">
            {companies.map(company => (
              <li 
                key={company.id}
                className={selectedCompany?.id === company.id ? 'active' : ''}
                onClick={() => handleCompanySelect(company.id)}
              >
                {company.name}
              </li>
            ))}
          </ul>
        </aside>

        <div className="settings-form-container">
          {selectedCompany ? (
            <form onSubmit={handleSubmit}>
              <div className="form-section">
                <h3>Basic Information</h3>
                <div className="form-group">
                  <label>Company Name</label>
                  <input 
                    type="text" 
                    name="name" 
                    required 
                    defaultValue={selectedCompany.name}
                  />
                </div>

                <div className="form-group">
                  <label>Work Model</label>
                  <select name="work_model" defaultValue={selectedCompany.work_model}>
                    <option value="5-2">5 days work, 2 days off</option>
                    <option value="6-1">6 days work, 1 day off</option>
                    <option value="4-3">4 days work, 3 days off</option>
                    <option value="custom">Custom</option>
                  </select>
                </div>
              </div>

              <div className="form-section">
                <h3>Active Shifts</h3>
                <p className="section-hint">Enter one shift per line (e.g., "Morning 08:00-16:00")</p>
                <div className="form-group">
                  <textarea 
                    name="active_shifts"
                    rows={8}
                    defaultValue={selectedCompany.active_shifts.join('\n')}
                    placeholder="Morning 08:00-16:00&#10;Afternoon 16:00-00:00&#10;Night 00:00-08:00"
                  />
                </div>
              </div>

              <div className="form-section">
                <h3>Employee Roles</h3>
                <p className="section-hint">Enter one role per line</p>
                <div className="form-group">
                  <textarea 
                    name="roles"
                    rows={6}
                    defaultValue={selectedCompany.roles.join('\n')}
                    placeholder="Nurse&#10;Doctor&#10;Receptionist&#10;Technician"
                  />
                </div>
              </div>

              <div className="form-section">
                <h3>Business Rules</h3>
                <div className="rules-display">
                  {selectedCompany.rules && Object.keys(selectedCompany.rules).length > 0 ? (
                    <pre>{JSON.stringify(selectedCompany.rules, null, 2)}</pre>
                  ) : (
                    <p className="empty-rules">No custom rules configured. Rules are managed via backend.</p>
                  )}
                </div>
              </div>

              <div className="form-actions">
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? '💾 Saving...' : '💾 Save Settings'}
                </button>
              </div>
            </form>
          ) : (
            <div className="empty-state">
              <p>No company selected.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
