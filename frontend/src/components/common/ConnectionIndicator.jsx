import React, { useEffect, useState } from 'react';
import { Wifi, WifiOff, AlertCircle } from 'lucide-react';
import '../../styles/connection-indicator.css';

export default function ConnectionIndicator({ status = 'connected', lastUpdate = null }) {
  const [displayTime, setDisplayTime] = useState('');
  
  useEffect(() => {
    if (!lastUpdate) return;
    
    const updateTime = () => {
      const now = new Date();
      const diff = Math.floor((now - new Date(lastUpdate)) / 1000);
      
      if (diff < 60) {
        setDisplayTime(`${diff}s ago`);
      } else if (diff < 3600) {
        setDisplayTime(`${Math.floor(diff / 60)}m ago`);
      } else {
        setDisplayTime(`${Math.floor(diff / 3600)}h ago`);
      }
    };
    
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, [lastUpdate]);
  
  const getStatusConfig = () => {
    switch(status) {
      case 'connected':
        return {
          color: '#3ecf8e',
          icon: Wifi,
          label: 'Connected',
          ariaLabel: 'Backend connected'
        };
      case 'connecting':
        return {
          color: '#f5a623',
          icon: Wifi,
          label: 'Connecting...',
          ariaLabel: 'Connecting to backend'
        };
      case 'error':
        return {
          color: '#e05252',
          icon: WifiOff,
          label: 'Offline',
          ariaLabel: 'Backend disconnected'
        };
      default:
        return {
          color: '#8b919e',
          icon: WifiOff,
          label: 'Unknown',
          ariaLabel: 'Connection status unknown'
        };
    }
  };
  
  const config = getStatusConfig();
  const IconComponent = config.icon;
  
  return (
    <div 
      className={`connection-indicator status-${status}`}
      role="status"
      aria-label={config.ariaLabel}
      aria-live="polite"
    >
      <div className="connection-icon" style={{ color: config.color }}>
        <IconComponent size={16} />
        {status === 'connecting' && <div className="pulse"></div>}
      </div>
      <div className="connection-info">
        <div className="connection-status">{config.label}</div>
      </div>
    </div>
  );
}
