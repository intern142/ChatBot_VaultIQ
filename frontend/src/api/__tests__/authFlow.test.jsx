/*
 * End-to-end auth flows through AuthContext + Login page.
 * These tests do NOT mock the API layer — they exercise the real driver
 * selected by `VITE_API_MODE` (mock by default). The very same file runs
 * against the real backend by setting VITE_API_MODE=real (backend must be
 * up and seeded with the same fixture users).
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider, useAuth } from '../../context/AuthContext';
import Login from '../../pages/Login';
import { describe, it, expect, beforeEach } from 'vitest';

const renderWithAuth = (component) =>
  render(
    <BrowserRouter>
      <AuthProvider>{component}</AuthProvider>
    </BrowserRouter>
  );

const SEEDED = {
  good: ['ORG-12345', 'admin', 'admin@acme.com', 'Admin@123', 'super-admin'],
  badPassword: ['ORG-12345', 'admin', 'admin@acme.com', 'wrong-password', 'super-admin'],
  badOrg: ['ORG-XXXXX', 'admin', 'admin@acme.com', 'Admin@123', 'super-admin'],
  wrongUserType: ['ORG-12345', 'employee', 'employee@acme.com', 'Employee@123', 'super-admin'],
};

describe('AuthContext vs active backend', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  const Harness = () => {
    const { isAuthenticated, role, isLockedOut, failedAttempts, error, login, register } = useAuth();
    return (
      <div>
        <span data-testid="auth">{String(isAuthenticated)}</span>
        <span data-testid="role">{role || 'none'}</span>
        <span data-testid="locked">{String(isLockedOut)}</span>
        <span data-testid="attempts">{failedAttempts}</span>
        <span data-testid="error">{error || 'none'}</span>
        <button onClick={() => login(...SEEDED.good)}>good</button>
        <button onClick={() => login(...SEEDED.badPassword)}>badPassword</button>
        <button onClick={() => login(...SEEDED.badOrg)}>badOrg</button>
        <button onClick={() => login(...SEEDED.wrongUserType)}>wrongUserType</button>
        <button onClick={() => register('ORG-12345', 'flow.user@acme.com', 'Flow@123', 'employee')}>registerGood</button>
      </div>
    );
  };

  it('starts unauthenticated', () => {
    renderWithAuth(<Harness />);
    expect(screen.getByTestId('auth').textContent).toBe('false');
  });

  it('logs in with valid credentials and stores the session', async () => {
    renderWithAuth(<Harness />);
    fireEvent.click(screen.getByText('good'));
    await waitFor(() => expect(screen.getByTestId('auth').textContent).toBe('true'), { timeout: 3000 });
    expect(screen.getByTestId('role').textContent).toBe('super-admin');
  });

  it('shows generic error and increments attempts on wrong password', async () => {
    renderWithAuth(<Harness />);
    fireEvent.click(screen.getByText('badPassword'));
    await waitFor(() => expect(screen.getByTestId('attempts').textContent).toBe('1'), { timeout: 3000 });
    expect(screen.getByTestId('error').textContent).toBe('Invalid credentials');
    expect(screen.getByTestId('auth').textContent).toBe('false');
  });

  it('shows generic error for unknown organization', async () => {
    renderWithAuth(<Harness />);
    fireEvent.click(screen.getByText('badOrg'));
    await waitFor(() => expect(screen.getByTestId('error').textContent).toBe('Invalid credentials'), { timeout: 3000 });
  });

  it('shows generic error for role/userType mismatch', async () => {
    renderWithAuth(<Harness />);
    fireEvent.click(screen.getByText('wrongUserType'));
    await waitFor(() => expect(screen.getByTestId('error').textContent).toBe('Invalid credentials'), { timeout: 3000 });
    expect(screen.getByTestId('auth').textContent).toBe('false');
  });

  it('registers a new employee and authenticates the session', async () => {
    renderWithAuth(<Harness />);
    fireEvent.click(screen.getByText('registerGood'));
    await waitFor(() => expect(screen.getByTestId('auth').textContent).toBe('true'), { timeout: 3000 });
    expect(screen.getByTestId('role').textContent).toBe('employee');
  });

  it('locks the account after 5 failed attempts', async () => {
    renderWithAuth(<Harness />);
    const btn = screen.getByText('badPassword');
    for (let i = 0; i < 5; i++) {
      fireEvent.click(btn);
      await waitFor(() => expect(screen.getByTestId('attempts').textContent).toBe(String(i + 1)), { timeout: 3000 });
    }
    expect(screen.getByTestId('locked').textContent).toBe('true');
  });
});

describe('Login page validation vs active backend', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it('shows "Invalid credentials" when a field is left empty (no API call needed)', async () => {
    renderWithAuth(<Login />);
    fireEvent.click(screen.getByRole('button', { name: /Sign In/i }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Invalid credentials'));
  });

  it('shows "Invalid credentials" for wrong credentials and keeps the form on screen', async () => {
    renderWithAuth(<Login />);
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'admin' } });
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'admin@acme.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrong-password' } });
    fireEvent.change(screen.getByLabelText('Organization Code'), { target: { value: 'ORG-12345' } });
    fireEvent.click(screen.getByLabelText('Super Admin'));
    fireEvent.click(screen.getByRole('button', { name: /Sign In/i }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Invalid credentials'));
    expect(screen.getByRole('button', { name: /Sign In/i })).toBeInTheDocument();
  });
});