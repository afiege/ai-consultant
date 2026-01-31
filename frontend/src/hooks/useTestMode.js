import { useState, useEffect } from 'react';

/**
 * Custom hook for managing test mode state.
 * Synchronizes with localStorage and listens for changes from:
 * - Other tabs (via 'storage' event)
 * - Same tab (via custom 'testModeChanged' event)
 *
 * @returns {boolean} Whether test mode is enabled
 */
export const useTestMode = () => {
  const [testModeEnabled, setTestModeEnabled] = useState(() => {
    return localStorage.getItem('test_mode_enabled') === 'true';
  });

  useEffect(() => {
    // Handle changes from other tabs
    const handleStorageChange = () => {
      setTestModeEnabled(localStorage.getItem('test_mode_enabled') === 'true');
    };

    // Handle changes from same tab (dispatched by ExpertSettingsModal)
    const handleTestModeChanged = (e) => {
      setTestModeEnabled(e.detail.enabled);
    };

    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('testModeChanged', handleTestModeChanged);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('testModeChanged', handleTestModeChanged);
    };
  }, []);

  return testModeEnabled;
};

export default useTestMode;
