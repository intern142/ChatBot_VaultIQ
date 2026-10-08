import { describe, it, expect } from 'vitest';
import {
  getDashboardOverview,
  getDashboardList,
  getKnowledgeGaps,
  downloadDashboardCsv,
} from '@/api/dashboard';
import { ApiError } from '@/api/errors';

function blobToText(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

describe('dashboard API (mock mode)', () => {
  it('returns the declared overview shape', async () => {
    const overview = await getDashboardOverview();
    expect(typeof overview.active_users).toBe('number');
    expect(typeof overview.answered_count).toBe('number');
    expect(typeof overview.partial_count).toBe('number');
    expect(typeof overview.not_found_count).toBe('number');
    expect(overview.avg_confidence === null || typeof overview.avg_confidence === 'number').toBe(
      true,
    );
    expect(Array.isArray(overview.questions_per_day_30d)).toBe(true);
    expect(overview.questions_per_day_30d.length).toBeGreaterThan(0);
    const first = overview.questions_per_day_30d[0] as Record<string, unknown>;
    expect(typeof first.day).toBe('string');
    expect(typeof first.count).toBe('number');
  });

  it('returns a paginated list with the declared envelope', async () => {
    const page = await getDashboardList('documents', { limit: 2, offset: 0 });
    expect(page.items).toHaveLength(2);
    expect(page.total).toBe(3);
    expect(page.limit).toBe(2);
    expect(page.offset).toBe(0);
  });

  it('honours offset when slicing', async () => {
    const page = await getDashboardList('users', { limit: 2, offset: 2 });
    expect(page.items).toHaveLength(1);
    expect(page.offset).toBe(2);
    expect(page.total).toBe(3);
  });

  it('filters by search across row values', async () => {
    const matched = await getDashboardList('documents', { search: 'policy' });
    expect(matched.total).toBeGreaterThan(0);
    for (const item of matched.items) {
      const haystack = Object.values(item).map((value) => String(value).toLowerCase()).join(' ');
      expect(haystack).toContain('policy');
    }
    const none = await getDashboardList('documents', { search: 'no-such-record-xyz' });
    expect(none.items).toHaveLength(0);
    expect(none.total).toBe(0);
  });

  it('returns knowledge gaps with question/count/last_asked', async () => {
    const gaps = await getKnowledgeGaps({ limit: 10, offset: 0 });
    expect(gaps.items.length).toBeGreaterThan(0);
    const first = gaps.items[0];
    expect(typeof first.question).toBe('string');
    expect(typeof first.count).toBe('number');
    expect(typeof first.last_asked).toBe('string');
  });

  it('builds a CSV with quoted headers and known rows', async () => {
    const blob = await downloadDashboardCsv('documents');
    expect(blob.type).toContain('text/csv');
    const text = await blobToText(blob);
    const [header, ...lines] = text.trim().split('\n');
    expect(header).toContain('"original_filename"');
    expect(header).toContain('"processing_status"');
    expect(lines.length).toBe(3);
    expect(text).toContain('security-policy.pdf');
  });

  it('rejects an unknown export entity with 404', async () => {
    const err = await downloadDashboardCsv('nope').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(404);
  });
});
