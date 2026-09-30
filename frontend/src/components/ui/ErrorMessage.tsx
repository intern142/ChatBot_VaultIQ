

interface ErrorMessageProps {
  error: unknown;
  fallback?: string;
  className?: string;
  style?: React.CSSProperties;
}

export function ErrorMessage({ error, fallback = 'An unexpected error occurred', className = '', style }: ErrorMessageProps) {
  const message = error instanceof Error ? error.message : typeof error === 'string' ? error : fallback;

  return (
    <div style={{ ...styles.container, ...style }} className={className} role="alert">
      <span style={styles.icon}>⚠️</span>
      <span style={styles.message}>{message}</span>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 12px',
    background: '#fef2f2',
    border: '1px solid #fecaca',
    borderRadius: '8px',
    color: '#991b1b',
    fontSize: '13px',
  },
  icon: { flexShrink: 0 },
  message: { lineHeight: '1.4' },
};