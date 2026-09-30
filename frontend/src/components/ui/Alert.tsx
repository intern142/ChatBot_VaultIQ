import { ReactNode } from 'react';

type Variant = 'error' | 'warning' | 'info' | 'success';

interface AlertProps {
  variant?: Variant;
  children: ReactNode;
  onDismiss?: () => void;
  className?: string;
  style?: React.CSSProperties;
}

export function Alert({ variant = 'error', children, onDismiss, className = '', style }: AlertProps) {
  const variantStyles: Record<Variant, React.CSSProperties> = {
    error: { background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b' },
    warning: { background: '#fffbeb', border: '1px solid #fde68a', color: '#92400e' },
    info: { background: '#eff6ff', border: '1px solid #bfdbfe', color: '#1e40af' },
    success: { background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534' },
  };

  return (
    <div
      style={{
        ...styles.base,
        ...variantStyles[variant],
        ...style,
      }}
      className={className}
      role="alert"
    >
      <div style={styles.content}>{children}</div>
      {onDismiss && <button style={styles.dismiss} onClick={onDismiss}>×</button>}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  base: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: '12px',
    padding: '12px 16px',
    borderRadius: '8px',
    fontSize: '14px',
    lineHeight: '1.5',
  },
  content: { flex: 1 },
  dismiss: {
    background: 'none',
    border: 'none',
    fontSize: '18px',
    cursor: 'pointer',
    color: 'inherit',
    opacity: 0.7,
    lineHeight: 1,
    padding: '0 4px',
    flexShrink: 0,
  },
};