import React, { useEffect } from 'react';
import { AlertCircle, CheckCircle, Info, X } from 'lucide-react';
import '../../styles/toast.css';

const toastContainer = {
  toasts: [],
  listeners: new Set(),
  
  add(message, type = 'info', duration = 4000) {
    const id = Date.now();
    const toast = { id, message, type, duration };
    this.toasts.push(toast);
    this.notify();
    
    if (duration > 0) {
      setTimeout(() => this.remove(id), duration);
    }
    return id;
  },
  
  remove(id) {
    this.toasts = this.toasts.filter(t => t.id !== id);
    this.notify();
  },
  
  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  },
  
  notify() {
    this.listeners.forEach(listener => listener([...this.toasts]));
  }
};

export function useToast() {
  const [toasts, setToasts] = React.useState([]);
  
  React.useEffect(() => {
    return toastContainer.subscribe(setToasts);
  }, []);
  
  return {
    success: (message) => toastContainer.add(message, 'success', 3000),
    error: (message) => toastContainer.add(message, 'error', 5000),
    info: (message) => toastContainer.add(message, 'info', 3000),
    warning: (message) => toastContainer.add(message, 'warning', 4000),
    remove: (id) => toastContainer.remove(id),
    toasts
  };
}

const Toast = ({ id, message, type, onClose }) => {
  const icons = {
    success: <CheckCircle size={20} />,
    error: <AlertCircle size={20} />,
    warning: <AlertCircle size={20} />,
    info: <Info size={20} />,
  };
  
  return (
    <div className={`toast toast-${type}`} role="alert" aria-live="polite">
      <div className="toast-content">
        <div className="toast-icon">{icons[type]}</div>
        <div className="toast-message">{message}</div>
      </div>
      <button 
        className="toast-close" 
        onClick={() => onClose(id)}
        aria-label="Close notification"
      >
        <X size={16} />
      </button>
    </div>
  );
};

export default function ToastContainer() {
  const { toasts, remove } = useToast();
  
  return (
    <div className="toast-container" role="region" aria-label="Notifications">
      {toasts.map((toast) => (
        <Toast 
          key={toast.id} 
          id={toast.id} 
          message={toast.message} 
          type={toast.type}
          onClose={remove}
        />
      ))}
    </div>
  );
}
