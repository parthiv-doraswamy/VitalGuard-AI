import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { LoginPage } from './LoginPage';
import { ProtectedRoute, RequirePermission } from '../components/ProtectedRoute';
import { authHeaders, can, getSession, openOfflineSession } from '../services/auth';

afterEach(() => { vi.unstubAllGlobals(); });

function renderLogin() {
  render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/dashboard" element={<div>Dashboard mock</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('demo role login', () => {
  it('signs in against the backend and keeps the signed token', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({
      token: 'signed.token', expires_in: 3600,
      user: { username: 'nurse.demo', display_name: 'Nurse Kavitha (demo)', role: 'nurse', wards: ['ICU'] },
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    renderLogin();

    fireEvent.click(screen.getByRole('button', { name: /Nurse/i }));
    expect(screen.getByLabelText(/Username/i)).toHaveValue('nurse.demo');
    expect(screen.getByLabelText(/Demo password/i)).toHaveValue('demo-access');
    expect(screen.getByTestId('role-access')).toHaveTextContent(/acknowledgement/);
    fireEvent.click(screen.getByRole('button', { name: /Open demo workspace/i }));

    expect(await screen.findByText('Dashboard mock')).toBeInTheDocument();
    expect(getSession()).toMatchObject({ role: 'nurse', username: 'nurse.demo', token: 'signed.token' });
    expect(authHeaders()).toEqual({ Authorization: 'Bearer signed.token' });
  });

  it('falls back to an offline session (no token) when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch'); }));
    renderLogin();
    fireEvent.click(screen.getByRole('button', { name: /Doctor/i }));
    fireEvent.change(screen.getByLabelText(/Doctor account/i), { target: { value: 'dr.khan' } });
    fireEvent.click(screen.getByRole('button', { name: /Open demo workspace/i }));

    expect(await screen.findByText('Dashboard mock')).toBeInTheDocument();
    expect(getSession()).toMatchObject({ role: 'doctor', username: 'dr.khan', token: null, wards: ['Emergency'] });
  });

  it('shows the backend error for wrong credentials', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'Unknown username or wrong password' }), { status: 401 })));
    renderLogin();
    fireEvent.change(screen.getByLabelText(/Demo password/i), { target: { value: 'nope' } });
    fireEvent.click(screen.getByRole('button', { name: /Open demo workspace/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/wrong password/i);
    expect(getSession()).toBeNull();
  });

  it('requires a demo role selection with matching credentials', () => {
    renderLogin();
    fireEvent.change(screen.getByLabelText(/Username/i), { target: { value: 'someone-else' } });
    fireEvent.click(screen.getByRole('button', { name: /Open demo workspace/i }));

    expect(screen.getByRole('alert')).toHaveTextContent(/Choose a demo role/i);
    expect(screen.queryByText('Dashboard mock')).not.toBeInTheDocument();
  });

  it('redirects to login when no session exists', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="/login" element={<div>Login route</div>} />
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<div>Dashboard mock</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText('Login route')).toBeInTheDocument();
    expect(screen.queryByText('Dashboard mock')).not.toBeInTheDocument();
  });
});

describe('role-based access', () => {
  it('applies the permission table per role', () => {
    const doctor = { role: 'doctor' as const };
    const nurse = { role: 'nurse' as const };
    expect([can(doctor, 'liveDemo'), can(doctor, 'resolveAlert'), can(doctor, 'modelPerformance')]).toEqual([false, true, true]);
    expect([can(nurse, 'liveDemo'), can(nurse, 'resolveAlert'), can(nurse, 'modelPerformance')]).toEqual([true, false, false]);
    expect(can({ role: 'admin' }, 'systemSettings')).toBe(true);
    expect(can(null, 'dashboard')).toBe(false);
  });

  it('blocks pages a role cannot open', () => {
    openOfflineSession('doctor.demo');
    render(
      <MemoryRouter>
        <RequirePermission permission="liveDemo"><div>Live demo mock</div></RequirePermission>
      </MemoryRouter>,
    );
    expect(screen.queryByText('Live demo mock')).not.toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent(/Not available for your role/);
  });
});
