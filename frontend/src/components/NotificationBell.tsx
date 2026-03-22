import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Bell } from 'lucide-react';
import { useNotifications } from '../contexts/NotificationContext';
import NotificationInboxPanel from './NotificationInboxPanel';
import './NotificationBell.css';

export default function NotificationBell() {
  const { unreadCount } = useNotifications();
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, right: 0 });
  const buttonRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Calcola posizione dropdown
  useEffect(() => {
    const updateDropdownPosition = () => {
      if (buttonRef.current) {
        const rect = buttonRef.current.getBoundingClientRect();
        setDropdownPosition({
          top: rect.bottom + 8,
          right: window.innerWidth - rect.right,
        });
      }
    };

    if (isDropdownOpen) {
      updateDropdownPosition();
      window.addEventListener('scroll', updateDropdownPosition, true);
      window.addEventListener('resize', updateDropdownPosition);
    }

    return () => {
      window.removeEventListener('scroll', updateDropdownPosition, true);
      window.removeEventListener('resize', updateDropdownPosition);
    };
  }, [isDropdownOpen]);

  // Chiudi dropdown se si clicca fuori
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      const isButtonClick = buttonRef.current?.contains(target);
      const isDropdownClick = dropdownRef.current?.contains(target);

      if (!isButtonClick && !isDropdownClick && isDropdownOpen) {
        setIsDropdownOpen(false);
      }
    };

    if (isDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isDropdownOpen]);

  const handleToggleDropdown = () => {
    setIsDropdownOpen(!isDropdownOpen);
  };

  return (
    <div className="notification-bell-container">
      <button
        ref={buttonRef}
        className={`notification-bell-button ${isDropdownOpen ? 'active' : ''}`}
        onClick={handleToggleDropdown}
        aria-label="Notifiche"
        aria-expanded={isDropdownOpen}
      >
        <Bell size={20} />
        {unreadCount > 0 && (
          <span className="notification-badge">{unreadCount > 99 ? '99+' : unreadCount}</span>
        )}
      </button>

      {isDropdownOpen &&
        createPortal(
          <div
            ref={dropdownRef}
            className="notification-dropdown"
            style={{
              position: 'fixed',
              top: dropdownPosition.top,
              right: dropdownPosition.right,
            }}
          >
            <NotificationInboxPanel
              variant="dropdown"
              onClose={() => setIsDropdownOpen(false)}
            />
          </div>,
          document.body
        )}
    </div>
  );
}
