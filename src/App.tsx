import { lazy, Suspense } from 'react';
import { HashRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { SimulationProvider } from './store/SimulationContext.tsx';
import { ProtectedRoute, RequirePermission } from './components/ProtectedRoute.tsx';
import { LiveEventsProvider } from './services/LiveEventsProvider.tsx';

const DashboardPage = lazy(() => import('./pages/DashboardPage.tsx').then(m => ({ default: m.DashboardPage })));
const PatientsPage = lazy(() => import('./pages/PatientsPage.tsx').then(m => ({ default: m.PatientsPage })));
const PatientDetailPage = lazy(() => import('./pages/PatientDetailPage.tsx').then(m => ({ default: m.PatientDetailPage })));
const AlertsPage = lazy(() => import('./pages/AlertsPage.tsx').then(m => ({ default: m.AlertsPage })));
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage.tsx').then(m => ({ default: m.AnalyticsPage })));
const SettingsPage = lazy(() => import('./pages/SettingsPage.tsx').then(m => ({ default: m.SettingsPage })));
const HistoryPage = lazy(() => import('./pages/HistoryPage.tsx').then(m => ({ default: m.HistoryPage })));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage.tsx').then(m => ({ default: m.NotFoundPage })));
const LoginPage = lazy(() => import('./pages/LoginPage.tsx').then(m => ({ default: m.LoginPage })));
const LiveDemoPage = lazy(() => import('./pages/LiveDemoPage.tsx').then(m => ({ default: m.LiveDemoPage })));
const ModelPerformancePage = lazy(() => import('./pages/ModelPerformancePage.tsx').then(m => ({ default: m.ModelPerformancePage })));

function RouteLoading() {
  return <div className="min-h-screen grid place-items-center bg-slate-50 text-slate-600" role="status" aria-live="polite">Loading VitalGuard…</div>;
}

function LiveLayout() {
  return <LiveEventsProvider><Outlet /></LiveEventsProvider>;
}

export function App() {
  return (
    <SimulationProvider>
      <HashRouter>
        <Suspense fallback={<RouteLoading />}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<LiveLayout />}>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/live-demo" element={<RequirePermission permission="liveDemo"><LiveDemoPage /></RequirePermission>} />
                <Route path="/patients" element={<PatientsPage />} />
                <Route path="/patients/:patientId" element={<PatientDetailPage />} />
                <Route path="/alerts" element={<AlertsPage />} />
                <Route path="/history" element={<RequirePermission permission="history"><HistoryPage /></RequirePermission>} />
                <Route path="/analytics" element={<RequirePermission permission="analytics"><AnalyticsPage /></RequirePermission>} />
                <Route path="/model-performance" element={<RequirePermission permission="modelPerformance"><ModelPerformancePage /></RequirePermission>} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Route>
          </Routes>
        </Suspense>
      </HashRouter>
    </SimulationProvider>
  );
}
