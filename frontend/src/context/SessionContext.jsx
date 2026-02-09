import React, { createContext, useContext, useState, useEffect } from 'react';
import { sessionAPI } from '../services/api';

const SessionContext = createContext(null);

export const useSession = () => {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
};

export const SessionProvider = ({ children }) => {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Create new session
  const createSession = async (companyName = '') => {
    setLoading(true);
    setError(null);
    try {
      const response = await sessionAPI.create({ company_name: companyName });
      setSession(response.data);
      // Store session UUID in localStorage for persistence
      localStorage.setItem('currentSessionUuid', response.data.session_uuid);
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  // Load existing session
  const loadSession = async (sessionUuid) => {
    setLoading(true);
    setError(null);
    try {
      const response = await sessionAPI.get(sessionUuid);
      setSession(response.data);
      localStorage.setItem('currentSessionUuid', sessionUuid);
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  // Update session
  const updateSession = async (updates) => {
    if (!session) return;

    setLoading(true);
    setError(null);
    try {
      const response = await sessionAPI.update(session.session_uuid, updates);
      setSession(response.data);
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  // Move to next step
  const nextStep = async () => {
    if (!session || session.current_step >= 6) return;
    return updateSession({ current_step: session.current_step + 1 });
  };

  // Move to previous step
  const previousStep = async () => {
    if (!session || session.current_step <= 1) return;
    return updateSession({ current_step: session.current_step - 1 });
  };

  // Clear session
  const clearSession = () => {
    setSession(null);
    localStorage.removeItem('currentSessionUuid');
  };

  // Try to restore session from localStorage on mount
  useEffect(() => {
    const storedUuid = localStorage.getItem('currentSessionUuid');
    if (storedUuid) {
      loadSession(storedUuid).catch(() => {
        // If session doesn't exist, clear it
        localStorage.removeItem('currentSessionUuid');
      });
    }
  }, []);

  const value = {
    session,
    loading,
    error,
    createSession,
    loadSession,
    updateSession,
    nextStep,
    previousStep,
    clearSession,
  };

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  );
};
