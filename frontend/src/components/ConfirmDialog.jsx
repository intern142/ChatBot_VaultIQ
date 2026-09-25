import { useEffect } from 'react';
import { XIcon, CheckIcon, AlertTriangleIcon } from '../components/Icons';

export default function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  variant = 'danger',
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  loading = false,
}) {
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const variantStyles = {
    danger: {
      icon: AlertTriangleIcon,
      iconColor: 'var(--destructive)',
      confirmBg: 'var(--destructive)',
      confirmHover: 'hsl(0 84.2% 50%)',
    },
    warning: {
      icon: AlertTriangleIcon,
      iconColor: 'var(--warning)',
      confirmBg: 'var(--warning)',
      confirmHover: 'hsl(38 92% 45%)',
    },
    info: {
      icon: CheckIcon,
      iconColor: 'var(--primary)',
      confirmBg: 'var(--primary)',
      confirmHover: 'hsl(0 0% 20%)',
    },
  };

  const { icon: Icon, iconColor, confirmBg, confirmHover } = variantStyles[variant];

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') onClose();
    if (e.key === 'Enter' && !loading) onConfirm();
  };

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose, onConfirm, loading]);

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="confirm-title">
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3 id="confirm-title" className="modal-title">
            <span className="modal-icon" style={{ color: iconColor }}>
              <Icon />
            </span>
            {title}
          </h3>
          <button type="button" className="modal-close" onClick={onClose} disabled={loading} aria-label="Close">
            <XIcon />
          </button>
        </div>
        <div className="modal-body">
          <p className="confirm-message">{message}</p>
        </div>
        <div className="modal-actions">
          <button
            type="button"
            className="secondary-btn"
            onClick={onClose}
            disabled={loading}
          >
            {cancelText}
          </button>
          <button
            type="button"
            className="primary-btn confirm-btn"
            onClick={onConfirm}
            disabled={loading}
            style={{ background: confirmBg }}
          >
            {loading ? (
              <span className="btn-loading"><span className="spinner" /> Processing…</span>
            ) : confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}