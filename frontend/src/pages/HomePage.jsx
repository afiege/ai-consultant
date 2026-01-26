import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { sessionAPI, expertSettingsAPI, sessionBackupAPI, apiKeyManager } from '../services/api';
import LLMConfigSection from '../components/common/LLMConfigSection';

// Helper to load/save LLM config from localStorage
const LLM_CONFIG_KEY = 'ai_consultant_llm_config';

const loadSavedLLMConfig = () => {
  try {
    const saved = localStorage.getItem(LLM_CONFIG_KEY);
    if (saved) {
      return JSON.parse(saved);
    }
  } catch (e) {
    console.error('Failed to load saved LLM config:', e);
  }
  return { model: '', api_key: '', api_base: '' };
};

const saveLLMConfig = (config) => {
  try {
    localStorage.setItem(LLM_CONFIG_KEY, JSON.stringify(config));
  } catch (e) {
    console.error('Failed to save LLM config:', e);
  }
};

const HomePage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [companyName, setCompanyName] = useState('');
  const [creating, setCreating] = useState(false);
  const [llmConfig, setLlmConfig] = useState({ model: '', api_key: '', api_base: '' });
  const [showLLMConfig, setShowLLMConfig] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [restoreError, setRestoreError] = useState(null);
  const fileInputRef = useRef(null);

  // Load saved LLM config on mount
  useEffect(() => {
    const savedConfig = loadSavedLLMConfig();
    setLlmConfig(savedConfig);
    // Show config section if user has previously configured it
    if (savedConfig.model || savedConfig.api_key) {
      setShowLLMConfig(true);
    }
  }, []);

  const handleLLMConfigChange = (newConfig) => {
    setLlmConfig(newConfig);
    saveLLMConfig(newConfig);
  };

  const handleCreateSession = async (e) => {
    e.preventDefault();
    setCreating(true);

    try {
      // Create session
      const response = await sessionAPI.create({
        company_name: companyName || ''
      });
      const sessionUuid = response.data.session_uuid;

      // If LLM config is set, save it to the session
      if (llmConfig.model || llmConfig.api_key || llmConfig.api_base) {
        try {
          await expertSettingsAPI.update(sessionUuid, {
            llm_config: {
              model: llmConfig.model || null,
              api_key: llmConfig.api_key || null,
              api_base: llmConfig.api_base || null,
            }
          });
          // Also set the API key in sessionStorage so it's available for all steps
          if (llmConfig.api_key) {
            apiKeyManager.set(llmConfig.api_key);
          }
        } catch (configErr) {
          console.error('Failed to save LLM config to session:', configErr);
          // Continue anyway - user can configure later
        }
      }

      navigate(`/session/${sessionUuid}/step1a`);
    } catch (err) {
      console.error('Error creating session:', err);
      alert(t('errors.failedToStart'));
    } finally {
      setCreating(false);
    }
  };

  const handleRestoreSession = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setRestoring(true);
    setRestoreError(null);

    try {
      const response = await sessionBackupAPI.restoreBackup(file);
      const { new_session_uuid, original_company_name } = response.data;

      // Navigate to the appropriate step based on restored session state
      navigate(`/session/${new_session_uuid}/step1a`);
    } catch (err) {
      console.error('Error restoring session:', err);
      setRestoreError(err.response?.data?.detail || t('errors.failedToRestore'));
    } finally {
      setRestoring(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="max-w-2xl w-full mx-4">
        <div className="bg-white rounded-lg shadow-xl p-8 md:p-12">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-600 rounded-full mb-4">
              <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <h1 className="text-4xl font-bold text-gray-900 mb-2">
              {t('home.title')}
            </h1>
            <p className="text-lg text-gray-600">
              {t('home.subtitle')}
            </p>
          </div>

          {/* Features */}
          <div className="mb-8 space-y-3">
            <div className="flex items-start">
              <div className="flex-shrink-0 w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center mr-3 mt-0.5">
                <span className="text-blue-600 font-semibold text-sm">1</span>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">{t('home.features.step1Title')}</h3>
                <p className="text-sm text-gray-600">{t('home.features.step1Desc')}</p>
              </div>
            </div>
            <div className="flex items-start">
              <div className="flex-shrink-0 w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center mr-3 mt-0.5">
                <span className="text-blue-600 font-semibold text-sm">2</span>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">{t('home.features.step2Title')}</h3>
                <p className="text-sm text-gray-600">{t('home.features.step2Desc')}</p>
              </div>
            </div>
            <div className="flex items-start">
              <div className="flex-shrink-0 w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center mr-3 mt-0.5">
                <span className="text-blue-600 font-semibold text-sm">3</span>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">{t('home.features.step3Title')}</h3>
                <p className="text-sm text-gray-600">{t('home.features.step3Desc')}</p>
              </div>
            </div>
            <div className="flex items-start">
              <div className="flex-shrink-0 w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center mr-3 mt-0.5">
                <span className="text-blue-600 font-semibold text-sm">4</span>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">{t('home.features.step4Title')}</h3>
                <p className="text-sm text-gray-600">{t('home.features.step4Desc')}</p>
              </div>
            </div>
            <div className="flex items-start">
              <div className="flex-shrink-0 w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center mr-3 mt-0.5">
                <span className="text-blue-600 font-semibold text-sm">5</span>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">{t('home.features.step5Title')}</h3>
                <p className="text-sm text-gray-600">{t('home.features.step5Desc')}</p>
              </div>
            </div>
          </div>

          {/* Create Session Form */}
          <form onSubmit={handleCreateSession} className="space-y-4">
            <div>
              <label htmlFor="company-name" className="block text-sm font-medium text-gray-700 mb-2">
                {t('home.companyNameOptional')}
              </label>
              <input
                type="text"
                id="company-name"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder={t('home.companyNamePlaceholder')}
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={creating}
              />
            </div>

            {/* LLM Configuration Section */}
            <div className="border-t pt-4">
              <button
                type="button"
                onClick={() => setShowLLMConfig(!showLLMConfig)}
                className="flex items-center justify-between w-full text-left"
              >
                <span className="text-sm font-medium text-gray-700">
                  {t('home.llmConfig.title')}
                  {(llmConfig.model || llmConfig.api_key) && (
                    <span className="ml-2 text-xs text-green-600">✓ {t('home.llmConfig.configured')}</span>
                  )}
                </span>
                <svg
                  className={`w-5 h-5 text-gray-500 transition-transform ${showLLMConfig ? 'rotate-180' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {!showLLMConfig && (
                <p className="mt-1 text-xs text-gray-500">
                  {t('home.llmConfig.hint')}
                </p>
              )}

              {showLLMConfig && (
                <div className="mt-3 p-4 bg-blue-50 rounded-lg border border-blue-200">
                  <LLMConfigSection
                    config={llmConfig}
                    onChange={handleLLMConfigChange}
                    showTitle={false}
                    compact={true}
                  />
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={creating || restoring}
              className="w-full bg-blue-600 text-white py-3 px-6 rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium text-lg"
            >
              {creating ? t('home.creating') : t('home.startButton')}
            </button>
          </form>

          {/* Restore Session Section */}
          <div className="mt-6 pt-6 border-t border-gray-200">
            <div className="text-center">
              <p className="text-sm text-gray-600 mb-3">{t('home.restoreSession.description')}</p>

              <input
                ref={fileInputRef}
                type="file"
                accept=".json"
                onChange={handleRestoreSession}
                className="hidden"
                id="restore-file-input"
              />

              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={restoring || creating}
                className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:bg-gray-100 disabled:cursor-not-allowed transition-colors"
              >
                {restoring ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-gray-500" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    {t('home.restoreSession.restoring')}
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                    </svg>
                    {t('home.restoreSession.button')}
                  </>
                )}
              </button>

              {restoreError && (
                <p className="mt-2 text-sm text-red-600">{restoreError}</p>
              )}
            </div>
          </div>

          <p className="mt-6 text-center text-sm text-gray-500">
            {t('home.duration')}
          </p>
        </div>
      </div>
    </div>
  );
};

export default HomePage;
