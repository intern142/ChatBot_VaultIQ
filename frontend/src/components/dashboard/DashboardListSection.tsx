import { useState } from 'react';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { Spinner } from '@/components/ui/Spinner';
import { useDashboardExport, useDashboardList } from '@/hooks/useDashboard';
import type { DashboardEntity } from '@/api/dashboard';

type ListEntity = DashboardEntity | 'knowledge-gaps';

interface ColumnDef {
  key: string;
  label: string;
}

const ENTITY_COLUMNS: Record<ListEntity, ColumnDef[]> = {
  documents: [
    { key: 'original_filename', label: 'Filename' },
    { key: 'category', label: 'Category' },
    { key: 'status', label: 'Status' },
    { key: 'processing_status', label: 'Processing' },
    { key: 'size_bytes', label: 'Size' },
    { key: 'created_at', label: 'Created' },
  ],
  users: [
    { key: 'email', label: 'Email' },
    { key: 'role', label: 'Role' },
    { key: 'is_active', label: 'Active' },
    { key: 'created_at', label: 'Created' },
  ],
  audit: [
    { key: 'action', label: 'Action' },
    { key: 'target_type', label: 'Target' },
    { key: 'actor_role', label: 'Actor role' },
    { key: 'created_at', label: 'When' },
  ],
  feedback: [
    { key: 'vote', label: 'Vote' },
    { key: 'comment', label: 'Comment' },
    { key: 'answer_id', label: 'Answer' },
    { key: 'created_at', label: 'When' },
  ],
  'knowledge-gaps': [
    { key: 'question', label: 'Question' },
    { key: 'count', label: 'Times asked' },
    { key: 'last_asked', label: 'Last asked' },
  ],
};

const ENTITY_TITLES: Record<ListEntity, string> = {
  documents: 'Documents',
  users: 'Users',
  audit: 'Audit entries',
  feedback: 'Feedback',
  'knowledge-gaps': 'Knowledge gaps',
};

function titleCase(key: string): string {
  return key
    .split('_')
    .map((part) => (part.length > 0 ? part.charAt(0).toUpperCase() + part.slice(1) : part))
    .join(' ');
}

function buildColumns(entity: ListEntity, items: Array<Record<string, unknown>>): ColumnDef[] {
  const configured = ENTITY_COLUMNS[entity];
  const present = new Set(items.flatMap((item) => Object.keys(item)));
  const columns = configured.filter((column) => present.has(column.key));
  const known = new Set(configured.map((column) => column.key));
  for (const item of items) {
    for (const key of Object.keys(item)) {
      if (!known.has(key) && !columns.some((column) => column.key === key)) {
        columns.push({ key, label: titleCase(key) });
        known.add(key);
      }
    }
  }
  return columns;
}

function formatCell(key: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (key === 'size_bytes' && typeof value === 'number') return `${Math.round(value / 1024)} KB`;
  if (
    (key.endsWith('_at') || key === 'last_asked' || key === 'date') &&
    typeof value === 'string'
  ) {
    const parsed = new Date(value);
    if (!Number.isNaN(parsed.getTime())) return parsed.toLocaleString();
  }
  if (key === 'vote') return value === 1 ? '👍 up' : value === -1 ? '👎 down' : String(value);
  return String(value);
}

interface DashboardListSectionProps {
  entity: ListEntity;
}

export function DashboardListSection({ entity }: DashboardListSectionProps) {
  const { items, total, limit, offset, search, loading, error, runSearch, goToOffset, reload } =
    useDashboardList(entity);
  const { exporting, error: exportError, exportCsv, dismissError } = useDashboardExport();
  const [searchInput, setSearchInput] = useState('');

  const isExporting = exporting === entity;
  const canPrev = offset > 0 && !loading;
  const canNext = offset + limit < total && !loading;
  const rangeStart = total === 0 ? 0 : offset + 1;
  const rangeEnd = Math.min(offset + items.length, total);

  const submitSearch = (event: React.FormEvent) => {
    event.preventDefault();
    runSearch(searchInput.trim());
  };

  const columns = items.length > 0 ? buildColumns(entity, items) : [];

  return (
    <section data-testid={`dashboard-list-${entity}`}>
      <div style={styles.toolbar}>
        <form onSubmit={submitSearch} style={styles.searchForm} role="search">
          <input
            type="search"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder={`Search ${ENTITY_TITLES[entity].toLowerCase()}…`}
            aria-label={`Search ${ENTITY_TITLES[entity]}`}
            style={styles.searchInput}
          />
          <Button type="submit" variant="outline" size="sm">
            Search
          </Button>
          {search && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                setSearchInput('');
                runSearch('');
              }}
            >
              Clear
            </Button>
          )}
        </form>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          loading={isExporting}
          onClick={() => void exportCsv(entity as DashboardEntity)}
          disabled={entity === 'knowledge-gaps'}
          title={
            entity === 'knowledge-gaps'
              ? 'CSV export covers documents, users, audit and feedback only'
              : undefined
          }
        >
          Export CSV
        </Button>
      </div>

      {exportError && (
        <Alert onDismiss={dismissError} style={styles.alert}>
          {exportError}
        </Alert>
      )}

      {loading && (
        <div style={styles.center}>
          <Spinner label={`Loading ${ENTITY_TITLES[entity].toLowerCase()}…`} />
        </div>
      )}

      {!loading && error && (
        <div style={styles.errorBox}>
          <Alert style={styles.alert}>{error}</Alert>
          <Button type="button" variant="outline" size="sm" onClick={reload}>
            Retry
          </Button>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <EmptyState
          title={search ? 'No matching records' : `No ${ENTITY_TITLES[entity].toLowerCase()} yet`}
          description={
            search
              ? `Nothing matched "${search}". Try a different search.`
              : 'When this tenant has data, it will appear here.'
          }
        />
      )}

      {!loading && !error && items.length > 0 && (
        <div style={styles.tableWrap}>
          <table style={styles.table}>
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column.key} style={styles.th}>
                    {column.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((item, index) => (
                <tr key={index} style={styles.row}>
                  {columns.map((column) => (
                    <td key={column.key} style={styles.td}>
                      {formatCell(column.key, item[column.key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && !error && total > 0 && (
        <div style={styles.pagination}>
          <span style={styles.pageInfo}>
            Showing {rangeStart}–{rangeEnd} of {total}
          </span>
          <div style={styles.pageButtons}>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!canPrev}
              onClick={() => goToOffset(offset - limit)}
            >
              Previous
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!canNext}
              onClick={() => goToOffset(offset + limit)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}

const styles: Record<string, React.CSSProperties> = {
  toolbar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '12px',
    flexWrap: 'wrap',
    marginBottom: '12px',
  },
  searchForm: { display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' },
  searchInput: {
    padding: '8px 12px',
    border: '1px solid #cbd5e1',
    borderRadius: '8px',
    fontSize: '14px',
    minWidth: '220px',
    color: '#1e293b',
    background: 'white',
  },
  alert: { marginBottom: '12px' },
  center: { display: 'flex', justifyContent: 'center', padding: '32px 0' },
  errorBox: { marginBottom: '12px' },
  tableWrap: { overflowX: 'auto', border: '1px solid #e2e8f0', borderRadius: '8px' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '14px' },
  th: {
    textAlign: 'left',
    padding: '10px 12px',
    background: '#f8fafc',
    borderBottom: '1px solid #e2e8f0',
    fontWeight: 600,
    color: '#334155',
    whiteSpace: 'nowrap',
  },
  row: { borderBottom: '1px solid #f1f5f9' },
  td: { padding: '10px 12px', color: '#1e293b', verticalAlign: 'top' },
  pagination: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: '12px',
    flexWrap: 'wrap',
    gap: '8px',
  },
  pageInfo: { fontSize: '13px', color: '#64748b' },
  pageButtons: { display: 'flex', gap: '8px' },
};
