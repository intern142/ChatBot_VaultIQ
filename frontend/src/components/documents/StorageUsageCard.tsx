export function StorageUsageCard({ totalDocuments, totalSizeMb, error }: { totalDocuments: number; totalSizeMb: number; error?: string | null }) {
  return (
    <div style={styles.card}>
      <div style={styles.grid}>
        <div style={styles.item}>
          <div style={styles.label}>Documents</div>
          <div style={styles.value}>{totalDocuments.toLocaleString()}</div>
        </div>
        <div style={styles.item}>
          <div style={styles.label}>Storage Used</div>
          <div style={styles.value}>{totalSizeMb.toFixed(2)} MB</div>
        </div>
      </div>
      {error && <div style={styles.error}>{error}</div>}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    background: 'white',
    border: '1px solid #e2e8f0',
    borderRadius: '12px',
    padding: '20px 24px',
    marginBottom: '24px',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
    gap: '24px',
  },
  item: { display: 'flex', flexDirection: 'column', gap: '4px' },
  label: { fontSize: '13px', fontWeight: 500, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' },
  value: { fontSize: '28px', fontWeight: 700, color: '#0f172a' },
  error: { marginTop: '16px', padding: '12px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', color: '#991b1b', fontSize: '13px' },
};