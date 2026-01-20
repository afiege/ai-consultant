import React, { createContext, useContext, useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { expertSettingsAPI } from '../services/api';

const LanguageContext = createContext();

export const useLanguage = () => {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
};

export const LanguageProvider = ({ children }) => {
  const { i18n } = useTranslation();
  const [language, setLanguageState] = useState('en');
  const [sessionUuid, setSessionUuid] = useState(null);

  // Load language from session settings when sessionUuid changes
  useEffect(() => {
    if (sessionUuid) {
      loadLanguageFromSession(sessionUuid);
    }
  }, [sessionUuid]);

  const loadLanguageFromSession = async (uuid) => {
    try {
      const response = await expertSettingsAPI.get(uuid);
      const lang = response.data.prompt_language || 'en';
      setLanguageState(lang);
      i18n.changeLanguage(lang);
    } catch (err) {
      // Session might not exist yet, use default
      console.log('Could not load language from session, using default');
    }
  };

  const setLanguage = async (newLanguage) => {
    setLanguageState(newLanguage);
    i18n.changeLanguage(newLanguage);

    // If we have a session, save to backend
    if (sessionUuid) {
      try {
        await expertSettingsAPI.update(sessionUuid, {
          prompt_language: newLanguage
        });
      } catch (err) {
        console.error('Failed to save language to session:', err);
      }
    }
  };

  const registerSession = (uuid) => {
    setSessionUuid(uuid);
  };

  const value = {
    language,
    setLanguage,
    registerSession,
    sessionUuid
  };

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
};

export default LanguageContext;
