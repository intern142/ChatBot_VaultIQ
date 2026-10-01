const STORAGE_KEY = 'vaultiq_login_lockout';

interface LockoutState {
  attempts: number;
  lockedUntil: number | null;
}

function readAll(): Record<string, LockoutState> {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
  } catch {
    return {};
  }
}

function writeAll(data: Record<string, LockoutState>): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

const MAX_ATTEMPTS = 5;
const LOCKOUT_MS = 15 * 60 * 1000;

function makeKey(org: string, email: string): string {
  return `${org}:${email}`.toLowerCase();
}

export interface UseLoginLockoutReturn {
  isLocked: () => boolean;
  remainingMs: () => number;
  attempts: () => number;
  recordFailure: () => void;
  recordSuccess: () => void;
  reset: () => void;
}

export function useLoginLockout(org: string, email: string): UseLoginLockoutReturn {
  const key = makeKey(org, email);

  const getState = (): LockoutState => readAll()[key] ?? { attempts: 0, lockedUntil: null };

  const isLocked = (): boolean => {
    const s = getState();
    return s.lockedUntil !== null && s.lockedUntil > Date.now();
  };

  const remainingMs = (): number => {
    const s = getState();
    if (s.lockedUntil === null) return 0;
    return Math.max(0, s.lockedUntil - Date.now());
  };

  const attempts = (): number => getState().attempts;

  const recordFailure = (): void => {
    const all = readAll();
    const s = all[key] ?? { attempts: 0, lockedUntil: null };
    s.attempts += 1;
    if (s.attempts >= MAX_ATTEMPTS) {
      s.lockedUntil = Date.now() + LOCKOUT_MS;
    }
    all[key] = s;
    writeAll(all);
  };

  const recordSuccess = (): void => {
    const all = readAll();
    if (all[key]) {
      delete all[key];
      writeAll(all);
    }
  };

  const reset = (): void => {
    const all = readAll();
    if (all[key]) {
      delete all[key];
      writeAll(all);
    }
  };

  return { isLocked, remainingMs, attempts, recordFailure, recordSuccess, reset };
}