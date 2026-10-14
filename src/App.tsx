import { HashRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
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
import { LiveDemoPage } from './pages/LiveDemoPage.tsx';
import { LiveEventsProvider } from './services/LiveEventsProvider.tsx';

// One backend live connection per signed-in tab, shared by every page so the
// event log and an active producer survive navigation.
function LiveLayout() {
  return <LiveEventsProvider><Outlet /></LiveEventsProvider>;
}

export function App() {
  return (
    <SimulationProvider>
      {/* HashRouter keeps client-side routes after #, so static hosting never requests /dashboard from the server. */}
      <HashRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<LiveLayout />}>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/live-demo" element={<LiveDemoPage />} />
              <Route path="/patients" element={<PatientsPage />} />
              <Route path="/patients/:patientId" element={<PatientDetailPage />} />
              <Route path="/alerts" element={<AlertsPage />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Route>
        </Routes>
      </HashRouter>
    </SimulationProvider>
  );
}
