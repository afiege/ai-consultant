import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import { companyInfoAPI, prioritizationAPI, consultationAPI, businessCaseAPI, costEstimationAPI, apiKeyManager } from '../services/api';
import { PageHeader, ExplanationBox } from '../components/common';
import ApiKeyPrompt from '../components/common/ApiKeyPrompt';

const Step5Page = () => {
  const { t } = useTranslation();
  const { sessionUuid } = useParams();
  const navigate = useNavigate();
  const messagesEndRef = useRef(null);

  // Tab state: 'potentials' (5a) or 'costs' (5b)
  const [activeTab, setActiveTab] = useState('potentials');

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Context from previous steps
  const [companyInfo, setCompanyInfo] = useState([]);
  const [topIdea, setTopIdea] = useState(null);
  const [crispDmFindings, setCrispDmFindings] = useState(null);
  const [contextExpanded, setContextExpanded] = useState(false);

  // Step 5a (Potentials) state
  const [potentialsMessages, setPotentialsMessages] = useState([]);
  const [potentialsInput, setPotentialsInput] = useState('');
  const [potentialsSending, setPotentialsSending] = useState(false);
  const [potentialsStarted, setPotentialsStarted] = useState(false);
  const [potentialsFindings, setPotentialsFindings] = useState(null);
  const [potentialsExtracting, setPotentialsExtracting] = useState(false);

  // Step 5b (Costs) state
  const [costsMessages, setCostsMessages] = useState([]);
  const [costsInput, setCostsInput] = useState('');
  const [costsSending, setCostsSending] = useState(false);
  const [costsStarted, setCostsStarted] = useState(false);
  const [costsFindings, setCostsFindings] = useState(null);
  const [costsExtracting, setCostsExtracting] = useState(false);

  // API Key prompt state
  const [showApiKeyPrompt, setShowApiKeyPrompt] = useState(false);
  const [pendingAction, setPendingAction] = useState(null);

  useEffect(() => {
    loadData();
  }, [sessionUuid]);

  useEffect(() => {
    scrollToBottom();
  }, [potentialsMessages, costsMessages, activeTab]);

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

      // Load existing 5a (Potentials) messages
      try {
        const messagesResponse = await businessCaseAPI.getMessages(sessionUuid);
        if (messagesResponse.data.length > 0) {
          setPotentialsMessages(messagesResponse.data);
          setPotentialsStarted(true);
        }
      } catch (e) {
        console.log('No existing potentials messages');
      }

      // Load 5a (Potentials) findings
      try {
        const bcFindingsResponse = await businessCaseAPI.getFindings(sessionUuid);
        if (bcFindingsResponse.data.classification || bcFindingsResponse.data.calculation ||
            bcFindingsResponse.data.validation_questions || bcFindingsResponse.data.management_pitch) {
          setPotentialsFindings(bcFindingsResponse.data);
        }
      } catch (e) {
        console.log('No potentials findings');
      }

      // Load existing 5b (Costs) messages
      try {
        const costsMessagesResponse = await costEstimationAPI.getMessages(sessionUuid);
        if (costsMessagesResponse.data.length > 0) {
          setCostsMessages(costsMessagesResponse.data);
          setCostsStarted(true);
        }
      } catch (e) {
        console.log('No existing costs messages');
      }

      // Load 5b (Costs) findings
      try {
        const costsFindingsResponse = await costEstimationAPI.getFindings(sessionUuid);
        if (costsFindingsResponse.data.complexity || costsFindingsResponse.data.initial_investment ||
            costsFindingsResponse.data.tco) {
          setCostsFindings(costsFindingsResponse.data);
        }
      } catch (e) {
        console.log('No costs findings');
      }
    } catch (err) {
      console.error('Failed to load data:', err);
    } finally {
      setLoading(false);
    }
  };

  // 5a Potentials handlers
  const handleStartPotentials = async () => {
    if (!apiKeyManager.isSet()) {
      setPendingAction('start_potentials');
      setShowApiKeyPrompt(true);
      return;
    }

    setPotentialsSending(true);
    setPotentialsStarted(true);

    const placeholderId = Date.now();
    setPotentialsMessages([{
      id: placeholderId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString()
    }]);

    try {
      await businessCaseAPI.startStream(
        sessionUuid,
        (chunk) => {
          setPotentialsMessages(prev => {
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
        () => setPotentialsSending(false),
        (errorMsg) => {
          setError(errorMsg || 'Failed to start potentials analysis');
          setPotentialsSending(false);
        }
      );
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start potentials analysis');
      setPotentialsSending(false);
    }
  };

  const handleSendPotentialsMessage = async (e) => {
    e.preventDefault();
    if (!potentialsInput.trim() || potentialsSending) return;

    const userMessage = potentialsInput.trim();
    setPotentialsInput('');
    setPotentialsSending(true);

    const userMsgId = Date.now();
    setPotentialsMessages(prev => [...prev, {
      id: userMsgId,
      role: 'user',
      content: userMessage,
      created_at: new Date().toISOString()
    }]);

    try {
      await businessCaseAPI.saveMessage(sessionUuid, userMessage);

      const aiMsgId = Date.now() + 1;
      setPotentialsMessages(prev => [...prev, {
        id: aiMsgId,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString()
      }]);

      await businessCaseAPI.requestAiResponseStream(
        sessionUuid,
        (chunk) => {
          setPotentialsMessages(prev => {
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
        () => setPotentialsSending(false),
        (errorMsg) => {
          setError(errorMsg || 'Failed to get AI response');
          setPotentialsSending(false);
          setPotentialsMessages(prev => prev.filter(m => m.id !== aiMsgId || m.content));
        }
      );
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to send message');
      setPotentialsSending(false);
    }
  };

  const handleExtractPotentials = async () => {
    if (!apiKeyManager.isSet()) {
      setPendingAction('extract_potentials');
      setShowApiKeyPrompt(true);
      return;
    }

    setPotentialsExtracting(true);
    try {
      const response = await businessCaseAPI.extract(sessionUuid);
      setPotentialsFindings(response.data.findings);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to extract potentials');
    } finally {
      setPotentialsExtracting(false);
    }
  };

  // 5b Costs handlers
  const handleStartCosts = async () => {
    if (!apiKeyManager.isSet()) {
      setPendingAction('start_costs');
      setShowApiKeyPrompt(true);
      return;
    }

    setCostsSending(true);
    setCostsStarted(true);

    const placeholderId = Date.now();
    setCostsMessages([{
      id: placeholderId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString()
    }]);

    try {
      await costEstimationAPI.startStream(
        sessionUuid,
        (chunk) => {
          setCostsMessages(prev => {
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
        () => setCostsSending(false),
        (errorMsg) => {
          setError(errorMsg || 'Failed to start cost estimation');
          setCostsSending(false);
        }
      );
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start cost estimation');
      setCostsSending(false);
    }
  };

  const handleSendCostsMessage = async (e) => {
    e.preventDefault();
    if (!costsInput.trim() || costsSending) return;

    const userMessage = costsInput.trim();
    setCostsInput('');
    setCostsSending(true);

    const userMsgId = Date.now();
    setCostsMessages(prev => [...prev, {
      id: userMsgId,
      role: 'user',
      content: userMessage,
      created_at: new Date().toISOString()
    }]);

    try {
      await costEstimationAPI.saveMessage(sessionUuid, userMessage);

      const aiMsgId = Date.now() + 1;
      setCostsMessages(prev => [...prev, {
        id: aiMsgId,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString()
      }]);

      await costEstimationAPI.requestAiResponseStream(
        sessionUuid,
        (chunk) => {
          setCostsMessages(prev => {
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
        () => setCostsSending(false),
        (errorMsg) => {
          setError(errorMsg || 'Failed to get AI response');
          setCostsSending(false);
          setCostsMessages(prev => prev.filter(m => m.id !== aiMsgId || m.content));
        }
      );
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to send message');
      setCostsSending(false);
    }
  };

  const handleExtractCosts = async () => {
    if (!apiKeyManager.isSet()) {
      setPendingAction('extract_costs');
      setShowApiKeyPrompt(true);
      return;
    }

    setCostsExtracting(true);
    try {
      const response = await costEstimationAPI.extract(sessionUuid);
      setCostsFindings(response.data.findings);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to extract cost estimation');
    } finally {
      setCostsExtracting(false);
    }
  };

  // API Key handler
  const handleApiKeySet = () => {
    setShowApiKeyPrompt(false);
    if (pendingAction === 'start_potentials') {
      handleStartPotentials();
    } else if (pendingAction === 'extract_potentials') {
      handleExtractPotentials();
    } else if (pendingAction === 'start_costs') {
      handleStartCosts();
    } else if (pendingAction === 'extract_costs') {
      handleExtractCosts();
    }
    setPendingAction(null);
  };

  // Summarize company info for display
  const getCompanySummary = () => {
    if (!companyInfo.length) return null;
    const first = companyInfo[0];
    if (!first.content) return null;
    return first.content.substring(0, 200) + (first.content.length > 200 ? '...' : '');
  };

  // Message renderer component
  const MessageBubble = ({ msg }) => (
    <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-3 ${
          msg.role === 'user'
            ? 'bg-blue-600 text-white'
            : 'bg-gray-100 text-gray-900'
        }`}
      >
        <div className={`text-sm max-w-none ${
          msg.role === 'user' ? '' : 'prose prose-sm prose-gray'
        }`}>
          <ReactMarkdown
            components={{
              p: ({children}) => <p className="mb-2 last:mb-0">{children}</p>,
              ul: ({children}) => <ul className={`list-disc ml-4 mb-2 ${msg.role === 'user' ? 'text-white' : ''}`}>{children}</ul>,
              ol: ({children}) => <ol className={`list-decimal ml-4 mb-2 ${msg.role === 'user' ? 'text-white' : ''}`}>{children}</ol>,
              li: ({children}) => <li className="mb-1">{children}</li>,
              strong: ({children}) => <strong className="font-semibold">{children}</strong>,
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
  );

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">{t('common.loading')}</p>
      </div>
    );
  }

  const hasContext = companyInfo.length > 0 || topIdea || crispDmFindings;
  const currentMessages = activeTab === 'potentials' ? potentialsMessages : costsMessages;
  const currentSending = activeTab === 'potentials' ? potentialsSending : costsSending;

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

        {/* Tab Navigation */}
        <div className="mb-6 border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('potentials')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'potentials'
                  ? 'border-green-500 text-green-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <span className="flex items-center">
                <span className="bg-green-100 text-green-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">5a</span>
                {t('step5.tabs.potentials')}
                {potentialsStarted && (
                  <span className="ml-2 w-2 h-2 bg-green-400 rounded-full"></span>
                )}
              </span>
            </button>
            <button
              onClick={() => setActiveTab('costs')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'costs'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <span className="flex items-center">
                <span className="bg-blue-100 text-blue-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">5b</span>
                {t('step5.tabs.costs')}
                {costsStarted && (
                  <span className="ml-2 w-2 h-2 bg-blue-400 rounded-full"></span>
                )}
              </span>
            </button>
          </nav>
        </div>

        {/* Explanation Box - show when respective section hasn't started */}
        {activeTab === 'potentials' && !potentialsStarted && (
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

        {activeTab === 'costs' && !costsStarted && (
          <ExplanationBox
            title={t('step5.costsExplanation.title')}
            description={t('step5.costsExplanation.description')}
            bullets={[
              t('step5.costsExplanation.bullet1'),
              t('step5.costsExplanation.bullet2'),
              t('step5.costsExplanation.bullet3'),
              t('step5.costsExplanation.bullet4'),
            ]}
            tip={t('step5.costsExplanation.tip')}
            variant="blue"
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
                {companyInfo.length > 0 && (
                  <div className="bg-white rounded p-3">
                    <h4 className="text-sm font-semibold text-gray-700 mb-1">{t('step5.chat.companyProfile')}</h4>
                    <p className="text-xs text-gray-600">{getCompanySummary()}</p>
                  </div>
                )}
                {topIdea && (
                  <div className="bg-white rounded p-3">
                    <h4 className="text-sm font-semibold text-gray-700 mb-1">{t('step5.chat.focusIdea')}</h4>
                    <p className="text-xs text-gray-600">{topIdea.idea_content}</p>
                  </div>
                )}
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

        {/* Main content area */}
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
              {activeTab === 'potentials' ? (
                !potentialsStarted ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center">
                      <p className="text-gray-600 mb-4">{t('step5.chat.startMessage')}</p>
                      <button
                        onClick={handleStartPotentials}
                        disabled={potentialsSending}
                        className="bg-green-600 text-white py-3 px-8 rounded-md hover:bg-green-700 disabled:bg-gray-300 transition-colors font-medium"
                      >
                        {potentialsSending ? t('step5.chat.starting') : t('step5.chat.startButton')}
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    {potentialsMessages.map((msg) => (
                      <MessageBubble key={msg.id} msg={msg} />
                    ))}
                    {potentialsSending && potentialsMessages.length > 0 && potentialsMessages[potentialsMessages.length - 1].content === '' && (
                      <div className="flex justify-start">
                        <div className="bg-gray-100 rounded-lg px-4 py-3">
                          <p className="text-gray-500 text-sm animate-pulse">{t('step5.chat.thinking')}</p>
                        </div>
                      </div>
                    )}
                  </>
                )
              ) : (
                !costsStarted ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center">
                      <p className="text-gray-600 mb-4">{t('step5.costs.startMessage')}</p>
                      <button
                        onClick={handleStartCosts}
                        disabled={costsSending}
                        className="bg-blue-600 text-white py-3 px-8 rounded-md hover:bg-blue-700 disabled:bg-gray-300 transition-colors font-medium"
                      >
                        {costsSending ? t('step5.costs.starting') : t('step5.costs.startButton')}
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    {costsMessages.map((msg) => (
                      <MessageBubble key={msg.id} msg={msg} />
                    ))}
                    {costsSending && costsMessages.length > 0 && costsMessages[costsMessages.length - 1].content === '' && (
                      <div className="flex justify-start">
                        <div className="bg-gray-100 rounded-lg px-4 py-3">
                          <p className="text-gray-500 text-sm animate-pulse">{t('step5.costs.thinking')}</p>
                        </div>
                      </div>
                    )}
                  </>
                )
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input area */}
            {((activeTab === 'potentials' && potentialsStarted) || (activeTab === 'costs' && costsStarted)) && (
              <div className="border-t p-4">
                <form onSubmit={activeTab === 'potentials' ? handleSendPotentialsMessage : handleSendCostsMessage} className="flex gap-2">
                  <input
                    type="text"
                    value={activeTab === 'potentials' ? potentialsInput : costsInput}
                    onChange={(e) => activeTab === 'potentials' ? setPotentialsInput(e.target.value) : setCostsInput(e.target.value)}
                    placeholder={t('step5.chat.messagePlaceholder')}
                    disabled={currentSending}
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    type="submit"
                    disabled={currentSending || !(activeTab === 'potentials' ? potentialsInput.trim() : costsInput.trim())}
                    className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-300 transition-colors"
                  >
                    {t('common.send')}
                  </button>
                </form>
                <div className="mt-2 flex justify-end">
                  <button
                    onClick={activeTab === 'potentials' ? handleExtractPotentials : handleExtractCosts}
                    disabled={(activeTab === 'potentials' ? potentialsExtracting : costsExtracting) || currentMessages.length < 4}
                    className="text-sm text-blue-600 hover:text-blue-800 disabled:text-gray-400"
                  >
                    {activeTab === 'potentials'
                      ? (potentialsExtracting ? t('step5.chat.extracting') : t('step5.chat.extractFindings'))
                      : (costsExtracting ? t('step5.costs.extracting') : t('step5.costs.extractFindings'))
                    }
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Findings sidebar - 1/3 width */}
          <div className="space-y-4">
            {activeTab === 'potentials' ? (
              <>
                {/* Potentials Findings Header */}
                <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                  <h3 className="font-semibold text-green-800 text-sm">{t('step5.findings.title')}</h3>
                  <p className="text-xs text-green-600 mt-1">{t('step5.findings.subtitle')}</p>
                </div>

                {/* Classification */}
                <div className="bg-white rounded-lg shadow p-4">
                  <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
                    <span className="bg-green-100 text-green-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">1</span>
                    {t('step5.findings.classification')}
                  </h3>
                  {potentialsFindings?.classification ? (
                    <div className="text-sm text-gray-700 prose prose-sm max-w-none">
                      <ReactMarkdown>{potentialsFindings.classification}</ReactMarkdown>
                    </div>
                  ) : (
                    <p className="text-sm text-gray-400 italic">{t('step5.findings.classificationPlaceholder')}</p>
                  )}
                </div>

                {/* Calculation */}
                <div className="bg-white rounded-lg shadow p-4">
                  <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
                    <span className="bg-green-100 text-green-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">2</span>
                    {t('step5.findings.calculation')}
                  </h3>
                  {potentialsFindings?.calculation ? (
                    <div className="text-sm text-gray-700 prose prose-sm max-w-none">
                      <ReactMarkdown>{potentialsFindings.calculation}</ReactMarkdown>
                    </div>
                  ) : (
                    <p className="text-sm text-gray-400 italic">{t('step5.findings.calculationPlaceholder')}</p>
                  )}
                </div>

                {/* Validation Questions */}
                <div className="bg-white rounded-lg shadow p-4">
                  <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
                    <span className="bg-green-100 text-green-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">3</span>
                    {t('step5.findings.validationQuestions')}
                  </h3>
                  {potentialsFindings?.validation_questions ? (
                    <div className="text-sm text-gray-700 prose prose-sm max-w-none">
                      <ReactMarkdown>{potentialsFindings.validation_questions}</ReactMarkdown>
                    </div>
                  ) : (
                    <p className="text-sm text-gray-400 italic">{t('step5.findings.validationPlaceholder')}</p>
                  )}
                </div>

                {/* Management Pitch */}
                <div className="bg-white rounded-lg shadow p-4">
                  <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
                    <span className="bg-green-100 text-green-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">4</span>
                    {t('step5.findings.managementPitch')}
                  </h3>
                  {potentialsFindings?.management_pitch ? (
                    <div className="text-sm text-gray-700 prose prose-sm max-w-none font-medium">
                      <ReactMarkdown>{potentialsFindings.management_pitch}</ReactMarkdown>
                    </div>
                  ) : (
                    <p className="text-sm text-gray-400 italic">{t('step5.findings.managementPitchPlaceholder')}</p>
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
              </>
            ) : (
              <>
                {/* Costs Findings Header */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                  <h3 className="font-semibold text-blue-800 text-sm">{t('step5.costsFindings.title')}</h3>
                  <p className="text-xs text-blue-600 mt-1">{t('step5.costsFindings.subtitle')}</p>
                </div>

                {/* Complexity */}
                <div className="bg-white rounded-lg shadow p-4">
                  <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
                    <span className="bg-blue-100 text-blue-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">1</span>
                    {t('step5.costsFindings.complexity')}
                  </h3>
                  {costsFindings?.complexity ? (
                    <div className="text-sm text-gray-700 prose prose-sm max-w-none">
                      <ReactMarkdown>{costsFindings.complexity}</ReactMarkdown>
                    </div>
                  ) : (
                    <p className="text-sm text-gray-400 italic">{t('step5.costsFindings.complexityPlaceholder')}</p>
                  )}
                </div>

                {/* Initial Investment */}
                <div className="bg-white rounded-lg shadow p-4">
                  <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
                    <span className="bg-blue-100 text-blue-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">2</span>
                    {t('step5.costsFindings.initialInvestment')}
                  </h3>
                  {costsFindings?.initial_investment ? (
                    <div className="text-sm text-gray-700 prose prose-sm max-w-none">
                      <ReactMarkdown>{costsFindings.initial_investment}</ReactMarkdown>
                    </div>
                  ) : (
                    <p className="text-sm text-gray-400 italic">{t('step5.costsFindings.initialPlaceholder')}</p>
                  )}
                </div>

                {/* Recurring Costs */}
                <div className="bg-white rounded-lg shadow p-4">
                  <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
                    <span className="bg-blue-100 text-blue-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">3</span>
                    {t('step5.costsFindings.recurring')}
                  </h3>
                  {costsFindings?.recurring_costs ? (
                    <div className="text-sm text-gray-700 prose prose-sm max-w-none">
                      <ReactMarkdown>{costsFindings.recurring_costs}</ReactMarkdown>
                    </div>
                  ) : (
                    <p className="text-sm text-gray-400 italic">{t('step5.costsFindings.recurringPlaceholder')}</p>
                  )}
                </div>

                {/* TCO */}
                <div className="bg-white rounded-lg shadow p-4">
                  <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
                    <span className="bg-blue-100 text-blue-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">4</span>
                    {t('step5.costsFindings.tco')}
                  </h3>
                  {costsFindings?.tco ? (
                    <div className="text-sm text-gray-700 prose prose-sm max-w-none font-medium">
                      <ReactMarkdown>{costsFindings.tco}</ReactMarkdown>
                    </div>
                  ) : (
                    <p className="text-sm text-gray-400 italic">{t('step5.costsFindings.tcoPlaceholder')}</p>
                  )}
                </div>

                {/* ROI Analysis */}
                <div className="bg-white rounded-lg shadow p-4">
                  <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
                    <span className="bg-blue-100 text-blue-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">5</span>
                    {t('step5.costsFindings.roi')}
                  </h3>
                  {costsFindings?.roi_analysis ? (
                    <div className="text-sm text-gray-700 prose prose-sm max-w-none">
                      <ReactMarkdown>{costsFindings.roi_analysis}</ReactMarkdown>
                    </div>
                  ) : (
                    <p className="text-sm text-gray-400 italic">{t('step5.costsFindings.roiPlaceholder')}</p>
                  )}
                </div>

                {/* Cost Framework Reference */}
                <div className="bg-gray-50 rounded-lg p-3">
                  <h4 className="text-xs font-semibold text-gray-700 mb-2">{t('step5.costFramework.title')}</h4>
                  <div className="text-xs text-gray-600 space-y-1">
                    <p><span className="font-medium">{t('step5.costFramework.quickWin')}:</span> 2-4 {t('step5.costFramework.weeks')}, 5k-15k</p>
                    <p><span className="font-medium">{t('step5.costFramework.standard')}:</span> 1-3 {t('step5.costFramework.months')}, 15k-50k</p>
                    <p><span className="font-medium">{t('step5.costFramework.complex')}:</span> 3-6 {t('step5.costFramework.months')}, 50k-150k</p>
                    <p><span className="font-medium">{t('step5.costFramework.enterprise')}:</span> 6+ {t('step5.costFramework.months')}, 150k+</p>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Navigation */}
        <div className="mt-6 flex justify-start">
          <button
            onClick={() => navigate(`/session/${sessionUuid}/step4`)}
            className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
          >
            {t('step5.backStep4')}
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
