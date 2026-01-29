import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { expertSettingsAPI } from '../../services/api';

const LLMConfigSection = ({
  config,
  onChange,
  showTitle = true,
  compact = false,
  className = ''
}) => {
  const { t } = useTranslation();
  const [llmProviders, setLlmProviders] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState('');
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [availableModels, setAvailableModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelsMessage, setModelsMessage] = useState(null);
  const [modelsFallback, setModelsFallback] = useState(false);

  useEffect(() => {
    loadProviders();
  }, []);

  // When config changes externally (e.g., loaded from session), match the provider
  useEffect(() => {
    if (config.api_base && llmProviders.length > 0) {
      const matchedProvider = llmProviders.find(p => p.api_base === config.api_base);
      if (matchedProvider && matchedProvider.name !== selectedProvider) {
        setSelectedProvider(matchedProvider.name);
        // Set initial models from hardcoded list
        setAvailableModels(matchedProvider.models || []);
      }
    }
  }, [config.api_base, llmProviders]);

  // Fetch models when provider changes and API key is available
  const fetchModelsFromProvider = useCallback(async (apiBase, apiKey) => {
    if (!apiBase || !apiKey) {
      return;
    }

    setLoadingModels(true);
    setModelsMessage(null);
    setModelsFallback(false);

    try {
      const response = await expertSettingsAPI.fetchModels(apiBase, apiKey);
      const data = response.data;

      if (data.models && data.models.length > 0) {
        setAvailableModels(data.models);
        setModelsFallback(data.fallback || false);
        if (data.message) {
          setModelsMessage(data.message);
        }
      }
    } catch (err) {
      console.error('Failed to fetch models:', err);
      // Keep using existing models (fallback)
      setModelsMessage(t('expertSettings.llmConfig.fetchModelsFailed', 'Could not fetch models from provider'));
      setModelsFallback(true);
    } finally {
      setLoadingModels(false);
    }
  }, [t]);

  // Auto-fetch models when API key changes and provider is selected
  useEffect(() => {
    if (selectedProvider && config.api_key && config.api_base) {
      // Debounce the fetch to avoid too many requests while typing
      const timeoutId = setTimeout(() => {
        fetchModelsFromProvider(config.api_base, config.api_key);
      }, 500);
      return () => clearTimeout(timeoutId);
    }
  }, [config.api_key, config.api_base, selectedProvider, fetchModelsFromProvider]);

  const loadProviders = async () => {
    try {
      const res = await expertSettingsAPI.getLLMProviders();
      setLlmProviders(res.data || []);
    } catch (err) {
      console.error('Failed to load LLM providers:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleProviderChange = (providerName) => {
    setSelectedProvider(providerName);
    setModelsMessage(null);
    setModelsFallback(false);
    const provider = llmProviders.find(p => p.name === providerName);
    if (provider) {
      // Set hardcoded models initially
      setAvailableModels(provider.models || []);
      onChange({
        ...config,
        api_base: provider.api_base,
        model: provider.models[0] || '',
      });
      // If API key is already set, fetch dynamic models
      if (config.api_key && provider.api_base) {
        fetchModelsFromProvider(provider.api_base, config.api_key);
      }
    }
  };

  const handleFieldChange = (field, value) => {
    onChange({ ...config, [field]: value });
    // Clear test result when config changes
    setTestResult(null);
  };

  const handleTestConnection = async () => {
    if (!config.model || !config.api_key) {
      setTestResult({
        success: false,
        message: t('expertSettings.llmConfig.testMissingFields')
      });
      return;
    }

    // Check if model has openai/ prefix but no api_base (would call real OpenAI)
    if (config.model.startsWith('openai/') && !config.api_base) {
      setTestResult({
        success: false,
        message: 'Model uses "openai/" prefix but no API base URL is set. Please select a provider.'
      });
      return;
    }

    setTesting(true);
    setTestResult(null);

    // Debug logging
    console.log('[LLM Test] Sending config:', {
      model: config.model,
      api_base: config.api_base,
      api_key: config.api_key ? `${config.api_key.substring(0, 10)}...` : 'none'
    });

    try {
      const response = await expertSettingsAPI.testLLM({
        model: config.model,
        api_key: config.api_key,
        api_base: config.api_base || null
      });

      setTestResult(response.data);
    } catch (err) {
      setTestResult({
        success: false,
        message: err.response?.data?.message || t('expertSettings.llmConfig.testFailed')
      });
    } finally {
      setTesting(false);
    }
  };

  const canTest = config.model && config.api_key;

  if (loading) {
    return (
      <div className={`flex justify-center py-4 ${className}`}>
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  const inputSize = compact ? 'px-3 py-1.5 text-sm' : 'px-3 py-2 text-sm';

  return (
    <div className={className}>
      {showTitle && (
        <h4 className="text-sm font-medium text-gray-700 mb-3">
          {t('expertSettings.llmConfig.title')}
        </h4>
      )}

      {/* Provider Selection */}
      <div className="mb-3">
        <label className="block text-xs font-medium text-gray-600 mb-1">
          {t('expertSettings.llmConfig.provider')}
        </label>
        <select
          value={selectedProvider}
          onChange={(e) => handleProviderChange(e.target.value)}
          className={`w-full ${inputSize} border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500`}
        >
          <option value="">{t('expertSettings.llmConfig.selectProvider')}</option>
          {llmProviders.map((provider) => (
            <option key={provider.name} value={provider.name}>
              {provider.name}
            </option>
          ))}
        </select>
      </div>

      {/* Model Selection */}
      {selectedProvider && (
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1">
            <label className="block text-xs font-medium text-gray-600">
              {t('expertSettings.llmConfig.model')}
            </label>
            {config.api_key && config.api_base && (
              <button
                type="button"
                onClick={() => fetchModelsFromProvider(config.api_base, config.api_key)}
                disabled={loadingModels}
                className="text-xs text-blue-600 hover:text-blue-800 flex items-center"
                title={t('expertSettings.llmConfig.refreshModels', 'Refresh model list from provider')}
              >
                {loadingModels ? (
                  <svg className="animate-spin h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                ) : (
                  <svg className="h-3 w-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                )}
                {t('expertSettings.llmConfig.refresh', 'Refresh')}
              </button>
            )}
          </div>
          <div className="relative">
            <select
              value={config.model}
              onChange={(e) => handleFieldChange('model', e.target.value)}
              disabled={loadingModels}
              className={`w-full ${inputSize} border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${loadingModels ? 'opacity-50' : ''}`}
            >
              <option value="">{loadingModels ? t('expertSettings.llmConfig.loadingModels', 'Loading models...') : t('expertSettings.llmConfig.selectModel')}</option>
              {availableModels.map((model) => (
                <option key={model} value={model}>
                  {/* Display model name without provider prefix for cleaner UI */}
                  {model.includes('/') ? model.split('/').slice(1).join('/') : model}
                </option>
              ))}
            </select>
          </div>
          {/* Model fetch status message */}
          {modelsMessage && (
            <p className={`mt-1 text-xs ${modelsFallback ? 'text-amber-600' : 'text-green-600'}`}>
              {modelsFallback && (
                <svg className="inline h-3 w-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              )}
              {modelsMessage}
            </p>
          )}
          {!config.api_key && selectedProvider && (
            <p className="mt-1 text-xs text-gray-500">
              {t('expertSettings.llmConfig.enterApiKeyForModels', 'Enter API key to fetch available models')}
            </p>
          )}
        </div>
      )}

      {/* API Key */}
      <div className="mb-3">
        <label className="block text-xs font-medium text-gray-600 mb-1">
          {t('expertSettings.llmConfig.apiKey')}
        </label>
        <input
          type="password"
          value={config.api_key}
          onChange={(e) => handleFieldChange('api_key', e.target.value)}
          placeholder={t('expertSettings.llmConfig.apiKeyPlaceholder')}
          className={`w-full ${inputSize} border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500`}
        />
        {!compact && (
          <p className="mt-1 text-xs text-gray-500">
            {t('expertSettings.llmConfig.apiKeyNote')}
          </p>
        )}
      </div>

      {/* API Base URL (advanced) - only show if not compact */}
      {!compact && (
        <div className="mb-3">
          <label className="block text-xs font-medium text-gray-600 mb-1">
            {t('expertSettings.llmConfig.apiBase')}
          </label>
          <input
            type="text"
            value={config.api_base}
            onChange={(e) => handleFieldChange('api_base', e.target.value)}
            placeholder={t('expertSettings.llmConfig.apiBasePlaceholder')}
            className={`w-full ${inputSize} border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500`}
          />
        </div>
      )}

      {/* Test Connection Button */}
      <div className="mt-3">
        <button
          type="button"
          onClick={handleTestConnection}
          disabled={!canTest || testing}
          className={`w-full ${compact ? 'py-1.5 text-xs' : 'py-2 text-sm'} px-4 font-medium rounded-md transition-colors ${
            canTest && !testing
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
              {t('expertSettings.llmConfig.testing')}
            </span>
          ) : (
            t('expertSettings.llmConfig.testConnection')
          )}
        </button>

        {/* Test Result */}
        {testResult && (
          <div className={`mt-2 p-2 rounded-md text-xs ${
            testResult.success
              ? 'bg-green-50 border border-green-200 text-green-700'
              : 'bg-red-50 border border-red-200 text-red-700'
          }`}>
            <div className="flex items-start">
              {testResult.success ? (
                <svg className="w-4 h-4 mr-1.5 flex-shrink-0 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
              ) : (
                <svg className="w-4 h-4 mr-1.5 flex-shrink-0 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              )}
              <span>{testResult.message}</span>
            </div>
            {testResult.response_preview && (
              <div className="mt-1 text-xs text-gray-500 italic">
                "{testResult.response_preview}"
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default LLMConfigSection;
