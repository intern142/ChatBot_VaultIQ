const isMockMode = (): boolean => {
  return import.meta.env.VITE_API_MODE !== 'real';
};

const getApiBaseUrl = (): string => {
  return import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
};

export { isMockMode, getApiBaseUrl };