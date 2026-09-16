/*
 * Single environment/configuration switch between the Mock and the Real backend.
 *
 *   VITE_API_MODE=mock  → in-browser mock backend (default, works offline)
 *   VITE_API_MODE=real  → HTTP calls to VITE_API_BASE (default '/api')
 *
 * No application code needs to change — every screen talks to `authApi` in
 * `src/api/auth.ts`, which reads this config at module load.
 */

export type ApiMode = 'mock' | 'real';

export const API_MODE: ApiMode = (import.meta.env.VITE_API_MODE as ApiMode) || 'mock';
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? '/api';
export const isMockMode: boolean = API_MODE === 'mock';