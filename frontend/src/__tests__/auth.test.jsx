import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider, useAuth } from '../context/AuthContext';
import Login from '../pages/Login';
import Register from '../pages/Register';
import { LockoutBanner } from '../components/LockoutBanner';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

vi.mock('../api/auth', () => ({
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    refresh: vi.fn(),
    logout: vi.fn(),
    verify: vi.fn(),
  },
}));

import { authApi } from '../api/auth';

const renderWithAuth = (component) => {
  return render(
    <BrowserRouter>
      <AuthProvider>
        {component}
      </AuthProvider>
    </BrowserRouter>
  );
};

describe('LockoutBanner', () => {
  it('renders nothing when lockoutUntil is 0', () => {
    renderWithAuth(<LockoutBanner lockoutUntil={0} />);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('renders countdown when lockoutUntil is in future', () => {
    const future = Date.now() + 60000;
    renderWithAuth(<LockoutBanner lockoutUntil={future} />);
    expect(screen.getByRole('alert')).toHaveTextContent(/Try again in/);
  });

  it('calls onClose when lockout expires', async () => {
    const onClose = vi.fn();
    const nearFuture = Date.now() + 50;
    renderWithAuth(<LockoutBanner lockoutUntil={nearFuture} onClose={onClose} />);
    await waitFor(() => expect(onClose).toHaveBeenCalled(), { timeout: 2000 });
  });
});

describe('Login', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.clearAllMocks();
    authApi.login.mockRejectedValue(new Error('LOGIN_FAILED'));
  });

  it('renders org code, email, password fields', () => {
    renderWithAuth(<Login />);
    expect(screen.getByLabelText('Organization Code')).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
  });

  it('submit button exists and is clickable', () => {
    renderWithAuth(<Login />);
    expect(screen.getByRole('button', { name: /Sign In/i })).toBeInTheDocument();
  });
});

describe('Register', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.clearAllMocks();
    authApi.register.mockRejectedValue(new Error('LOGIN_FAILED'));
  });

  it('renders org code, email, password, role select', () => {
    renderWithAuth(<Register />);
    expect(screen.getByLabelText('Organization Code')).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
    expect(screen.getByLabelText('Role')).toBeInTheDocument();
  });

  it('submit button exists', () => {
    renderWithAuth(<Register />);
    expect(screen.getByRole('button', { name: /Create Account/i })).toBeInTheDocument();
  });
});

describe('AuthContext states', () => {
  const TestComponent = () => {
    const { isAuthenticated, isLockedOut, failedAttempts, lockoutUntil, error, login, register, logout, clearError } = useAuth();
    return (
      <div>
        <span data-testid="authenticated">{String(isAuthenticated)}</span>
        <span data-testid="locked">{String(isLockedOut)}</span>
        <span data-testid="attempts">{failedAttempts}</span>
        <span data-testid="lockoutUntil">{lockoutUntil}</span>
        <span data-testid="error">{error || 'none'}</span>
        <button onClick={() => login('ORG-1', 'a@b.com', 'pass')}>Login</button>
        <button onClick={() => register('ORG-1', 'a@b.com', 'pass', 'employee')}>Register</button>
        <button onClick={logout}>Logout</button>
        <button onClick={clearError}>ClearError</button>
      </div>
    );
  };

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.clearAllMocks();
    authApi.login.mockRejectedValue(new Error('LOGIN_FAILED'));
    authApi.register.mockRejectedValue(new Error('LOGIN_FAILED'));
  });

  it('starts unauthenticated', () => {
    renderWithAuth(<TestComponent />);
    expect(screen.getByTestId('authenticated').textContent).toBe('false');
  });

  it('increments failed attempts on login failure', async () => {
    const { getByTestId, getByRole } = renderWithAuth(<TestComponent />);
    fireEvent.click(getByRole('button', { name: /Login/i }));
    await waitFor(() => expect(getByTestId('attempts').textContent).toBe('1'), { timeout: 10000 });
  });

  it('locks out after 5 failures', async () => {
    const { getByTestId, getByRole } = renderWithAuth(<TestComponent />);
    for (let i = 0; i < 5; i++) {
      fireEvent.click(getByRole('button', { name: /Login/i }));
      await waitFor(() => expect(getByTestId('attempts').textContent).toBe(String(i + 1)), { timeout: 10000 });
    }
    expect(getByTestId('locked').textContent).toBe('true');
  });

  it('clears error on clearError', async () => {
    const { getByTestId, getByRole } = renderWithAuth(<TestComponent />);
    fireEvent.click(getByRole('button', { name: /Login/i }));
    await waitFor(() => expect(getByTestId('error').textContent).not.toBe('none'), { timeout: 10000 });
    fireEvent.click(getByRole('button', { name: /ClearError/i }));
    expect(getByTestId('error').textContent).toBe('none');
  });
});