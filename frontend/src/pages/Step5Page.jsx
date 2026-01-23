import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import { companyInfoAPI, prioritizationAPI, consultationAPI, businessCaseAPI, apiKeyManager } from '../services/api';
import { PageHeader, ExplanationBox } from '../components/common';
import ApiKeyPrompt from '../components/common/ApiKeyPrompt';

const Step5Page = () => {
  const { t } = useTranslation();
  const { sessionUuid } = useParams();
  const navigate = useNavigate();
  const messagesEndRef = useRef(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Context from previous steps
  const [companyInfo, setCompanyInfo] = useState([]);
  const [topIdea, setTopIdea] = useState(null);
  const [crispDmFindings, setCrispDmFindings] = useState(null);
  const [contextExpanded, setContextExpanded] = useState(false);

  // Chat state
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);
  const [businessCaseStarted, setBusinessCaseStarted] = useState(false);

  // Business case findings
  const [findings, setFindings] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [showApiKeyPrompt, setShowApiKeyPrompt] = useState(false);
  const [pendingAction, setPendingAction] = useState(null); // 'start' or 'extract'

  useEffect(() => {
    loadData();
  }, [sessionUuid]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadData = async () => {
    try {
      // Load company info (Step 1)
      try {
        const companyResponse = await companyInfoAPI.getAll(sessionUuid);
        setCompanyInfo(companyResponse.data || []);
      } catch (e) {
        console.log('No company info');
      }

      // Load top idea (Step 3)
      try {
        const resultsResponse = await prioritizationAPI.getResults(sessionUuid);
        if (resultsResponse.data.top_ideas?.length > 0) {
          setTopIdea(resultsResponse.data.top_ideas[0]);
        }
      } catch (e) {
        console.log('No prioritization results');
      }

      // Load CRISP-DM findings (Step 4)
      try {
        const findingsResponse = await consultationAPI.getFindings(sessionUuid);
        if (findingsResponse.data.business_objectives || findingsResponse.data.situation_assessment ||
            findingsResponse.data.ai_goals || findingsResponse.data.project_plan) {
          setCrispDmFindings(findingsResponse.data);
        }
      } catch (e) {
        console.log('No CRISP-DM findings');
      }

      // Load existing business case messages
      try {
        const messagesResponse = await businessCaseAPI.getMessages(sessionUuid);
        if (messagesResponse.data.length > 0) {
          setMessages(messagesResponse.data);
          setBusinessCaseStarted(true);
        }
      } catch (e) {
        console.log('No existing business case messages');
      }

      // Load business case findings
      try {
        const bcFindingsResponse = await businessCaseAPI.getFindings(sessionUuid);
        if (bcFindingsResponse.data.classification || bcFindingsResponse.data.calculation ||
            bcFindingsResponse.data.validation_questions || bcFindingsResponse.data.management_pitch) {
          setFindings(bcFindingsResponse.data);
        }
      } catch (e) {
        console.log('No business case findings');
      }
    } catch (err) {
      console.error('Failed to load data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleStartBusinessCase = async () => {
    // Check if API key is set
    if (!apiKeyManager.isSet()) {
      setPendingAction('start');
      setShowApiKeyPrompt(true);
      return;
    }

    setSendingMessage(true);
    setBusinessCaseStarted(true);

    // Add placeholder message for streaming
    const placeholderId = Date.now();
    setMessages([{
      id: placeholderId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString()
    }]);

    try {
      await businessCaseAPI.startStream(
        sessionUuid,
        (chunk) => {
          setMessages(prev => {
            const updated = [...prev];
            const lastIdx = updated.length - 1;
            if (lastIdx >= 0 && updated[lastIdx].id === placeholderId) {
              updated[lastIdx] = {
                ...updated[lastIdx],
                content: updated[lastIdx].content + chunk
              };
            }
            return updated;
          });
        },
        () => {
          setSendingMessage(false);
        },
        (errorMsg) => {
          setError(errorMsg || 'Failed to start business case');
          setSendingMessage(false);
        }
      );
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start business case');
      setSendingMessage(false);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || sendingMessage) return;

    const userMessage = inputMessage.trim();
    setInputMessage('');
    setSendingMessage(true);

    // Add user message immediately to UI
    const userMsgId = Date.now();
    setMessages(prev => [...prev, {
      id: userMsgId,
      role: 'user',
      content: userMessage,
      created_at: new Date().toISOString()
    }]);

    try {
      await businessCaseAPI.saveMessage(sessionUuid, userMessage);

      const aiMsgId = Date.now() + 1;
      setMessages(prev => [...prev, {
        id: aiMsgId,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString()
      }]);

      await businessCaseAPI.requestAiResponseStream(
        sessionUuid,
        (chunk) => {
          setMessages(prev => {
            const updated = [...prev];
            const aiIdx = updated.findIndex(m => m.id === aiMsgId);
            if (aiIdx >= 0) {
              updated[aiIdx] = {
                ...updated[aiIdx],
                content: updated[aiIdx].content + chunk
              };
            }
            return updated;
          });
        },
        () => {
          setSendingMessage(false);
        },
        (errorMsg) => {
          setError(errorMsg || 'Failed to get AI response');
          setSendingMessage(false);
          setMessages(prev => prev.filter(m => m.id !== aiMsgId || m.content));
        }
      );
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to send message');
      setSendingMessage(false);
    }
  };

  const handleExtractFindings = async () => {
    // Check if API key is set
    if (!apiKeyManager.isSet()) {
      setPendingAction('extract');
      setShowApiKeyPrompt(true);
      return;
    }

    setExtracting(true);
    try {
      const response = await businessCaseAPI.extract(sessionUuid);
      setFindings(response.data.findings);

      if (response.data.summary) {
        setMessages(prev => [...prev, {
          id: Date.now(),
          role: 'assistant',
          content: response.data.summary,
          created_at: new Date().toISOString()
        }]);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to extract business case');
    } finally {
      setExtracting(false);
    }
  };

  // Summarize company info for display
  const getCompanySummary = () => {
    if (!companyInfo.length) return null;
    const first = companyInfo[0];
    if (!first.content) return null;
    return first.content.substring(0, 200) + (first.content.length > 200 ? '...' : '');
  };

  const handleApiKeySet = () => {
    setShowApiKeyPrompt(false);
    // Execute the pending action now that we have the API key
    if (pendingAction === 'start') {
      handleStartBusinessCase();
    } else if (pendingAction === 'extract') {
      handleExtractFindings();
    }
    setPendingAction(null);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">{t('common.loading')}</p>
      </div>
    );
  }

  const hasContext = companyInfo.length > 0 || topIdea || crispDmFindings;

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <PageHeader
        title={t('step5.title')}
        subtitle={t('step5.subtitle')}
        sessionUuid={sessionUuid}
      />

      <div className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 w-full">
        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* Explanation - show when business case hasn't started */}
        {!businessCaseStarted && (
          <ExplanationBox
            title={t('step5.explanation.title')}
            description={t('step5.explanation.description')}
            bullets={[
              t('step5.explanation.bullet1'),
              t('step5.explanation.bullet2'),
              t('step5.explanation.bullet3'),
              t('step5.explanation.bullet4'),
              t('step5.explanation.bullet5'),
            ]}
            tip={t('step5.explanation.tip')}
            variant="green"
            defaultOpen={true}
          />
        )}

        {/* Context Panel (Collapsible) */}
        {hasContext && (
          <div className="mb-4 bg-gray-100 border border-gray-200 rounded-lg overflow-hidden">
            <button
              onClick={() => setContextExpanded(!contextExpanded)}
              className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-150 transition-colors"
            >
              <span className="font-medium text-gray-700">{t('step5.chat.contextTitle')}</span>
              <svg
                className={`w-5 h-5 text-gray-500 transform transition-transform ${contextExpanded ? 'rotate-180' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {contextExpanded && (
              <div className="px-4 pb-4 space-y-3">
                {/* Company Profile */}
                {companyInfo.length > 0 && (
                  <div className="bg-white rounded p-3">
                    <h4 className="text-sm font-semibold text-gray-700 mb-1">{t('step5.chat.companyProfile')}</h4>
                    <p className="text-xs text-gray-600">{getCompanySummary()}</p>
                  </div>
                )}
                {/* Focus Idea */}
                {topIdea && (
                  <div className="bg-white rounded p-3">
                    <h4 className="text-sm font-semibold text-gray-700 mb-1">{t('step5.chat.focusIdea')}</h4>
                    <p className="text-xs text-gray-600">{topIdea.idea_content}</p>
                  </div>
                )}
                {/* CRISP-DM Summary */}
                {crispDmFindings && (
                  <div className="bg-white rounded p-3">
                    <h4 className="text-sm font-semibold text-gray-700 mb-1">{t('step5.chat.crispDmSummary')}</h4>
                    <div className="text-xs text-gray-600 space-y-1">
                      {crispDmFindings.business_objectives && (
                        <p><strong>{t('step4.findings.businessObjectives')}:</strong> {crispDmFindings.business_objectives.substring(0, 100)}...</p>
                      )}
                      {crispDmFindings.ai_goals && (
                        <p><strong>{t('step4.findings.aiGoals')}:</strong> {crispDmFindings.ai_goals.substring(0, 100)}...</p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Main business case area */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Chat area - 2/3 width */}
          <div className="lg:col-span-2 flex flex-col bg-white rounded-lg shadow h-[600px]">
            {/* Top idea banner */}
            {topIdea && (
              <div className="bg-yellow-50 border-b border-yellow-200 px-4 py-3">
                <p className="text-sm font-medium text-yellow-800">
                  {t('step4.chat.focus')} {topIdea.idea_content}
                </p>
              </div>
            )}

            {/* Messages area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {!businessCaseStarted ? (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <p className="text-gray-600 mb-4">
                      {t('step5.chat.startMessage')}
                    </p>
                    <button
                      onClick={handleStartBusinessCase}
                      disabled={sendingMessage}
                      className="bg-blue-600 text-white py-3 px-8 rounded-md hover:bg-blue-700 disabled:bg-gray-300 transition-colors font-medium"
                    >
                      {sendingMessage ? t('step5.chat.starting') : t('step5.chat.startButton')}
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  {messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-[80%] rounded-lg px-4 py-3 ${
                          msg.role === 'user'
                            ? 'bg-blue-600 text-white'
                            : 'bg-gray-100 text-gray-900'
                        }`}
                      >
                        <div className={`text-sm max-w-none ${
                          msg.role === 'user'
                            ? ''
                            : 'prose prose-sm prose-gray'
                        }`}>
                          <ReactMarkdown
                            components={{
                              p: ({children}) => <p className="mb-2 last:mb-0">{children}</p>,
                              ul: ({children}) => <ul className={`list-disc ml-4 mb-2 ${msg.role === 'user' ? 'text-white' : ''}`}>{children}</ul>,
                              ol: ({children}) => <ol className={`list-decimal ml-4 mb-2 ${msg.role === 'user' ? 'text-white' : ''}`}>{children}</ol>,
                              li: ({children}) => <li className="mb-1">{children}</li>,
                              strong: ({children}) => <strong className="font-semibold">{children}</strong>,
                              em: ({children}) => <em className="italic">{children}</em>,
                              h1: ({children}) => <h1 className={`text-lg font-bold mb-2 mt-3 first:mt-0 ${msg.role === 'user' ? 'text-white' : 'text-gray-900'}`}>{children}</h1>,
                              h2: ({children}) => <h2 className={`text-base font-bold mb-2 mt-3 first:mt-0 ${msg.role === 'user' ? 'text-white' : 'text-gray-900'}`}>{children}</h2>,
                              h3: ({children}) => <h3 className={`text-sm font-bold mb-1 mt-2 first:mt-0 ${msg.role === 'user' ? 'text-white' : 'text-gray-900'}`}>{children}</h3>,
                              h4: ({children}) => <h4 className={`text-sm font-semibold mb-1 mt-2 first:mt-0 ${msg.role === 'user' ? 'text-white' : 'text-gray-900'}`}>{children}</h4>,
                              code: ({inline, children}) => inline
                                ? <code className={`px-1 py-0.5 rounded text-xs font-mono ${msg.role === 'user' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-800'}`}>{children}</code>
                                : <code className={`block p-2 rounded text-xs font-mono my-2 overflow-x-auto ${msg.role === 'user' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-800'}`}>{children}</code>,
                              blockquote: ({children}) => <blockquote className={`border-l-4 pl-3 my-2 italic ${msg.role === 'user' ? 'border-blue-300 text-blue-100' : 'border-gray-300 text-gray-600'}`}>{children}</blockquote>,
                              hr: () => <hr className={`my-3 ${msg.role === 'user' ? 'border-blue-400' : 'border-gray-300'}`} />,
                              table: ({children}) => <table className="min-w-full border border-gray-300 my-2">{children}</table>,
                              thead: ({children}) => <thead className="bg-gray-100">{children}</thead>,
                              tbody: ({children}) => <tbody>{children}</tbody>,
                              tr: ({children}) => <tr className="border-b border-gray-300">{children}</tr>,
                              th: ({children}) => <th className="px-2 py-1 text-left text-xs font-semibold border-r border-gray-300 last:border-r-0">{children}</th>,
                              td: ({children}) => <td className="px-2 py-1 text-xs border-r border-gray-300 last:border-r-0">{children}</td>,
                            }}
                          >
                            {msg.content}
                          </ReactMarkdown>
                        </div>
                      </div>
                    </div>
                  ))}
                  {sendingMessage && messages.length > 0 && messages[messages.length - 1].content === '' && (
                    <div className="flex justify-start">
                      <div className="bg-gray-100 rounded-lg px-4 py-3">
                        <p className="text-gray-500 text-sm animate-pulse">{t('step5.chat.thinking')}</p>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </>
              )}
            </div>

            {/* Input area */}
            {businessCaseStarted && (
              <div className="border-t p-4">
                <form onSubmit={handleSendMessage} className="flex gap-2">
                  <input
                    type="text"
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    placeholder={t('step5.chat.messagePlaceholder')}
                    disabled={sendingMessage}
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    type="submit"
                    disabled={sendingMessage || !inputMessage.trim()}
                    className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-300 transition-colors"
                  >
                    {t('common.send')}
                  </button>
                </form>
                <div className="mt-2 flex justify-end">
                  <button
                    onClick={handleExtractFindings}
                    disabled={extracting || messages.length < 4}
                    className="text-sm text-blue-600 hover:text-blue-800 disabled:text-gray-400"
                  >
                    {extracting ? t('step5.chat.extracting') : t('step5.chat.extractFindings')}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Business Case Findings sidebar - 1/3 width */}
          <div className="space-y-4">
            {/* 5-Level Framework Header */}
            <div className="bg-green-50 border border-green-200 rounded-lg p-3">
              <h3 className="font-semibold text-green-800 text-sm">{t('step5.findings.title')}</h3>
              <p className="text-xs text-green-600 mt-1">{t('step5.findings.subtitle')}</p>
            </div>

            {/* 1. Classification */}
            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
                <span className="bg-green-100 text-green-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">1</span>
                {t('step5.findings.classification')}
              </h3>
              {findings?.classification ? (
                <div className="text-sm text-gray-700 prose prose-sm max-w-none">
                  <ReactMarkdown>{findings.classification}</ReactMarkdown>
                </div>
              ) : (
                <p className="text-sm text-gray-400 italic">
                  {t('step5.findings.classificationPlaceholder')}
                </p>
              )}
            </div>

            {/* 2. Calculation */}
            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
                <span className="bg-green-100 text-green-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">2</span>
                {t('step5.findings.calculation')}
              </h3>
              {findings?.calculation ? (
                <div className="text-sm text-gray-700 prose prose-sm max-w-none">
                  <ReactMarkdown>{findings.calculation}</ReactMarkdown>
                </div>
              ) : (
                <p className="text-sm text-gray-400 italic">
                  {t('step5.findings.calculationPlaceholder')}
                </p>
              )}
            </div>

            {/* 3. Validation Questions */}
            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
                <span className="bg-green-100 text-green-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">3</span>
                {t('step5.findings.validationQuestions')}
              </h3>
              {findings?.validation_questions ? (
                <div className="text-sm text-gray-700 prose prose-sm max-w-none">
                  <ReactMarkdown>{findings.validation_questions}</ReactMarkdown>
                </div>
              ) : (
                <p className="text-sm text-gray-400 italic">
                  {t('step5.findings.validationPlaceholder')}
                </p>
              )}
            </div>

            {/* 4. Management Pitch */}
            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
                <span className="bg-green-100 text-green-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">4</span>
                {t('step5.findings.managementPitch')}
              </h3>
              {findings?.management_pitch ? (
                <div className="text-sm text-gray-700 prose prose-sm max-w-none font-medium">
                  <ReactMarkdown>{findings.management_pitch}</ReactMarkdown>
                </div>
              ) : (
                <p className="text-sm text-gray-400 italic">
                  {t('step5.findings.managementPitchPlaceholder')}
                </p>
              )}
            </div>

            {/* 5-Level Framework Reference */}
            <div className="bg-gray-50 rounded-lg p-3">
              <h4 className="text-xs font-semibold text-gray-700 mb-2">{t('step5.framework.title')}</h4>
              <div className="text-xs text-gray-600 space-y-1">
                <p><span className="font-medium">1.</span> {t('step5.framework.level1')}</p>
                <p><span className="font-medium">2.</span> {t('step5.framework.level2')}</p>
                <p><span className="font-medium">3.</span> {t('step5.framework.level3')}</p>
                <p><span className="font-medium">4.</span> {t('step5.framework.level4')}</p>
                <p><span className="font-medium">5.</span> {t('step5.framework.level5')}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <div className="mt-6 flex justify-between">
          <button
            onClick={() => navigate(`/session/${sessionUuid}/step4`)}
            className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
          >
            {t('step5.backStep4')}
          </button>
          <button
            onClick={() => navigate(`/session/${sessionUuid}/export`)}
            className="px-6 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
          >
            {t('step5.continueExport')}
          </button>
        </div>
      </div>

      {/* API Key Prompt Modal */}
      <ApiKeyPrompt
        isOpen={showApiKeyPrompt}
        onClose={() => setShowApiKeyPrompt(false)}
        onApiKeySet={handleApiKeySet}
      />
    </div>
  );
};

export default Step5Page;
