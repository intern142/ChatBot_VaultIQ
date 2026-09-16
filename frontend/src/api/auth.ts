/*
 * Common API layer facade.
 *
 * Every screen talks to `authApi` from here — never to the mock or the real
 * backend directly. The active driver is chosen once from `src/api/config.ts`:
 *
 *   VITE_API_MODE=mock (default) → in-browser mock backend
 *   VITE_API_MODE=real           → HTTP calls to VITE_API_BASE
 *
 * UI code is completely unaware of which backend is active.
 */
import { isMockMode } from './config';
import { mockAuthApi } from './mock';
import { realAuthApi } from './real';

export const authApi = isMockMode ? mockAuthApi : realAuthApi;

export { API_MODE, API_BASE, isMockMode } from './config';
export * from './types';