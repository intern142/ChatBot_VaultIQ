export class ApiError extends Error {
  constructor(
    public readonly message: string,
    public readonly status: number,
    public readonly detail?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export function normaliseError(status: number, body: unknown): ApiError {
  if (!body || typeof body !== 'object' || !('detail' in body)) {
    return new ApiError('Unknown error', status, body);
  }
  const detail = (body as { detail: unknown }).detail;
  const msg = Array.isArray(detail)
    ? detail.map((d: any) => d?.msg ?? String(d)).join('; ')
    : String(detail);
  return new ApiError(msg, status, detail);
}