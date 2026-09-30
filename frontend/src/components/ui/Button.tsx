import { ButtonHTMLAttributes, forwardRef } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  icon?: string;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', loading, icon, children, disabled, className = '', style, ...props }, ref) => {
    const baseStyles: React.CSSProperties = {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '8px',
      fontWeight: 600,
      borderRadius: '8px',
      border: '1px solid transparent',
      cursor: loading || disabled ? 'not-allowed' : 'pointer',
      transition: 'all 0.15s ease',
      opacity: loading || disabled ? 0.7 : 1,
      textDecoration: 'none',
    };

    const sizeStyles: Record<string, React.CSSProperties> = {
      sm: { padding: '6px 12px', fontSize: '13px', height: '36px' },
      md: { padding: '10px 20px', fontSize: '14px', height: '44px' },
      lg: { padding: '14px 28px', fontSize: '15px', height: '52px' },
    };

    const variantStyles: Record<string, React.CSSProperties> = {
      primary: { background: '#1e293b', color: 'white', borderColor: '#1e293b' },
      secondary: { background: '#334155', color: 'white', borderColor: '#334155' },
      outline: { background: 'transparent', color: '#1e293b', borderColor: '#cbd5e1' },
      ghost: { background: 'transparent', color: '#475569', borderColor: 'transparent' },
      danger: { background: '#dc2626', color: 'white', borderColor: '#dc2626' },
    };

    return (
      <button
        ref={ref}
        disabled={loading || disabled}
        style={{
          ...baseStyles,
          ...sizeStyles[size],
          ...variantStyles[variant],
          ...style,
        }}
        className={className}
        {...props}
      >
        {loading ? (
          <>
            <span style={styles.spinner} />
            Loading…
          </>
        ) : (
          <>
            {icon && <span>{icon}</span>}
            {children}
          </>
        )}
      </button>
    );
  }
);

Button.displayName = 'Button';

const styles: Record<string, React.CSSProperties> = {
  spinner: {
    width: '16px',
    height: '16px',
    border: '2px solid currentColor',
    borderRightColor: 'transparent',
    borderRadius: '50%',
    animation: 'spin 0.6s linear infinite',
  },
};

// Add keyframes via style injection
if (typeof document !== 'undefined' && !document.getElementById('button-spinner-style')) {
  const style = document.createElement('style');
  style.id = 'button-spinner-style';
  style.textContent = `
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
  `;
  document.head.appendChild(style);
}