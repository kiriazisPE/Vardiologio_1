import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import ScheduleView from './pages/ScheduleView';
import EmployeeManager from './pages/EmployeeManager';
import CompanySettings from './pages/CompanySettings';
import Analytics from './pages/Analytics';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<ScheduleView />} />
          <Route path="/employees" element={<EmployeeManager />} />
          <Route path="/settings" element={<CompanySettings />} />
          <Route path="/analytics" element={<Analytics />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
