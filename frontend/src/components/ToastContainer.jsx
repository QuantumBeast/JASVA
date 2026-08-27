import React from 'react';
import { useJasva } from '../context/JasvaContext';

export const ToastContainer = () => {
  const { toasts } = useJasva();

  if (!toasts || toasts.length === 0) return null;

  return (
    <div className="toast-container">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast-card ${toast.type || 'info'}`}>
          {toast.title && (
            <div style={{ fontWeight: 800, fontSize: '11px', letterSpacing: '1px', marginBottom: '2px', color: 'var(--accent-color)' }}>
              {toast.title}
            </div>
          )}
          <div>{toast.message}</div>
        </div>
      ))}
    </div>
  );
};
