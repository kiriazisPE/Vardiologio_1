import { useState, useEffect } from 'react';
import api from '../services/api';
import type { Company, ScheduleEntry, Violation, ScheduleMetrics } from '../types';
import './ScheduleView.css';

export default function ScheduleView() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);
  const [schedule, setSchedule] = useState<ScheduleEntry[]>([]);
  const [violations, setViolations] = useState<Violation[]>([]);
  const [metrics, setMetrics] = useState<ScheduleMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [startDate, setStartDate] = useState(new Date().toISOString().split('T')[0]);
  const [numDays, setNumDays] = useState(7);

  useEffect(() => {
    loadCompanies();
  }, []);

  useEffect(() => {
    if (selectedCompanyId) {
      loadSchedule();
    }
  }, [selectedCompanyId, startDate]);

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

  const loadSchedule = async () => {
    if (!selectedCompanyId) return;
    
    setLoading(true);
    try {
      const endDate = new Date(startDate);
      endDate.setDate(endDate.getDate() + numDays);
      
      const data = await api.getSchedule(
        selectedCompanyId,
        startDate,
        endDate.toISOString().split('T')[0]
      );
      setSchedule(data);
    } catch (error) {
      console.error('Failed to load schedule:', error);
    } finally {
      setLoading(false);
    }
  };

  const generateSchedule = async () => {
    if (!selectedCompanyId) return;
    
    setGenerating(true);
    try {
      const result = await api.generateSchedule({
        company_id: selectedCompanyId,
        start_date: startDate,
        num_days: numDays,
      });
      
      setSchedule(result.schedule);
      setViolations(result.violations);
      setMetrics(result.metrics);
      
      // Auto-save if no hard violations
      if (result.violations.filter(v => v.type === 'hard').length === 0) {
        await api.saveSchedule(selectedCompanyId, result.schedule);
      }
    } catch (error) {
      console.error('Failed to generate schedule:', error);
      alert('Failed to generate schedule. Check console for details.');
    } finally {
      setGenerating(false);
    }
  };

  const saveSchedule = async () => {
    if (!selectedCompanyId) return;
    
    try {
      await api.saveSchedule(selectedCompanyId, schedule);
      alert('Schedule saved successfully!');
    } catch (error) {
      console.error('Failed to save schedule:', error);
      alert('Failed to save schedule.');
    }
  };

  const groupedSchedule = schedule.reduce((acc, entry) => {
    if (!acc[entry.date]) {
      acc[entry.date] = [];
    }
    acc[entry.date].push(entry);
    return acc;
  }, {} as Record<string, ScheduleEntry[]>);

  return (
    <div className="schedule-view">
      <header className="page-header">
        <h1>📅 Schedule Management</h1>
        <p>AI-powered shift scheduling with constraint checking</p>
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

        <div className="control-group">
          <label>Start Date:</label>
          <input 
            type="date" 
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
        </div>

        <div className="control-group">
          <label>Duration:</label>
          <select value={numDays} onChange={(e) => setNumDays(Number(e.target.value))}>
            <option value={7}>1 Week</option>
            <option value={14}>2 Weeks</option>
            <option value={21}>3 Weeks</option>
            <option value={28}>4 Weeks</option>
          </select>
        </div>

        <button 
          className="btn btn-primary" 
          onClick={generateSchedule}
          disabled={generating || !selectedCompanyId}
        >
          {generating ? '🤖 Generating with DSPy...' : '✨ Generate Schedule'}
        </button>

        <button 
          className="btn btn-secondary" 
          onClick={saveSchedule}
          disabled={schedule.length === 0}
        >
          💾 Save Schedule
        </button>
      </div>

      {violations.length > 0 && (
        <div className="violations-panel">
          <h3>⚠️ Violations ({violations.length})</h3>
          <div className="violations-list">
            {violations.map((v, idx) => (
              <div key={idx} className={`violation violation-${v.severity}`}>
                <span className="violation-type">{v.type}</span>
                <span className="violation-message">{v.message}</span>
                {v.employee_name && <span className="violation-employee">Employee: {v.employee_name}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {metrics && (
        <div className="metrics-panel">
          <h3>📊 Schedule Metrics</h3>
          <div className="metrics-grid">
            <div className="metric">
              <span className="metric-label">Total Shifts</span>
              <span className="metric-value">{metrics.total_shifts}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Coverage</span>
              <span className="metric-value">{(metrics.coverage_percentage * 100).toFixed(1)}%</span>
            </div>
            <div className="metric">
              <span className="metric-label">Fairness Score</span>
              <span className="metric-value">{(metrics.fairness_score * 100).toFixed(1)}%</span>
            </div>
            <div className="metric">
              <span className="metric-label">Hard Violations</span>
              <span className={`metric-value ${metrics.hard_violations > 0 ? 'error' : 'success'}`}>
                {metrics.hard_violations}
              </span>
            </div>
          </div>
        </div>
      )}

      <div className="schedule-grid">
        {loading ? (
          <p>Loading schedule...</p>
        ) : Object.keys(groupedSchedule).length === 0 ? (
          <div className="empty-state">
            <p>No schedule generated yet.</p>
            <p>Click "Generate Schedule" to create one with AI.</p>
          </div>
        ) : (
          Object.entries(groupedSchedule).map(([date, entries]) => (
            <div key={date} className="day-column">
              <h4>{new Date(date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}</h4>
              <div className="shifts-list">
                {entries.map(entry => (
                  <div key={entry.id} className="shift-card">
                    <div className="shift-name">{entry.shift_name}</div>
                    <div className="employee-name">Employee #{entry.employee_id}</div>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
