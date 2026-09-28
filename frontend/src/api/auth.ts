import { isMockMode } from './config';
import * as mock from './mock/handlers';
import * as real from './real';
import { TokenStore } from '../lib/TokenStore';
import type { AuthApi } from './types';

const api: AuthApi = isMockMode
  ? {
      login: (data) => mock.handleLogin(data),
      register: (data) => mock.handleRegister(data),
      refresh: () => mock.handleRefresh(TokenStore.getRefresh()),
      logout: () => mock.handleLogout(TokenStore.getRefresh()),
      verify: () => mock.handleVerify(TokenStore.getAccess()),
      getTenants: () => mock.handleGetTenants(),
      createTenant: (data) => mock.handleCreateTenant(data),
      updateTenant: (id, data) => mock.handleUpdateTenant(id, data),
      suspendTenant: (id) => mock.handleSuspendTenant(id),
      reactivateTenant: (id) => mock.handleReactivateTenant(id),
      getTenantQuota: () => mock.handleGetTenantQuota(),
    }
  : {
      login: (data) => real.realApi.login(data),
      register: (data) => real.realApi.register(data),
      refresh: () => real.realApi.refresh(),
      logout: () => real.realApi.logout(),
      verify: () => real.realApi.verify(),
      getTenants: () => real.realApi.getTenants(),
      createTenant: (data) => real.realApi.createTenant(data),
      updateTenant: (id, data) => real.realApi.updateTenant(id, data),
      suspendTenant: (id) => real.realApi.suspendTenant(id),
      reactivateTenant: (id) => real.realApi.reactivateTenant(id),
      getTenantQuota: () => real.realApi.getTenantQuota(),
    };

export default api;