import { Navigate, Outlet } from 'react-router-dom';

export function ProtectedRoute() {
  let authenticated = false;
  try {
    const session = JSON.parse(sessionStorage.getItem('vg-demo-session') || 'null') as { role?: string } | null;
    authenticated = !!session && ['admin', 'nurse', 'doctor'].includes(session.role || '');
  } catch {
    sessionStorage.removeItem('vg-demo-session');
  }
  return authenticated ? <Outlet /> : <Navigate to="/login" replace />;
}
