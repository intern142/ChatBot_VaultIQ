import { SelectHTMLAttributes, forwardRef } from 'react';

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  hint?: string;
  options: Array<{ value: string; label: string }>;
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, hint, options, placeholder, className = '', style, id, ...props }, ref) => {
    const selectId = id || props.name;

    return (
      <div style={styles.wrapper}>
        {label && <label htmlFor={id} style={styles.label}>{label}</label>}
        <select
          ref={ref}
          id={selectId}
          style={{
            ...styles.select,
            borderColor: error ? '#dc2626' : '#cbd5e1',
            ...style,
          }}
          className={className}
          aria-invalid={error ? 'true' : 'false'}
          aria-describedby={error ? `${selectId}-error` : hint ? `${selectId}-hint` : undefined}
          {...props}
        >
          {placeholder && <option value="" disabled>{placeholder}</option>}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {error && <p id={`${selectId}-error`} style={styles.error}>{error}</p>}
        {hint && !error && <p id={`${selectId}-hint`} style={styles.hint}>{hint}</p>}
      </div>
    );
  }
);

Select.displayName = 'Select';

const styles: Record<string, React.CSSProperties> = {
  wrapper: { display: 'flex', flexDirection: 'column', gap: '6px' },
  label: { fontSize: '13px', fontWeight: 500, color: '#334155' },
  select: {
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
    appearance: 'none',
    backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")",
    backgroundRepeat: 'no-repeat',
    backgroundPosition: 'right 12px center',
    paddingRight: '40px',
  },
  error: { margin: '0', fontSize: '12px', color: '#dc2626' },
  hint: { margin: '0', fontSize: '12px', color: '#94a3b8' },
};