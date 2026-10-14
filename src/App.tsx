import { lazy, Suspense } from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { SimulationProvider } from './store/SimulationContext.tsx';
import { ProtectedRoute } from './components/ProtectedRoute.tsx';

const DashboardPage = lazy(() => import('./pages/DashboardPage.tsx').then(m => ({ default: m.DashboardPage })));
const PatientsPage = lazy(() => import('./pages/PatientsPage.tsx').then(m => ({ default: m.PatientsPage })));
const PatientDetailPage = lazy(() => import('./pages/PatientDetailPage.tsx').then(m => ({ default: m.PatientDetailPage })));
const AlertsPage = lazy(() => import('./pages/AlertsPage.tsx').then(m => ({ default: m.AlertsPage })));
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage.tsx').then(m => ({ default: m.AnalyticsPage })));
const SettingsPage = lazy(() => import('./pages/SettingsPage.tsx').then(m => ({ default: m.SettingsPage })));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage.tsx').then(m => ({ default: m.NotFoundPage })));
const LoginPage = lazy(() => import('./pages/LoginPage.tsx').then(m => ({ default: m.LoginPage })));

function RouteLoading() {
  return <div className="min-h-screen grid place-items-center bg-slate-50 text-slate-600" role="status" aria-live="polite">Loading VitalGuard…</div>;
}

export function App() {
  return (
    <SimulationProvider>
      {/* HashRouter avoids static-hosting route 404s; lazy pages split the initial bundle by route. */}
      <HashRouter>
        <Suspense fallback={<RouteLoading />}>
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
        </Suspense>
      </HashRouter>
    </SimulationProvider>
  );
}
