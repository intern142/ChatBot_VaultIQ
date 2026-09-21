import { useState, useRef, useEffect } from 'react';

export function HoverCard({ children }) {
  return children;
}

export function HoverCardTrigger({ children, ...props }) {
  const ref = useRef(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onEnter = () => setOpen(true);
    const onLeave = () => setOpen(false);
    el.addEventListener('mouseenter', onEnter);
    el.addEventListener('mouseleave', onLeave);
    el.addEventListener('focusin', onEnter);
    el.addEventListener('focusout', onLeave);
    return () => {
      el.removeEventListener('mouseenter', onEnter);
      el.removeEventListener('mouseleave', onLeave);
      el.removeEventListener('focusin', onEnter);
      el.removeEventListener('focusout', onLeave);
    };
  }, []);

  return (
    <span ref={ref} className="hover-card-trigger" {...props}>
      {children}
      {open && <HoverCardPortal />}
    </span>
  );
}

function HoverCardPortal() {
  return <div className="hover-card-portal" />;
}

export function HoverCardContent({ children, side = 'top', align = 'center', className = '', ...props }) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef(null);
  const contentRef = useRef(null);

  useEffect(() => {
    const trigger = triggerRef.current?.parentElement;
    const content = contentRef.current;
    if (!trigger || !content) return;

    const onEnter = () => setOpen(true);
    const onLeave = () => setOpen(false);

    trigger.addEventListener('mouseenter', onEnter);
    trigger.addEventListener('mouseleave', onLeave);
    content.addEventListener('mouseenter', onEnter);
    content.addEventListener('mouseleave', onLeave);
    trigger.addEventListener('focusin', onEnter);
    trigger.addEventListener('focusout', onLeave);

    return () => {
      trigger.removeEventListener('mouseenter', onEnter);
      trigger.removeEventListener('mouseleave', onLeave);
      content.removeEventListener('mouseenter', onEnter);
      content.removeEventListener('mouseleave', onLeave);
      trigger.removeEventListener('focusin', onEnter);
      trigger.removeEventListener('focusout', onLeave);
    };
  }, []);

  if (!open) return null;

  return (
    <div
      ref={contentRef}
      className={`hover-card-content hover-card-content--${side} hover-card-content--${align} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

HoverCardTrigger.displayName = 'HoverCardTrigger';
HoverCardContent.displayName = 'HoverCardContent';