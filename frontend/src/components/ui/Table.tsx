import { TableHTMLAttributes } from 'react';

interface Column<T> {
  key: string;
  header: string;
  render?: (row: T, index: number) => React.ReactNode;
  className?: string;
}

interface TableProps<T> extends TableHTMLAttributes<HTMLTableElement> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (row: T) => string;
  striped?: boolean;
  hover?: boolean;
  emptyMessage?: string;
}

export function Table<T>({
  columns,
  data,
  keyExtractor,
  striped = true,
  hover = true,
  emptyMessage = 'No data',
  children,
  className = '',
  style,
  ...props
}: TableProps<T>) {
  return (
    <div style={{ ...styles.wrapper, ...style }} className={className}>
      <table {...props} style={{ ...styles.table, ...style }}>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} style={styles.th} className={col.className}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} style={styles.empty}>
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row, index) => {
              return (
                <tr
                  key={keyExtractor(row)}
                  style={{
                    ...styles.tr,
                    ...(striped && index % 2 === 1 ? styles.striped : {}),
                    ...(hover ? styles.hover : {}),
                  }}
                >
                  {columns.map((col) => (
                    <td key={col.key} style={styles.td} className={col.className}>
                      {col.render ? col.render(row, index) : (row as any)[col.key]}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: { overflowX: 'auto' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '13px' },
  th: {
    textAlign: 'left',
    padding: '12px 16px',
    borderBottom: '2px solid #e2e8f0',
    fontWeight: 600,
    color: '#334155',
    whiteSpace: 'nowrap',
  },
  tr: { borderBottom: '1px solid #e2e8f0', transition: 'background 0.1s' },
  striped: { background: '#f8fafc' },
  hover: { background: '#f1f5f9' },
  td: { padding: '12px 16px', color: '#1e293b', whiteSpace: 'nowrap' },
  empty: { padding: '48px', textAlign: 'center', color: '#94a3b8' },
};