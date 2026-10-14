import { beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { LoginPage } from './LoginPage';
import { ProtectedRoute } from '../components/ProtectedRoute';

beforeEach(() => {
  sessionStorage.clear();
});

describe('demo role login', () => {
  it('fills the selected role credentials and opens the dashboard', () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<div>Dashboard mock</div>} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: /Nurse/i }));

    expect(screen.getByLabelText(/Username/i)).toHaveValue('nurse.demo');
    expect(screen.getByLabelText(/Demo password/i)).toHaveValue('demo-access');

    fireEvent.click(screen.getByRole('button', { name: /Open demo workspace/i }));

    expect(screen.getByText('Dashboard mock')).toBeInTheDocument();
    expect(JSON.parse(sessionStorage.getItem('vg-demo-session') || '{}')).toMatchObject({
      role: 'nurse',
      username: 'nurse.demo',
    });
  });

  it('requires a demo role selection with matching credentials', () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<div>Dashboard mock</div>} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText(/Username/i), { target: { value: 'someone-else' } });
    fireEvent.click(screen.getByRole('button', { name: /Open demo workspace/i }));

    expect(screen.getByRole('alert')).toHaveTextContent(/Choose a demo role/i);
    expect(screen.queryByText('Dashboard mock')).not.toBeInTheDocument();
  });

  it('redirects to login when no demo session exists', () => {
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
