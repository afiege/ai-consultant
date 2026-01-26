import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import { QRCodeSVG } from 'qrcode.react';
import { sixThreeFiveAPI, prioritizationAPI, consultationAPI, apiKeyManager } from '../services/api';
import { PageHeader, ExplanationBox } from '../components/common';
import ApiKeyPrompt from '../components/common/ApiKeyPrompt';

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
  const [showApiKeyPrompt, setShowApiKeyPrompt] = useState(false);
  const [pendingAction, setPendingAction] = useState(null); // 'start' or 'summarize'

  // Collaborative mode state
  const [collaborativeMode, setCollaborativeMode] = useState(false);
  const [participants, setParticipants] = useState([]);
  const [participantUuid, setParticipantUuid] = useState(null);
  const [isOwner, setIsOwner] = useState(false);
  const [lastMessageId, setLastMessageId] = useState(null);
  const [showSharePanel, setShowSharePanel] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);

  // Topic tracking state
  const [topicsCovered, setTopicsCovered] = useState({
    businessObjectives: false,
    situationAssessment: false,
    aiGoals: false,
    projectPlan: false
  });
  const [skippedTopics, setSkippedTopics] = useState({});

  // Load participant UUID from localStorage (reuse from 6-3-5)
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

  // Poll for collaborative status and new messages
  useEffect(() => {
    if (collaborativeMode && consultationStarted) {
      const pollInterval = setInterval(async () => {
        try {
          // Poll for new messages
          const msgResponse = await consultationAPI.getCollaborativeMessages(sessionUuid, lastMessageId);
          if (msgResponse.data.length > 0) {
            setMessages(prev => {
              // Filter out messages we already have
              const existingIds = new Set(prev.map(m => m.id));
              const newMsgs = msgResponse.data.filter(m => !existingIds.has(m.id));
              if (newMsgs.length > 0) {
                setLastMessageId(msgResponse.data[msgResponse.data.length - 1].id);
                return [...prev, ...newMsgs];
              }
              return prev;
            });
          }

          // Also poll for collaborative status (participants list)
          const statusResponse = await consultationAPI.getCollaborativeStatus(sessionUuid);
          setParticipants(statusResponse.data.participants || []);
        } catch (err) {
          console.error('Error polling collaborative updates:', err);
        }
      }, 3000); // Poll every 3 seconds

      return () => clearInterval(pollInterval);
    }
  }, [collaborativeMode, consultationStarted, sessionUuid, lastMessageId]);

  // Analyze messages to detect which topics have been covered
  useEffect(() => {
    if (messages.length < 2) return;

    const allText = messages.map(m => m.content.toLowerCase()).join(' ');

    // Keywords for each topic
    const topicKeywords = {
      businessObjectives: ['goal', 'objective', 'problem', 'opportunity', 'success', 'kpi', 'metric', 'achieve', 'ziel', 'erfolg', 'problem', 'chance'],
      situationAssessment: ['budget', 'team', 'resource', 'timeline', 'constraint', 'data', 'employee', 'staff', 'regulation', 'budget', 'mitarbeiter', 'daten', 'zeitrahmen'],
      aiGoals: ['accuracy', 'input', 'output', 'model', 'algorithm', 'prediction', 'automat', 'solution', 'genauigkeit', 'modell', 'lösung', 'vorhersage'],
      projectPlan: ['milestone', 'phase', 'implement', 'pilot', 'timeline', 'rollout', 'start', 'deploy', 'meilenstein', 'umsetzung', 'pilot']
    };

    const newCovered = { ...topicsCovered };
    Object.entries(topicKeywords).forEach(([topic, keywords]) => {
      if (!skippedTopics[topic]) {
        const matches = keywords.filter(kw => allText.includes(kw)).length;
        if (matches >= 2) {
          newCovered[topic] = true;
        }
      }
    });

    if (JSON.stringify(newCovered) !== JSON.stringify(topicsCovered)) {
      setTopicsCovered(newCovered);
    }
  }, [messages, skippedTopics]);

  // Trigger incremental findings extraction after certain message counts
  const lastExtractionCount = useRef(0);
  useEffect(() => {
    const messageCount = messages.filter(m => m.role !== 'system').length;
    // Extract after every 4 messages (2 exchanges), but only if we have API key
    if (messageCount >= 4 && messageCount - lastExtractionCount.current >= 4 && apiKeyManager.isSet()) {
      lastExtractionCount.current = messageCount;
      // Run extraction in background without blocking UI
      consultationAPI.extractIncremental(sessionUuid)
        .then(response => {
          if (response.data.updated && response.data.findings) {
            setFindings(response.data.findings);
          }
        })
        .catch(err => console.error('Incremental extraction failed:', err));
    }
  }, [messages, sessionUuid]);

  // Handle skipping a topic
  const handleSkipTopic = (topicKey) => {
    setSkippedTopics(prev => ({ ...prev, [topicKey]: true }));
    setTopicsCovered(prev => ({ ...prev, [topicKey]: true }));
  };

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

      // Load collaborative status
      try {
        const collabResponse = await consultationAPI.getCollaborativeStatus(sessionUuid);
        setCollaborativeMode(collabResponse.data.collaborative_mode);
        setParticipants(collabResponse.data.participants || []);
        setConsultationStarted(collabResponse.data.consultation_started);

        // Check if current user is the owner
        const storedUuid = localStorage.getItem(`participant_${sessionUuid}`);
        if (storedUuid && collabResponse.data.owner_participant_uuid === storedUuid) {
          setIsOwner(true);
        }
      } catch (e) {
        // Collaborative mode not available
      }

      // Try to load existing consultation messages
      try {
        const messagesResponse = collaborativeMode
          ? await consultationAPI.getCollaborativeMessages(sessionUuid)
          : await consultationAPI.getMessages(sessionUuid);
        if (messagesResponse.data.length > 0) {
          setMessages(messagesResponse.data);
          setConsultationStarted(true);
          // Track last message ID for polling
          setLastMessageId(messagesResponse.data[messagesResponse.data.length - 1].id);
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
    // Check if API key is set
    if (!apiKeyManager.isSet()) {
      setPendingAction('start');
      setShowApiKeyPrompt(true);
      return;
    }

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
    // Check if API key is set
    if (!apiKeyManager.isSet()) {
      setPendingAction('summarize');
      setShowApiKeyPrompt(true);
      return;
    }

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

  const handleApiKeySet = () => {
    setShowApiKeyPrompt(false);
    // Execute the pending action now that we have the API key
    if (pendingAction === 'start') {
      handleStartConsultation();
    } else if (pendingAction === 'summarize') {
      handleSummarize();
    }
    setPendingAction(null);
  };

  // Collaborative mode handlers
  const handleToggleCollaborativeMode = async () => {
    try {
      const newMode = !collaborativeMode;
      await consultationAPI.setCollaborativeMode(sessionUuid, newMode);
      setCollaborativeMode(newMode);
      if (newMode) {
        setShowSharePanel(true);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to toggle collaborative mode');
    }
  };

  const handleCopyLink = async () => {
    const shareUrl = `${window.location.origin}/session/${sessionUuid}/step4`;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    } catch (err) {
      // Fallback
      const textArea = document.createElement('textarea');
      textArea.value = shareUrl;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    }
  };

  const handleSendCollaborativeMessage = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || sendingMessage) return;

    const userMessage = inputMessage.trim();
    setInputMessage('');
    setSendingMessage(true);

    try {
      // Save message with participant info
      const response = await consultationAPI.saveCollaborativeMessage(
        sessionUuid,
        userMessage,
        participantUuid
      );

      // Add to local messages
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
      setError(err.response?.data?.detail || 'Failed to send message');
      setSendingMessage(false);
    }
  };

  const handleRequestAiResponseCollaborative = async () => {
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
          // Reload messages to get proper ID from backend
          loadData();
        },
        (errorMsg) => {
          setError(errorMsg || 'Failed to get AI response');
          setSendingMessage(false);
          setMessages(prev => prev.filter(m => m.id !== aiMsgId || m.content));
        }
      );
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to get AI response');
      setSendingMessage(false);
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

        {/* Collaborative Mode Panel - show for session owner */}
        {(isOwner || collaborativeMode) && ideas.length > 0 && (
          <div className="mb-6 bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <h3 className="font-semibold text-gray-900">{t('step4.collaborative.title')}</h3>
                {isOwner && (
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={collaborativeMode}
                      onChange={handleToggleCollaborativeMode}
                      className="sr-only peer"
                      disabled={consultationStarted}
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                )}
                {!isOwner && collaborativeMode && (
                  <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                    {t('step4.collaborative.active')}
                  </span>
                )}
              </div>
              {collaborativeMode && (
                <button
                  onClick={() => setShowSharePanel(!showSharePanel)}
                  className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                >
                  {showSharePanel ? t('step4.collaborative.hideShare') : t('step4.collaborative.showShare')}
                </button>
              )}
            </div>

            {collaborativeMode && (
              <p className="text-sm text-gray-600 mt-2">
                {t('step4.collaborative.description')}
              </p>
            )}

            {/* Participants List */}
            {collaborativeMode && participants.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {participants.map((p) => (
                  <span
                    key={p.uuid}
                    className={`px-3 py-1 rounded-full text-xs font-medium ${
                      p.is_owner
                        ? 'bg-yellow-100 text-yellow-800'
                        : 'bg-blue-100 text-blue-800'
                    }`}
                  >
                    {p.name} {p.is_owner && '(Owner)'}
                  </span>
                ))}
              </div>
            )}

            {/* Share Panel with QR Code */}
            {collaborativeMode && showSharePanel && (
              <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
                <div className="flex flex-col md:flex-row items-center gap-4">
                  <div className="bg-white p-3 rounded-lg border border-gray-200">
                    <QRCodeSVG
                      value={`${window.location.origin}/session/${sessionUuid}/step4`}
                      size={120}
                      level="M"
                      includeMargin={true}
                    />
                  </div>
                  <div className="flex-1 space-y-3">
                    <p className="text-sm text-gray-600">{t('step4.collaborative.shareInstructions')}</p>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        readOnly
                        value={`${window.location.origin}/session/${sessionUuid}/step4`}
                        className="flex-1 px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-600 truncate"
                      />
                      <button
                        onClick={handleCopyLink}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                          linkCopied
                            ? 'bg-green-600 text-white'
                            : 'bg-blue-600 text-white hover:bg-blue-700'
                        }`}
                      >
                        {linkCopied ? t('common.copied') : t('common.copy')}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
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
                          {/* Show participant name in collaborative mode */}
                          {collaborativeMode && msg.participant_name && msg.role === 'user' && (
                            <p className="text-xs font-semibold mb-1 opacity-80">
                              {msg.participant_name}
                            </p>
                          )}
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
                  <form onSubmit={collaborativeMode ? handleSendCollaborativeMessage : handleSendMessage} className="flex gap-2">
                    <input
                      type="text"
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      placeholder={collaborativeMode ? t('step4.chat.collaborativePlaceholder') : t('step4.chat.messagePlaceholder')}
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
                  <div className="mt-2 flex justify-between items-center">
                    {/* Request AI Response button for collaborative mode */}
                    {collaborativeMode && (
                      <button
                        onClick={handleRequestAiResponseCollaborative}
                        disabled={sendingMessage || messages.length < 2}
                        className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-300 transition-colors text-sm font-medium"
                      >
                        {sendingMessage ? t('step4.chat.thinking') : t('step4.chat.requestAiResponse')}
                      </button>
                    )}
                    <div className={collaborativeMode ? '' : 'ml-auto'}>
                      <button
                        onClick={handleSummarize}
                        disabled={summarizing || messages.length < 4}
                        className="text-sm text-blue-600 hover:text-blue-800 disabled:text-gray-400"
                      >
                        {summarizing ? t('step4.chat.generatingSummary') : t('step4.chat.generateSummary')}
                      </button>
                    </div>
                  </div>
                  {collaborativeMode && (
                    <p className="mt-2 text-xs text-gray-500">
                      {t('step4.chat.collaborativeHint')}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Findings sidebar - 1/3 width (CRISP-DM Business Understanding) */}
            <div className="space-y-4">
              {/* Topic Progress Tracker */}
              <div className="bg-white rounded-lg shadow p-4">
                <h3 className="font-semibold text-gray-900 mb-3 text-sm">{t('step4.topics.title')}</h3>
                <div className="space-y-2">
                  {[
                    { key: 'businessObjectives', label: t('step4.topics.businessObjectives') },
                    { key: 'situationAssessment', label: t('step4.topics.situationAssessment') },
                    { key: 'aiGoals', label: t('step4.topics.aiGoals') },
                    { key: 'projectPlan', label: t('step4.topics.projectPlan') }
                  ].map(topic => (
                    <div key={topic.key} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className={`w-4 h-4 rounded-full flex items-center justify-center ${
                          topicsCovered[topic.key]
                            ? skippedTopics[topic.key]
                              ? 'bg-gray-300'
                              : 'bg-green-500'
                            : 'bg-gray-200'
                        }`}>
                          {topicsCovered[topic.key] && (
                            skippedTopics[topic.key] ? (
                              <span className="text-white text-xs">–</span>
                            ) : (
                              <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                              </svg>
                            )
                          )}
                        </div>
                        <span className={`text-sm ${
                          topicsCovered[topic.key]
                            ? skippedTopics[topic.key]
                              ? 'text-gray-400 line-through'
                              : 'text-green-700'
                            : 'text-gray-600'
                        }`}>
                          {topic.label}
                        </span>
                      </div>
                      {!topicsCovered[topic.key] && consultationStarted && (
                        <button
                          onClick={() => handleSkipTopic(topic.key)}
                          className="text-xs text-gray-400 hover:text-gray-600"
                          title={t('step4.topics.skip')}
                        >
                          {t('step4.topics.skipBtn')}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                <div className="mt-3 pt-3 border-t">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-gray-500">{t('step4.topics.progress')}</span>
                    <span className="font-medium text-blue-600">
                      {Object.values(topicsCovered).filter(Boolean).length}/4
                    </span>
                  </div>
                  <div className="mt-1 w-full bg-gray-200 rounded-full h-1.5">
                    <div
                      className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                      style={{ width: `${(Object.values(topicsCovered).filter(Boolean).length / 4) * 100}%` }}
                    />
                  </div>
                </div>
              </div>

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
        <div className="mt-6 flex justify-start">
          <button
            onClick={() => navigate(`/session/${sessionUuid}/step3`)}
            className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
          >
            {t('step4.backStep3')}
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

export default Step4Page;
