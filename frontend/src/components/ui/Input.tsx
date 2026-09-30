import { InputHTMLAttributes, forwardRef } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, className = '', style, id, ...props }, ref) => {
    const inputId = id || props.name;

    return (
      <div style={styles.wrapper}>
        {label && <label htmlFor={inputId} style={styles.label}>{label}</label>}
        <input
          ref={ref}
          id={inputId}
          style={{
            ...styles.input,
            borderColor: error ? '#dc2626' : '#cbd5e1',
            ...style,
          }}
          className={className}
          aria-invalid={error ? 'true' : 'false'}
          aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
          {...props}
        />
        {error && <p id={`${inputId}-error`} style={styles.error}>{error}</p>}
        {hint && !error && <p id={`${inputId}-hint`} style={styles.hint}>{hint}</p>}
      </div>
    );
  }
);

Input.displayName = 'Input';

const styles: Record<string, React.CSSProperties> = {
  wrapper: { display: 'flex', flexDirection: 'column', gap: '6px' },
  label: { fontSize: '13px', fontWeight: 500, color: '#334155' },
  input: {
    width: '100%',
    padding: '10px 14px',
    fontSize: '14px',
    fontFamily: 'inherit',
    color: '#0f172a',
    background: 'white',
    border: '1px solid',
    borderRadius: '8px',
    outline: 'none',
    transition: 'border-color 0.15s, box-shadow 0.15s',
    boxSizing: 'border-box',
  },
  error: { margin: '0', fontSize: '12px', color: '#dc2626' },
  hint: { margin: '0', fontSize: '12px', color: '#94a3b8' },
};