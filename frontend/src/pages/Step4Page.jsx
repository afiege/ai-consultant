import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import { sixThreeFiveAPI, prioritizationAPI, consultationAPI } from '../services/api';
import { PageHeader, ExplanationBox } from '../components/common';

const Step4Page = () => {
  const { t } = useTranslation();
  const { sessionUuid } = useParams();
  const navigate = useNavigate();
  const messagesEndRef = useRef(null);

  const [ideas, setIdeas] = useState([]);
  const [topIdea, setTopIdea] = useState(null);
  const [loading, setLoading] = useState(true);
  const [manualIdeas, setManualIdeas] = useState(['', '', '']);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Chat state
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);
  const [consultationStarted, setConsultationStarted] = useState(false);
  const [findings, setFindings] = useState(null);
  const [summarizing, setSummarizing] = useState(false);

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
      // Load all ideas
      const ideasResponse = await sixThreeFiveAPI.getIdeas(sessionUuid);
      setIdeas(ideasResponse.data);

      // Try to get prioritization results
      try {
        const resultsResponse = await prioritizationAPI.getResults(sessionUuid);
        if (resultsResponse.data.top_ideas?.length > 0) {
          setTopIdea(resultsResponse.data.top_ideas[0]);
        }
      } catch (e) {
        // No prioritization results
      }

      // Try to load existing consultation messages
      try {
        const messagesResponse = await consultationAPI.getMessages(sessionUuid);
        if (messagesResponse.data.length > 0) {
          setMessages(messagesResponse.data);
          setConsultationStarted(true);
        }
      } catch (e) {
        // No existing messages
      }

      // Try to load findings
      try {
        const findingsResponse = await consultationAPI.getFindings(sessionUuid);
        // Check for CRISP-DM fields or legacy fields
        if (findingsResponse.data.business_objectives || findingsResponse.data.situation_assessment ||
            findingsResponse.data.ai_goals || findingsResponse.data.project_plan ||
            findingsResponse.data.project || findingsResponse.data.risks ||
            findingsResponse.data.end_user || findingsResponse.data.business_case) {
          setFindings(findingsResponse.data);
        }
      } catch (e) {
        // No findings yet
      }
    } catch (err) {
      console.error('Failed to load data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleManualIdeaChange = (index, value) => {
    const newIdeas = [...manualIdeas];
    newIdeas[index] = value;
    setManualIdeas(newIdeas);
  };

  const handleSubmitManualIdeas = async () => {
    const filledIdeas = manualIdeas.filter(idea => idea.trim() !== '');

    if (filledIdeas.length === 0) {
      setError('Please enter at least one idea');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await sixThreeFiveAPI.submitManualIdeas(sessionUuid, filledIdeas);
      const response = await sixThreeFiveAPI.getIdeas(sessionUuid);
      setIdeas(response.data);
      if (response.data.length > 0) {
        setTopIdea({
          idea_id: response.data[0].id,
          idea_content: response.data[0].content,
          participant_name: response.data[0].participant_name,
          total_points: 0
        });
      }
      setManualIdeas(['', '', '']);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit ideas');
    } finally {
      setSubmitting(false);
    }
  };

  const handleStartConsultation = async () => {
    setSendingMessage(true);
    setConsultationStarted(true);

    // Add placeholder message for streaming
    const placeholderId = Date.now();
    setMessages([{
      id: placeholderId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString()
    }]);

    try {
      await consultationAPI.startStream(
        sessionUuid,
        // onChunk - update the message content as chunks arrive
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
        // onDone
        () => {
          setSendingMessage(false);
        },
        // onError
        (errorMsg) => {
          setError(errorMsg || 'Failed to start consultation');
          setSendingMessage(false);
        }
      );
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start consultation');
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
      // Save the user message
      await consultationAPI.saveMessage(sessionUuid, userMessage);

      // Automatically request AI response
      const aiMsgId = Date.now() + 1;
      setMessages(prev => [...prev, {
        id: aiMsgId,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString()
      }]);

      await consultationAPI.requestAiResponseStream(
        sessionUuid,
        // onChunk - update the AI message content as chunks arrive
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
        // onDone
        () => {
          setSendingMessage(false);
        },
        // onError
        (errorMsg) => {
          setError(errorMsg || 'Failed to get AI response');
          setSendingMessage(false);
          // Remove empty placeholder on error
          setMessages(prev => prev.filter(m => m.id !== aiMsgId || m.content));
        }
      );
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to send message');
      setSendingMessage(false);
    }
  };

  const handleRequestAiResponse = async () => {
    if (sendingMessage) return;
    setSendingMessage(true);

    // Add placeholder for AI response
    const aiMsgId = Date.now();
    setMessages(prev => [...prev, {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString()
    }]);

    try {
      await consultationAPI.requestAiResponseStream(
        sessionUuid,
        // onChunk - update the AI message content as chunks arrive
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
        // onDone
        () => {
          setSendingMessage(false);
        },
        // onError
        (errorMsg) => {
          setError(errorMsg || 'Failed to get AI response');
          setSendingMessage(false);
          // Remove empty placeholder on error
          setMessages(prev => prev.filter(m => m.id !== aiMsgId || m.content));
        }
      );
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to get AI response');
      setSendingMessage(false);
    }
  };

  const handleSummarize = async () => {
    setSummarizing(true);
    try {
      const response = await consultationAPI.summarize(sessionUuid);
      setFindings(response.data.findings);

      // Add summary to chat
      if (response.data.summary) {
        setMessages(prev => [...prev, {
          id: Date.now(),
          role: 'assistant',
          content: response.data.summary,
          created_at: new Date().toISOString()
        }]);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to generate summary');
    } finally {
      setSummarizing(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">{t('common.loading')}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <PageHeader
        title={t('step4.title')}
        subtitle={t('step4.subtitle')}
        sessionUuid={sessionUuid}
      />

      <div className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 w-full">
        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* Explanation - show when consultation hasn't started */}
        {!consultationStarted && (
          <ExplanationBox
            title={t('step4.explanation.title')}
            description={t('step4.explanation.description')}
            bullets={[
              t('step4.explanation.bullet1'),
              t('step4.explanation.bullet2'),
              t('step4.explanation.bullet3'),
              t('step4.explanation.bullet4'),
            ]}
            tip={t('step4.explanation.tip')}
            defaultOpen={true}
          />
        )}

        {/* Manual idea entry when no ideas exist */}
        {ideas.length === 0 && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-6">
            <h2 className="text-lg font-semibold text-blue-800 mb-3">{t('step4.manualEntry.title')}</h2>
            <p className="text-blue-700 mb-4">
              {t('step4.manualEntry.message')}
            </p>
            <div className="space-y-3">
              {manualIdeas.map((idea, index) => (
                <div key={index}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('step4.manualEntry.ideaLabel', { number: index + 1 })} {index === 0 && <span className="text-red-500">*</span>}
                  </label>
                  <textarea
                    value={idea}
                    onChange={(e) => handleManualIdeaChange(index, e.target.value)}
                    placeholder={t('step4.manualEntry.ideaPlaceholder')}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    rows="2"
                  />
                </div>
              ))}
            </div>
            <button
              onClick={handleSubmitManualIdeas}
              disabled={submitting}
              className="mt-4 w-full bg-blue-600 text-white py-2 px-6 rounded-md hover:bg-blue-700 disabled:bg-gray-300 transition-colors font-medium"
            >
              {submitting ? t('common.submitting') : t('step4.manualEntry.submitIdeas')}
            </button>
          </div>
        )}

        {/* Main consultation area */}
        {ideas.length > 0 && (
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
                {!consultationStarted ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center">
                      <p className="text-gray-600 mb-4">
                        {t('step4.chat.startMessage')}
                      </p>
                      <button
                        onClick={handleStartConsultation}
                        disabled={sendingMessage}
                        className="bg-blue-600 text-white py-3 px-8 rounded-md hover:bg-blue-700 disabled:bg-gray-300 transition-colors font-medium"
                      >
                        {sendingMessage ? t('step4.chat.starting') : t('step4.chat.startButton')}
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
                                // Style overrides for chat context
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
                          <p className="text-gray-500 text-sm animate-pulse">{t('step4.chat.thinking')}</p>
                        </div>
                      </div>
                    )}
                    <div ref={messagesEndRef} />
                  </>
                )}
              </div>

              {/* Input area */}
              {consultationStarted && (
                <div className="border-t p-4">
                  <form onSubmit={handleSendMessage} className="flex gap-2">
                    <input
                      type="text"
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      placeholder={t('step4.chat.messagePlaceholder')}
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
                      onClick={handleSummarize}
                      disabled={summarizing || messages.length < 4}
                      className="text-sm text-blue-600 hover:text-blue-800 disabled:text-gray-400"
                    >
                      {summarizing ? t('step4.chat.generatingSummary') : t('step4.chat.generateSummary')}
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Findings sidebar - 1/3 width (CRISP-DM Business Understanding) */}
            <div className="space-y-4">
              {/* CRISP-DM Header */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                <h3 className="font-semibold text-blue-800 text-sm">{t('step4.findings.crispDmTitle')}</h3>
                <p className="text-xs text-blue-600 mt-1">{t('step4.findings.crispDmSubtitle')}</p>
              </div>

              {/* 1. Business Objectives */}
              <div className="bg-white rounded-lg shadow p-4">
                <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
                  <span className="bg-blue-100 text-blue-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">1</span>
                  {t('step4.findings.businessObjectives')}
                </h3>
                {findings?.business_objectives ? (
                  <div className="text-sm text-gray-700 prose prose-sm max-w-none">
                    <ReactMarkdown>{findings.business_objectives}</ReactMarkdown>
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 italic">
                    {t('step4.findings.businessObjectivesPlaceholder')}
                  </p>
                )}
              </div>

              {/* 2. Situation Assessment */}
              <div className="bg-white rounded-lg shadow p-4">
                <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
                  <span className="bg-blue-100 text-blue-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">2</span>
                  {t('step4.findings.situationAssessment')}
                </h3>
                {findings?.situation_assessment ? (
                  <div className="text-sm text-gray-700 prose prose-sm max-w-none">
                    <ReactMarkdown>{findings.situation_assessment}</ReactMarkdown>
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 italic">
                    {t('step4.findings.situationPlaceholder')}
                  </p>
                )}
              </div>

              {/* 3. AI/Data Mining Goals */}
              <div className="bg-white rounded-lg shadow p-4">
                <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
                  <span className="bg-blue-100 text-blue-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">3</span>
                  {t('step4.findings.aiGoals')}
                </h3>
                {findings?.ai_goals ? (
                  <div className="text-sm text-gray-700 prose prose-sm max-w-none">
                    <ReactMarkdown>{findings.ai_goals}</ReactMarkdown>
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 italic">
                    {t('step4.findings.aiGoalsPlaceholder')}
                  </p>
                )}
              </div>

              {/* 4. Project Plan */}
              <div className="bg-white rounded-lg shadow p-4">
                <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
                  <span className="bg-blue-100 text-blue-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">4</span>
                  {t('step4.findings.projectPlan')}
                </h3>
                {findings?.project_plan ? (
                  <div className="text-sm text-gray-700 prose prose-sm max-w-none">
                    <ReactMarkdown>{findings.project_plan}</ReactMarkdown>
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 italic">
                    {t('step4.findings.projectPlanPlaceholder')}
                  </p>
                )}
              </div>

              {/* Ideas summary */}
              <div className="bg-white rounded-lg shadow p-4">
                <h3 className="font-semibold text-gray-900 mb-2">{t('step4.findings.ideas')} ({ideas.length})</h3>
                <div className="space-y-1 max-h-40 overflow-y-auto">
                  {ideas.slice(0, 5).map((idea) => (
                    <p key={idea.id} className="text-xs text-gray-600 truncate">
                      - {idea.content}
                    </p>
                  ))}
                  {ideas.length > 5 && (
                    <p className="text-xs text-gray-400">{t('step4.findings.moreIdeas', { count: ideas.length - 5 })}</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="mt-6 flex justify-between">
          <button
            onClick={() => navigate(`/session/${sessionUuid}/step3`)}
            className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
          >
            {t('step4.backStep3')}
          </button>
          <button
            onClick={() => navigate(`/session/${sessionUuid}/step5`)}
            className="px-6 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
          >
            {t('step4.continueStep5')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Step4Page;
