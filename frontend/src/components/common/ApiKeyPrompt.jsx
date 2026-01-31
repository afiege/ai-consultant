import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { apiKeyManager, expertSettingsAPI } from '../../services/api';

/**
 * A modal component that prompts for API key when needed.
 * Shows provider selection and allows testing the connection.
 * Includes focus management for accessibility.
 */
const ApiKeyPrompt = ({ isOpen, onClose, onApiKeySet }) => {
  const { t } = useTranslation();
  const [apiKey, setApiKey] = useState('');
  const [llmProviders, setLlmProviders] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [error, setError] = useState('');

  // Refs for focus management
  const modalRef = useRef(null);
  const firstFocusableRef = useRef(null);
  const lastFocusableRef = useRef(null);
  const previousActiveElement = useRef(null);

  // Store the element that triggered the modal
  useEffect(() => {
    if (isOpen) {
      previousActiveElement.current = document.activeElement;
      loadProviders();
      // Pre-fill if API key already exists
      const existingKey = apiKeyManager.get();
      if (existingKey) {
        setApiKey(existingKey);
      }
    } else {
      // Restore focus when modal closes
      if (previousActiveElement.current) {
        previousActiveElement.current.focus();
      }
    }
  }, [isOpen]);

  // Focus the first focusable element when loading completes
  useEffect(() => {
    if (isOpen && !loading && firstFocusableRef.current) {
      firstFocusableRef.current.focus();
    }
  }, [isOpen, loading]);

  // Handle keyboard navigation (Escape to close, Tab trapping)
  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
      return;
    }

    // Trap focus within modal
    if (e.key === 'Tab') {
      const focusableElements = modalRef.current?.querySelectorAll(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );

      if (focusableElements && focusableElements.length > 0) {
        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];

        if (e.shiftKey && document.activeElement === firstElement) {
          e.preventDefault();
          lastElement.focus();
        } else if (!e.shiftKey && document.activeElement === lastElement) {
          e.preventDefault();
          firstElement.focus();
        }
      }
    }
  }, [onClose]);

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, handleKeyDown]);

  const loadProviders = async () => {
    try {
      const res = await expertSettingsAPI.getLLMProviders();
      setLlmProviders(res.data || []);
      // Select first provider by default
      if (res.data && res.data.length > 0) {
        setSelectedProvider(res.data[0].name);
        if (res.data[0].models && res.data[0].models.length > 0) {
          setSelectedModel(res.data[0].models[0]);
        }
      }
    } catch (err) {
      console.error('Failed to load LLM providers:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleProviderChange = (providerName) => {
    setSelectedProvider(providerName);
    const provider = llmProviders.find(p => p.name === providerName);
    if (provider && provider.models && provider.models.length > 0) {
      setSelectedModel(provider.models[0]);
    } else {
      setSelectedModel('');
    }
    setTestResult(null);
  };

  const handleTestConnection = async () => {
    if (!apiKey) {
      setError(t('apiKeyPrompt.enterKey'));
      return;
    }

    setTesting(true);
    setTestResult(null);
    setError('');

    try {
      const provider = llmProviders.find(p => p.name === selectedProvider);
      const response = await expertSettingsAPI.testLLM({
        model: selectedModel,
        api_key: apiKey,
        api_base: provider?.api_base || null
      });

      setTestResult(response.data);
    } catch (err) {
      setTestResult({
        success: false,
        message: err.response?.data?.message || t('apiKeyPrompt.testFailed')
      });
    } finally {
      setTesting(false);
    }
  };

  const handleSubmit = () => {
    if (!apiKey.trim()) {
      setError(t('apiKeyPrompt.enterKey'));
      return;
    }

    // Save to sessionStorage
    apiKeyManager.set(apiKey.trim());

    // Callback
    if (onApiKeySet) {
      onApiKeySet(apiKey.trim());
    }

    onClose();
  };

  if (!isOpen) return null;

  const currentProvider = llmProviders.find(p => p.name === selectedProvider);
  const availableModels = currentProvider?.models || [];

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="api-key-modal-title"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        ref={modalRef}
        className="bg-white rounded-lg shadow-xl max-w-md w-full p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="api-key-modal-title" className="text-xl font-semibold text-gray-900 mb-2">
          {t('apiKeyPrompt.title')}
        </h2>
        <p className="text-sm text-gray-600 mb-4">
          {t('apiKeyPrompt.description')}
        </p>

        {loading ? (
          <div className="flex justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : (
          <>
            {/* Provider Selection */}
            <div className="mb-4">
              <label htmlFor="provider-select" className="block text-sm font-medium text-gray-700 mb-1">
                {t('apiKeyPrompt.provider')}
              </label>
              <select
                id="provider-select"
                ref={firstFocusableRef}
                value={selectedProvider}
                onChange={(e) => handleProviderChange(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {llmProviders.map((provider) => (
                  <option key={provider.name} value={provider.name}>
                    {provider.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Model Selection */}
            {availableModels.length > 0 && (
              <div className="mb-4">
                <label htmlFor="model-select" className="block text-sm font-medium text-gray-700 mb-1">
                  {t('apiKeyPrompt.model')}
                </label>
                <select
                  id="model-select"
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {availableModels.map((model) => (
                    <option key={model} value={model}>
                      {model.includes('/') ? model.split('/').slice(1).join('/') : model}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* API Key Input */}
            <div className="mb-4">
              <label htmlFor="api-key-input" className="block text-sm font-medium text-gray-700 mb-1">
                {t('apiKeyPrompt.apiKey')}
              </label>
              <input
                id="api-key-input"
                type="password"
                value={apiKey}
                onChange={(e) => {
                  setApiKey(e.target.value);
                  setError('');
                  setTestResult(null);
                }}
                placeholder={t('apiKeyPrompt.apiKeyPlaceholder')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                aria-describedby="api-key-security-note"
              />
              <p id="api-key-security-note" className="mt-1 text-xs text-gray-500">
                {t('apiKeyPrompt.securityNote')}
              </p>
            </div>

            {/* Error Message */}
            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
                {error}
              </div>
            )}

            {/* Test Result */}
            {testResult && (
              <div className={`mb-4 p-3 rounded-md text-sm ${
                testResult.success
                  ? 'bg-green-50 border border-green-200 text-green-700'
                  : 'bg-red-50 border border-red-200 text-red-700'
              }`}>
                <div className="flex items-start">
                  {testResult.success ? (
                    <svg className="w-5 h-5 mr-2 flex-shrink-0 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5 mr-2 flex-shrink-0 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                  )}
                  <span>{testResult.message}</span>
                </div>
              </div>
            )}

            {/* Buttons */}
            <div className="flex gap-3 mt-6">
              <button
                type="button"
                onClick={handleTestConnection}
                disabled={!apiKey || testing}
                className={`flex-1 py-2 px-4 text-sm font-medium rounded-md transition-colors ${
                  apiKey && !testing
                    ? 'bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-300'
                    : 'bg-gray-50 text-gray-400 cursor-not-allowed border border-gray-200'
                }`}
              >
                {testing ? (
                  <span className="flex items-center justify-center">
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-gray-500" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    {t('apiKeyPrompt.testing')}
                  </span>
                ) : (
                  t('apiKeyPrompt.testConnection')
                )}
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={!apiKey}
                className={`flex-1 py-2 px-4 text-sm font-medium rounded-md transition-colors ${
                  apiKey
                    ? 'bg-blue-600 text-white hover:bg-blue-700'
                    : 'bg-blue-300 text-white cursor-not-allowed'
                }`}
              >
                {t('apiKeyPrompt.continue')}
              </button>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="w-full mt-3 py-2 px-4 text-sm font-medium text-gray-600 hover:text-gray-800"
            >
              {t('common.cancel')}
            </button>
          </>
        )}
      </div>
    </div>
  );
};

export default ApiKeyPrompt;
