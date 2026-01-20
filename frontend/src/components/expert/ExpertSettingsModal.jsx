import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { expertSettingsAPI } from '../../services/api';
import LanguageSelector from './LanguageSelector';
import PromptEditor from './PromptEditor';
import LLMConfigSection from '../common/LLMConfigSection';

const ExpertSettingsModal = ({ isOpen, onClose, sessionUuid }) => {
  const { t, i18n } = useTranslation();

  const PROMPT_TABS = [
    {
      key: 'brainstorming_system',
      label: t('expertSettings.prompts.brainstormingSystem'),
      shortLabel: t('expertSettings.prompts.tabs.system'),
      description: t('expertSettings.prompts.brainstormingSystemDesc'),
      variables: ['company_context'],
    },
    {
      key: 'brainstorming_round1',
      label: t('expertSettings.prompts.round1Prompt'),
      shortLabel: t('expertSettings.prompts.tabs.round1'),
      description: t('expertSettings.prompts.round1Desc'),
      variables: ['round_number', 'uniqueness_note'],
    },
    {
      key: 'brainstorming_subsequent',
      label: t('expertSettings.prompts.subsequentRounds'),
      shortLabel: t('expertSettings.prompts.tabs.rounds26'),
      description: t('expertSettings.prompts.subsequentDesc'),
      variables: ['round_number', 'previous_ideas_numbered', 'uniqueness_note'],
    },
    {
      key: 'consultation_system',
      label: t('expertSettings.prompts.consultationSystem'),
      shortLabel: t('expertSettings.prompts.tabs.consultation'),
      description: t('expertSettings.prompts.consultationDesc'),
      variables: ['company_name', 'company_info_text', 'top_ideas_text', 'focus_idea'],
    },
    {
      key: 'extraction_summary',
      label: t('expertSettings.prompts.summaryExtraction'),
      shortLabel: t('expertSettings.prompts.tabs.summary'),
      description: t('expertSettings.prompts.summaryDesc'),
      variables: [],
    },
  ];

  const [expertMode, setExpertMode] = useState(false);
  const [language, setLanguage] = useState('en');
  const [customPrompts, setCustomPrompts] = useState({});
  const [defaultPrompts, setDefaultPrompts] = useState({ en: {}, de: {} });
  const [activeTab, setActiveTab] = useState('brainstorming_system');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // LLM Configuration state
  const [llmConfig, setLlmConfig] = useState({ model: '', api_key: '', api_base: '' });

  // Load settings when modal opens
  useEffect(() => {
    if (isOpen && sessionUuid) {
      loadSettings();
    }
  }, [isOpen, sessionUuid]);

  const loadSettings = async () => {
    setLoading(true);
    setError(null);
    try {
      const [settingsRes, defaultsRes] = await Promise.all([
        expertSettingsAPI.get(sessionUuid),
        expertSettingsAPI.getDefaults(),
      ]);

      setExpertMode(settingsRes.data.expert_mode || false);
      const lang = settingsRes.data.prompt_language || 'en';
      setLanguage(lang);
      // Sync i18n language with session language
      i18n.changeLanguage(lang);
      setCustomPrompts(settingsRes.data.custom_prompts || {});
      setDefaultPrompts(defaultsRes.data);

      // Load LLM config if present
      if (settingsRes.data.llm_config) {
        const config = settingsRes.data.llm_config;
        setLlmConfig({
          model: config.model || '',
          api_key: '', // Don't show masked key, user can enter new one
          api_base: config.api_base || '',
        });
      }
    } catch (err) {
      console.error('Failed to load expert settings:', err);
      setError(t('errors.failedToLoad'));
    } finally {
      setLoading(false);
    }
  };

  const handleLanguageChange = (newLang) => {
    setLanguage(newLang);
    // Also change i18n language for the whole app
    i18n.changeLanguage(newLang);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      // Build LLM config if any field is set
      let llmConfigData = null;
      if (llmConfig.model || llmConfig.api_key || llmConfig.api_base) {
        llmConfigData = {
          model: llmConfig.model || null,
          api_key: llmConfig.api_key || null, // Only send if user entered a new key
          api_base: llmConfig.api_base || null,
        };
      }

      await expertSettingsAPI.update(sessionUuid, {
        expert_mode: expertMode,
        prompt_language: language,
        custom_prompts: Object.keys(customPrompts).length > 0 ? customPrompts : null,
        llm_config: llmConfigData,
      });
      onClose();
    } catch (err) {
      console.error('Failed to save settings:', err);
      setError(t('errors.failedToSave'));
    } finally {
      setSaving(false);
    }
  };

  const handlePromptChange = (key, value) => {
    setCustomPrompts((prev) => {
      const updated = { ...prev };
      if (value === null || value === undefined || value === '') {
        delete updated[key];
      } else {
        updated[key] = value;
      }
      return updated;
    });
  };

  const handleResetAll = async () => {
    if (window.confirm(t('expertSettings.prompts.resetConfirm'))) {
      setCustomPrompts({});
      try {
        await expertSettingsAPI.resetAll(sessionUuid);
      } catch (err) {
        console.error('Failed to reset prompts:', err);
      }
    }
  };

  if (!isOpen) return null;

  const currentDefaultPrompts = defaultPrompts[language] || defaultPrompts.en || {};
  const activePromptInfo = PROMPT_TABS.find((tab) => tab.key === activeTab);

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
        {/* Background overlay */}
        <div
          className="fixed inset-0 transition-opacity bg-gray-500 bg-opacity-75"
          onClick={onClose}
        />

        {/* Modal panel */}
        <div className="inline-block w-full max-w-4xl px-4 pt-5 pb-4 overflow-hidden text-left align-bottom transition-all transform bg-white rounded-lg shadow-xl sm:my-8 sm:align-middle sm:p-6">
          {/* Header */}
          <div className="flex justify-between items-center mb-4 pb-4 border-b">
            <h3 className="text-lg font-medium text-gray-900">{t('expertSettings.title')}</h3>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-500"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {loading ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : (
            <>
              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
                  {error}
                </div>
              )}

              {/* Expert Mode Toggle */}
              <div className="mb-6 flex items-center justify-between">
                <div>
                  <label className="text-sm font-medium text-gray-700">
                    {t('expertSettings.expertMode')}
                  </label>
                  <p className="text-xs text-gray-500">
                    {t('expertSettings.expertModeDesc')}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setExpertMode(!expertMode)}
                  className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                    expertMode ? 'bg-blue-600' : 'bg-gray-200'
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                      expertMode ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>

              {expertMode && (
                <>
                  {/* LLM Configuration */}
                  <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
                    <LLMConfigSection
                      config={llmConfig}
                      onChange={(newConfig) => setLlmConfig(newConfig)}
                      showTitle={true}
                      compact={false}
                    />
                  </div>

                  {/* Language Selector */}
                  <div className="mb-6 p-4 bg-gray-50 rounded-lg">
                    <LanguageSelector
                      value={language}
                      onChange={handleLanguageChange}
                    />
                    <p className="mt-2 text-xs text-gray-500">
                      {t('expertSettings.language.note')}
                    </p>
                  </div>

                  {/* Prompt Tabs */}
                  <div className="mb-4">
                    <div className="flex justify-between items-center mb-2">
                      <h4 className="text-sm font-medium text-gray-700">{t('expertSettings.prompts.title')}</h4>
                      <button
                        type="button"
                        onClick={handleResetAll}
                        className="text-sm text-gray-500 hover:text-gray-700"
                      >
                        {t('expertSettings.prompts.resetAll')}
                      </button>
                    </div>
                    <div className="border-b border-gray-200">
                      <nav className="-mb-px flex space-x-4 overflow-x-auto" aria-label="Tabs">
                        {PROMPT_TABS.map((tab) => {
                          const isCustomized = customPrompts[tab.key];
                          return (
                            <button
                              key={tab.key}
                              onClick={() => setActiveTab(tab.key)}
                              className={`whitespace-nowrap py-2 px-3 border-b-2 font-medium text-sm ${
                                activeTab === tab.key
                                  ? 'border-blue-500 text-blue-600'
                                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                              }`}
                            >
                              {tab.shortLabel}
                              {isCustomized && (
                                <span className="ml-1 w-2 h-2 inline-block rounded-full bg-yellow-400"></span>
                              )}
                            </button>
                          );
                        })}
                      </nav>
                    </div>
                  </div>

                  {/* Prompt Editor */}
                  {activePromptInfo && (
                    <PromptEditor
                      promptKey={activePromptInfo.key}
                      label={activePromptInfo.label}
                      description={activePromptInfo.description}
                      variables={activePromptInfo.variables}
                      customValue={customPrompts[activePromptInfo.key]}
                      defaultValue={currentDefaultPrompts[activePromptInfo.key]}
                      onChange={handlePromptChange}
                    />
                  )}
                </>
              )}

              {/* Footer */}
              <div className="mt-6 flex justify-end gap-3 pt-4 border-t">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  {saving ? t('common.saving') : t('common.saveChanges')}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ExpertSettingsModal;
