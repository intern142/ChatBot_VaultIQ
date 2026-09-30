import { Button } from './Button';

interface EmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
  className?: string;
  style?: React.CSSProperties;
}

export function EmptyState({ icon = '📭', title, description, action, className = '', style }: EmptyStateProps) {
  return (
    <div style={{ ...styles.container, ...style }} className={className}>
      <span style={styles.icon}>{icon}</span>
      <h3 style={styles.title}>{title}</h3>
      {description && <p style={styles.description}>{description}</p>}
      {action && (
        <Button onClick={action.onClick} style={styles.action}>
          {action.label}
        </Button>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '48px 24px',
    textAlign: 'center',
    color: '#64748b',
  },
  icon: { fontSize: '48px', marginBottom: '16px' },
  title: { margin: '0 0 8px', fontSize: '18px', fontWeight: 600, color: '#334155' },
  description: { margin: '0 0 24px', fontSize: '14px', color: '#94a3b8' },
  action: { marginTop: '8px' },
};