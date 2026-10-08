import { useState } from 'react';
import {
  getMyTenantSettings,
  updateMyTenantSettings,
  uploadMyTenantLogo,
} from '@/api/tenant';
import type { TenantSettingsResponse, TenantSettingsUpdateClientAdmin } from '@/api/types';
import { ApiError } from '@/api/errors';

export interface TenantSettingsState {
  data: TenantSettingsResponse | null;
  loading: boolean;
  saving: boolean;
  uploading: boolean;
  error: string | null;
  success: string | null;
}

export function useTenantSettings() {
  const [state, setState] = useState<TenantSettingsState>({
    data: null,
    loading: true,
    saving: false,
    uploading: false,
    error: null,
    success: null,
  });

  const load = async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await getMyTenantSettings();
      setState((s) => ({ ...s, data, loading: false }));
    } catch (e) {
      const err = e as ApiError;
      setState((s) => ({
        ...s,
        loading: false,
        error: err.status === 401 ? 'Session expired. Please log in again.' : 
               err.status === 403 ? 'You do not have permission to view tenant settings.' :
               err.message || 'Failed to load tenant settings.',
      }));
    }
  };

  const save = async (payload: TenantSettingsUpdateClientAdmin) => {
    setState((s) => ({ ...s, saving: true, error: null, success: null }));
    try {
      const data = await updateMyTenantSettings(payload);
      setState((s) => ({ ...s, data, saving: false, success: 'Settings saved successfully.' }));
      return data;
    } catch (e) {
      const err = e as ApiError;
      setState((s) => ({
        ...s,
        saving: false,
        error: err.status === 401 ? 'Session expired. Please log in again.' :
               err.status === 403 ? 'You do not have permission to update tenant settings.' :
               err.message || 'Failed to save settings.',
      }));
      throw e;
    }
  };

  const uploadLogo = async (file: File) => {
    setState((s) => ({ ...s, uploading: true, error: null, success: null }));
    try {
      const res = await uploadMyTenantLogo(file);
      setState((s) => ({
        ...s,
        data: s.data ? { ...s.data, logo_path: res.path } : null,
        uploading: false,
        success: 'Logo uploaded successfully.',
      }));
      return res;
    } catch (e) {
      const err = e as ApiError;
      setState((s) => ({
        ...s,
        uploading: false,
        error: err.status === 401 ? 'Session expired. Please log in again.' :
               err.status === 403 ? 'You do not have permission to upload a logo.' :
               err.message || 'Failed to upload logo.',
      }));
      throw e;
    }
  };

  const dismissError = () => setState((s) => ({ ...s, error: null }));
  const dismissSuccess = () => setState((s) => ({ ...s, success: null }));

  return {
    ...state,
    load,
    save,
    uploadLogo,
    dismissError,
    dismissSuccess,
  };
}