import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { sixThreeFiveAPI, prioritizationAPI, consultationAPI, apiKeyManager } from '../services/api';
import { PageHeader, ExplanationBox, TypingIndicator } from '../components/common';
import { SkeletonChat } from '../components/common/Skeleton';
import ApiKeyPrompt from '../components/common/ApiKeyPrompt';
import TestModePanel from '../components/common/TestModePanel';
import {
  ChatMessage,
  ChatInput,
  CollaborativeModePanel,
  CrispDmFindingsSidebar,
  ManualIdeasEntry,
} from '../components/consultation';
import { useTestMode } from '../hooks/useTestMode';
import { extractApiError } from '../utils';

const Step4Page = () => {
  const { t, i18n } = useTranslation();
  const { sessionUuid } = useParams();
  const messagesEndRef = useRef(null);

  const [ideas, setIdeas] = useState([]);
  const [topIdea, setTopIdea] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Chat state
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);
  const [consultationStarted, setConsultationStarted] = useState(false);
  const [findings, setFindings] = useState(null);
  const [summarizing, setSummarizing] = useState(false);
  const [showApiKeyPrompt, setShowApiKeyPrompt] = useState(false);
  const [pendingAction, setPendingAction] = useState(null);

  // Collaborative mode state
  const [collaborativeMode, setCollaborativeMode] = useState(false);
  const [participants, setParticipants] = useState([]);
  const [participantUuid, setParticipantUuid] = useState(null);
  const [isOwner, setIsOwner] = useState(false);
  const [lastMessageId, setLastMessageId] = useState(null);

  // Test mode state
  const testModeEnabled = useTestMode();

  // Load participant UUID from localStorage
  useEffect(() => {
    const stored = localStorage.getItem(`participant_${sessionUuid}`);
    if (stored) {
      setParticipantUuid(stored);
    }
  }, [sessionUuid]);

  useEffect(() => {
    loadData();
  }, [sessionUuid]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Poll for collaborative updates
  useEffect(() => {
    if (collaborativeMode && consultationStarted) {
      const pollInterval = setInterval(async () => {
        try {
          const msgResponse = await consultationAPI.getCollaborativeMessages(sessionUuid, lastMessageId);
          if (msgResponse.data.length > 0) {
            setMessages(prev => {
              const existingIds = new Set(prev.map(m => m.id));
              const newMsgs = msgResponse.data.filter(m => !existingIds.has(m.id));
              if (newMsgs.length > 0) {
                setLastMessageId(msgResponse.data[msgResponse.data.length - 1].id);
                return [...prev, ...newMsgs];
              }
              return prev;
            });
          }

          const statusResponse = await consultationAPI.getCollaborativeStatus(sessionUuid);
          setParticipants(statusResponse.data.participants || []);
        } catch (err) {
          console.error('Error polling collaborative updates:', err);
        }
      }, 3000);

      return () => clearInterval(pollInterval);
    }
  }, [collaborativeMode, consultationStarted, sessionUuid, lastMessageId]);

  // Incremental findings extraction
  const lastExtractionCount = useRef(0);
  useEffect(() => {
    const messageCount = messages.filter(m => m.role !== 'system').length;
    if (messageCount >= 4 && messageCount - lastExtractionCount.current >= 4 && apiKeyManager.isSet()) {
      lastExtractionCount.current = messageCount;
      consultationAPI.extractIncremental(sessionUuid)
        .then(response => {
          if (response.data.updated && response.data.findings) {
            setFindings(response.data.findings);
          }
        })
        .catch(err => console.error('Incremental extraction failed:', err));
    }
  }, [messages, sessionUuid]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadData = async () => {
    try {
      const ideasResponse = await sixThreeFiveAPI.getIdeas(sessionUuid);
      setIdeas(ideasResponse.data);

      try {
        const resultsResponse = await prioritizationAPI.getResults(sessionUuid);
        if (resultsResponse.data.top_ideas?.length > 0) {
          setTopIdea(resultsResponse.data.top_ideas[0]);
        }
      } catch (e) {}

      try {
        const collabResponse = await consultationAPI.getCollaborativeStatus(sessionUuid);
        setCollaborativeMode(collabResponse.data.collaborative_mode);
        setParticipants(collabResponse.data.participants || []);
        setConsultationStarted(collabResponse.data.consultation_started);

        const storedUuid = localStorage.getItem(`participant_${sessionUuid}`);
        if (storedUuid && collabResponse.data.owner_participant_uuid === storedUuid) {
          setIsOwner(true);
        }
      } catch (e) {}

      try {
        const messagesResponse = collaborativeMode
          ? await consultationAPI.getCollaborativeMessages(sessionUuid)
          : await consultationAPI.getMessages(sessionUuid);
        if (messagesResponse.data.length > 0) {
          setMessages(messagesResponse.data);
          setConsultationStarted(true);
          setLastMessageId(messagesResponse.data[messagesResponse.data.length - 1].id);
        }
      } catch (e) {}

      try {
        const findingsResponse = await consultationAPI.getFindings(sessionUuid);
        if (findingsResponse.data.business_objectives || findingsResponse.data.situation_assessment ||
            findingsResponse.data.ai_goals || findingsResponse.data.project_plan ||
            findingsResponse.data.project || findingsResponse.data.risks ||
            findingsResponse.data.end_user || findingsResponse.data.business_case) {
          setFindings(findingsResponse.data);
        }
      } catch (e) {}
    } catch (err) {
      console.error('Failed to load data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitManualIdeas = async (filledIdeas) => {
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
      return true;
    } catch (err) {
      setError(extractApiError(err, i18n.language));
      return false;
    } finally {
      setSubmitting(false);
    }
  };

  const handleStartConsultation = async () => {
    if (!apiKeyManager.isSet()) {
      setPendingAction('start');
      setShowApiKeyPrompt(true);
      return;
    }

    setSendingMessage(true);
    setConsultationStarted(true);

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
        () => setSendingMessage(false),
        (errorMsg) => {
          setError(errorMsg || 'Failed to start consultation');
          setSendingMessage(false);
        }
      );
    } catch (err) {
      setError(extractApiError(err, i18n.language));
      setSendingMessage(false);
    }
  };

  const handleResetConsultation = async () => {
    if (!window.confirm(t('step4.chat.resetConfirm') || 'Are you sure you want to start over? All messages will be deleted.')) {
      return;
    }

    setError(null);
    try {
      await consultationAPI.reset(sessionUuid);
      setMessages([]);
      setConsultationStarted(false);
      setFindings(null);
      await loadData();
    } catch (err) {
      setError(extractApiError(err, i18n.language));
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || sendingMessage) return;

    const userMessage = inputMessage.trim();
    setInputMessage('');
    setSendingMessage(true);

    const userMsgId = Date.now();
    setMessages(prev => [...prev, {
      id: userMsgId,
      role: 'user',
      content: userMessage,
      created_at: new Date().toISOString()
    }]);

    try {
      await consultationAPI.saveMessage(sessionUuid, userMessage);

      const aiMsgId = Date.now() + 1;
      setMessages(prev => [...prev, {
        id: aiMsgId,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString()
      }]);

      await consultationAPI.requestAiResponseStream(
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
        () => setSendingMessage(false),
        (errorMsg) => {
          setError(errorMsg || 'Failed to get AI response');
          setSendingMessage(false);
          setMessages(prev => prev.filter(m => m.id !== aiMsgId || m.content));
        }
      );
    } catch (err) {
      setError(extractApiError(err, i18n.language));
      setSendingMessage(false);
    }
  };

  const handleSendCollaborativeMessage = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || sendingMessage) return;

    const userMessage = inputMessage.trim();
    setInputMessage('');
    setSendingMessage(true);

    try {
      const response = await consultationAPI.saveCollaborativeMessage(
        sessionUuid,
        userMessage,
        participantUuid
      );

      setMessages(prev => [...prev, {
        id: response.data.message_id,
        role: 'user',
        content: response.data.content,
        created_at: new Date().toISOString(),
        participant_name: response.data.participant_name
      }]);
      setLastMessageId(response.data.message_id);
      setSendingMessage(false);
    } catch (err) {
      setError(extractApiError(err, i18n.language));
      setSendingMessage(false);
    }
  };

  const handleRequestAiResponse = async () => {
    if (sendingMessage) return;
    setSendingMessage(true);

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
          if (collaborativeMode) loadData();
        },
        (errorMsg) => {
          setError(errorMsg || 'Failed to get AI response');
          setSendingMessage(false);
          setMessages(prev => prev.filter(m => m.id !== aiMsgId || m.content));
        }
      );
    } catch (err) {
      setError(extractApiError(err, i18n.language));
      setSendingMessage(false);
    }
  };

  const handleSummarize = async () => {
    if (!apiKeyManager.isSet()) {
      setPendingAction('summarize');
      setShowApiKeyPrompt(true);
      return;
    }

    setSummarizing(true);
    try {
      const response = await consultationAPI.summarize(sessionUuid);
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
      setError(extractApiError(err, i18n.language));
    } finally {
      setSummarizing(false);
    }
  };

  const handleApiKeySet = () => {
    setShowApiKeyPrompt(false);
    if (pendingAction === 'start') {
      handleStartConsultation();
    } else if (pendingAction === 'summarize') {
      handleSummarize();
    }
    setPendingAction(null);
  };

  const handleTestModeResponse = async (generatedResponse) => {
    if (!generatedResponse.trim() || sendingMessage) return;

    const userMessage = generatedResponse.trim();
    setSendingMessage(true);

    const userMsgId = Date.now();
    setMessages(prev => [...prev, {
      id: userMsgId,
      role: 'user',
      content: userMessage,
      created_at: new Date().toISOString()
    }]);

    try {
      await consultationAPI.saveMessage(sessionUuid, userMessage);

      const aiMsgId = Date.now() + 1;
      setMessages(prev => [...prev, {
        id: aiMsgId,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString()
      }]);

      await consultationAPI.requestAiResponseStream(
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
        () => setSendingMessage(false),
        (errorMsg) => {
          setError(errorMsg || 'Failed to get AI response');
          setSendingMessage(false);
          setMessages(prev => prev.filter(m => m.id !== aiMsgId || m.content));
        }
      );
    } catch (err) {
      setError(extractApiError(err, i18n.language));
      setSendingMessage(false);
    }
  };

  const handleToggleCollaborativeMode = async () => {
    try {
      const newMode = !collaborativeMode;
      await consultationAPI.setCollaborativeMode(sessionUuid, newMode);
      setCollaborativeMode(newMode);
    } catch (err) {
      setError(extractApiError(err, i18n.language));
    }
  };

  // Filter messages for display
  const displayMessages = messages.filter(msg =>
    msg.role !== 'system' &&
    !msg.content?.startsWith('[SESSION CONTEXT]') &&
    !msg.content?.startsWith('[IMPORTANT UPDATE') &&
    !msg.content?.startsWith('[WICHTIGE AKTUALISIERUNG')
  );

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <SkeletonChat messageCount={4} />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
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

        {(isOwner || collaborativeMode) && ideas.length > 0 && (
          <CollaborativeModePanel
            sessionUuid={sessionUuid}
            collaborativeMode={collaborativeMode}
            isOwner={isOwner}
            participants={participants}
            consultationStarted={consultationStarted}
            onToggleMode={handleToggleCollaborativeMode}
          />
        )}

        {ideas.length === 0 && (
          <ManualIdeasEntry onSubmit={handleSubmitManualIdeas} submitting={submitting} />
        )}

        {ideas.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Chat area */}
            <div className="lg:col-span-2 flex flex-col bg-white rounded-lg shadow min-h-[400px] max-h-[80vh]">
              {topIdea && (
                <div className="bg-yellow-50 border-b border-yellow-200 px-4 py-3 flex justify-between items-center">
                  <p className="text-sm font-medium text-yellow-800">
                    {t('step4.chat.focus')} {topIdea.idea_content}
                  </p>
                  {consultationStarted && (
                    <button
                      onClick={handleResetConsultation}
                      className="text-xs text-gray-500 hover:text-red-600 hover:bg-red-50 px-2 py-1 rounded transition-colors"
                      title={t('step4.chat.resetTitle') || 'Start over'}
                    >
                      {t('step4.chat.resetButton') || 'Start Over'}
                    </button>
                  )}
                </div>
              )}

              {/* Messages area */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {!consultationStarted ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center">
                      <p className="text-gray-600 mb-4">{t('step4.chat.startMessage')}</p>
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
                    {displayMessages.map((msg) => (
                      <ChatMessage
                        key={msg.id}
                        message={msg}
                        collaborativeMode={collaborativeMode}
                      />
                    ))}
                    {sendingMessage && messages.length > 0 && messages[messages.length - 1].content === '' && (
                      <div className="flex justify-start" role="status" aria-label={t('step4.chat.thinking')}>
                        <TypingIndicator />
                      </div>
                    )}
                    <div ref={messagesEndRef} />
                  </>
                )}
              </div>

              {consultationStarted && (
                <ChatInput
                  value={inputMessage}
                  onChange={setInputMessage}
                  onSubmit={collaborativeMode ? handleSendCollaborativeMessage : handleSendMessage}
                  onSummarize={handleSummarize}
                  onRequestAiResponse={collaborativeMode ? handleRequestAiResponse : undefined}
                  disabled={sendingMessage}
                  summarizing={summarizing}
                  collaborativeMode={collaborativeMode}
                  messageCount={messages.length}
                />
              )}
            </div>

            {/* Findings sidebar */}
            <CrispDmFindingsSidebar findings={findings} ideas={ideas} />
          </div>
        )}
      </div>

      <ApiKeyPrompt
        isOpen={showApiKeyPrompt}
        onClose={() => setShowApiKeyPrompt(false)}
        onApiKeySet={handleApiKeySet}
      />

      {testModeEnabled && (
        <TestModePanel
          sessionUuid={sessionUuid}
          messageType="consultation"
          onResponseGenerated={handleTestModeResponse}
          disabled={sendingMessage}
          consultationStarted={consultationStarted}
        />
      )}
    </div>
  );
};

export default Step4Page;
