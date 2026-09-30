type Size = 'sm' | 'md' | 'lg';

interface SpinnerProps {
  size?: Size;
  color?: string;
  className?: string;
  style?: React.CSSProperties;
  label?: string;
}

export function Spinner({ size = 'md', color = 'currentColor', className = '', style, label }: SpinnerProps) {
  const sizeStyles: Record<Size, React.CSSProperties> = {
    sm: { width: '16px', height: '16px', borderWidth: '2px' },
    md: { width: '24px', height: '24px', borderWidth: '3px' },
    lg: { width: '32px', height: '32px', borderWidth: '3px' },
  };

  return (
    <span
      style={{
        ...styles.base,
        ...sizeStyles[size],
        borderColor: `${color} ${color} transparent transparent`,
        ...style,
      }}
      className={className}
      role="status"
      aria-label={label || 'Loading'}
    >
      {label && <span style={styles.srOnly}>{label}</span>}
    </span>
  );
}

const styles: Record<string, React.CSSProperties> = {
  base: {
    display: 'inline-block',
    borderRadius: '50%',
    borderStyle: 'solid',
    animation: 'spin 0.6s linear infinite',
    verticalAlign: 'middle',
  },
  srOnly: {
    position: 'absolute',
    width: '1px',
    height: '1px',
    padding: 0,
    margin: '-1px',
    overflow: 'hidden',
    clip: 'rect(0, 0, 0, 0)',
    whiteSpace: 'nowrap',
    border: 0,
  },
};

// Inject keyframes once
if (typeof document !== 'undefined' && !document.getElementById('spinner-style')) {
  const style = document.createElement('style');
  style.id = 'spinner-style';
  style.textContent = `
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
  `;
  document.head.appendChild(style);
}