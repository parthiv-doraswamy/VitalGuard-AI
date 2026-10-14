import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { SimulationProvider } from './store/SimulationContext.tsx';
import { DashboardPage } from './pages/DashboardPage.tsx';
import { PatientsPage } from './pages/PatientsPage.tsx';
import { PatientDetailPage } from './pages/PatientDetailPage.tsx';
import { AlertsPage } from './pages/AlertsPage.tsx';
import { AnalyticsPage } from './pages/AnalyticsPage.tsx';
import { SettingsPage } from './pages/SettingsPage.tsx';
import { NotFoundPage } from './pages/NotFoundPage.tsx';
import { LoginPage } from './pages/LoginPage.tsx';
import { ProtectedRoute } from './components/ProtectedRoute.tsx';

export function App() {
  return (
    <SimulationProvider>
      {/* HashRouter keeps client-side routes after #, so static hosting never requests /dashboard from the server. */}
      <HashRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/patients" element={<PatientsPage />} />
            <Route path="/patients/:patientId" element={<PatientDetailPage />} />
            <Route path="/alerts" element={<AlertsPage />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </HashRouter>
    </SimulationProvider>
  );
}
