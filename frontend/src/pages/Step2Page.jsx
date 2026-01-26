import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { sixThreeFiveAPI, apiKeyManager } from '../services/api';
import ParticipantJoin from '../components/step2/ParticipantJoin';
import IdeaSheet from '../components/step2/IdeaSheet';
import ShareSession from '../components/step2/ShareSession';
import { PageHeader, ExplanationBox } from '../components/common';
import ApiKeyPrompt from '../components/common/ApiKeyPrompt';

const Step2Page = () => {
  const { t } = useTranslation();
  const { sessionUuid } = useParams();
  const navigate = useNavigate();

  const [participantUuid, setParticipantUuid] = useState(null);
  const [sessionStatus, setSessionStatus] = useState(null);
  const [mySheet, setMySheet] = useState(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [timeLeft, setTimeLeft] = useState(300); // 5 minutes in seconds
  const [showApiKeyPrompt, setShowApiKeyPrompt] = useState(false);
  const [pendingAction, setPendingAction] = useState(null); // 'start' or 'advance'

  // Load participant UUID from localStorage
  useEffect(() => {
    const stored = localStorage.getItem(`participant_${sessionUuid}`);
    if (stored) {
      setParticipantUuid(stored);
    }
  }, [sessionUuid]);

  // Poll for session status
  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 3000); // Poll every 3 seconds
    return () => clearInterval(interval);
  }, [sessionUuid]);

  // Load my sheet if I'm a participant
  useEffect(() => {
    if (participantUuid && sessionStatus?.status !== 'not_started') {
      loadMySheet();
      const interval = setInterval(loadMySheet, 3000); // Poll every 3 seconds
      return () => clearInterval(interval);
    }
  }, [participantUuid, sessionStatus]);

  // Timer countdown
  useEffect(() => {
    if (sessionStatus?.status === 'in_progress' && !mySheet?.has_submitted_current_round) {
      const timer = setInterval(() => {
        setTimeLeft(prev => (prev > 0 ? prev - 1 : 0));
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [sessionStatus, mySheet]);

  const loadStatus = async () => {
    try {
      const response = await sixThreeFiveAPI.getStatus(sessionUuid);
      setSessionStatus(response.data);
    } catch (err) {
      console.error('Error loading status:', err);
    }
  };

  const loadMySheet = async () => {
    try {
      const response = await sixThreeFiveAPI.getMySheet(sessionUuid, participantUuid);
      setMySheet(response.data);
    } catch (err) {
      console.error('Error loading sheet:', err);
    }
  };

  const handleJoin = async (name) => {
    try {
      const response = await sixThreeFiveAPI.join(sessionUuid, { name });
      const newParticipantUuid = response.data.participant_uuid;
      setParticipantUuid(newParticipantUuid);
      localStorage.setItem(`participant_${sessionUuid}`, newParticipantUuid);
      await loadStatus();
    } catch (err) {
      throw new Error(err.response?.data?.detail || 'Failed to join session');
    }
  };

  const handleStartSession = async () => {
    // Check if API key is set
    if (!apiKeyManager.isSet()) {
      setPendingAction('start');
      setShowApiKeyPrompt(true);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await sixThreeFiveAPI.start(sessionUuid);
      await loadStatus();
      await loadMySheet();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start session');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitIdeas = async (ideas) => {
    setSubmitting(true);
    try {
      await sixThreeFiveAPI.submitIdeas(sessionUuid, participantUuid, {
        sheet_id: mySheet.sheet_id,
        round_number: mySheet.current_round,
        ideas
      });
      await loadMySheet();
      setTimeLeft(300); // Reset timer
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to submit ideas');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAdvanceRound = async () => {
    // Check if API key is set
    if (!apiKeyManager.isSet()) {
      setPendingAction('advance');
      setShowApiKeyPrompt(true);
      return;
    }

    setLoading(true);
    try {
      const response = await sixThreeFiveAPI.advanceRound(sessionUuid);
      if (response.data.status === 'complete') {
        // Session complete, go to next step
        navigate(`/session/${sessionUuid}/step3`);
      } else {
        await loadStatus();
        await loadMySheet();
        setTimeLeft(300); // Reset timer for new round
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to advance round');
    } finally {
      setLoading(false);
    }
  };

  const handleSkipSession = async () => {
    if (!confirm(t('step2.session.skipConfirm'))) {
      return;
    }

    setLoading(true);
    try {
      await sixThreeFiveAPI.skip(sessionUuid);
      navigate(`/session/${sessionUuid}/step3`);
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to skip session');
    } finally {
      setLoading(false);
    }
  };

  const handleApiKeySet = () => {
    setShowApiKeyPrompt(false);
    // Execute the pending action now that we have the API key
    if (pendingAction === 'start') {
      handleStartSession();
    } else if (pendingAction === 'advance') {
      handleAdvanceRound();
    }
    setPendingAction(null);
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const canAdvance = sessionStatus?.sheets_submitted === sessionStatus?.total_sheets;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <PageHeader
        title={t('step2.title')}
        subtitle={t('step2.subtitle')}
        sessionUuid={sessionUuid}
      />

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* Explanation - show when session hasn't started */}
        {sessionStatus?.status === 'not_started' && (
          <ExplanationBox
            title={t('step2.explanation.title')}
            description={t('step2.explanation.description')}
            bullets={[
              t('step2.explanation.bullet1'),
              t('step2.explanation.bullet2'),
              t('step2.explanation.bullet3'),
              t('step2.explanation.bullet4'),
            ]}
            tip={t('step2.explanation.tip')}
            variant="green"
            defaultOpen={true}
          />
        )}

        {/* Not Started - Join/Start */}
        {sessionStatus?.status === 'not_started' && (
          <div className="space-y-6">
            {/* Share Session QR Code */}
            <div className="max-w-2xl mx-auto">
              <ShareSession sessionUuid={sessionUuid} />
            </div>

            {/* Only show join form if user hasn't joined yet */}
            {!participantUuid ? (
              <ParticipantJoin
                onJoin={handleJoin}
                participants={sessionStatus.participants || []}
                sessionStarted={false}
              />
            ) : (
              /* Show participant list when user has already joined */
              <div className="max-w-2xl mx-auto">
                <div className="bg-white rounded-lg shadow-lg p-8">
                  <h2 className="text-2xl font-bold text-gray-900 mb-4">
                    {t('step2.join.title')}
                  </h2>
                  <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-md">
                    <p className="text-green-800 font-medium">
                      ✓ {t('step2.join.alreadyJoined')}
                    </p>
                  </div>
                  {sessionStatus.participants?.length > 0 && (
                    <div className="p-4 bg-blue-50 rounded-md">
                      <h3 className="font-semibold text-gray-900 mb-2">
                        {t('step2.join.participants')} ({sessionStatus.participants.length}/6)
                      </h3>
                      <div className="space-y-1">
                        {sessionStatus.participants.map((p) => (
                          <div key={p.uuid} className="flex items-center text-sm">
                            {p.is_ai ? (
                              <span className="text-blue-600">🤖 {p.name}</span>
                            ) : (
                              <span className="text-gray-700">👤 {p.name}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {participantUuid && (
              <div className="max-w-2xl mx-auto space-y-4">
                {/* Only show Start button to session owner */}
                {participantUuid === sessionStatus.owner_participant_uuid ? (
                  <>
                    <button
                      onClick={handleStartSession}
                      disabled={loading}
                      className="w-full bg-green-600 text-white py-3 px-6 rounded-md hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium text-lg"
                    >
                      {loading ? t('step2.session.starting') : t('step2.session.startButton')}
                    </button>
                    <p className="text-sm text-gray-600 text-center">
                      {t('step2.session.aiNote')}
                    </p>

                    <div className="border-t border-gray-200 pt-4">
                      <button
                        onClick={handleSkipSession}
                        disabled={loading}
                        className="w-full bg-gray-200 text-gray-700 py-2 px-6 rounded-md hover:bg-gray-300 disabled:bg-gray-100 disabled:cursor-not-allowed transition-colors font-medium"
                      >
                        {t('step2.session.skipButton')}
                      </button>
                      <p className="text-xs text-gray-500 text-center mt-2">
                        {t('step2.session.skipNote')}
                      </p>
                    </div>
                  </>
                ) : (
                  /* Non-owners see a waiting message */
                  <div className="bg-blue-50 border border-blue-200 rounded-md p-4 text-center">
                    <p className="text-blue-800 font-medium">
                      {t('step2.session.waitingForOwner')}
                    </p>
                    <p className="text-sm text-blue-600 mt-1">
                      {t('step2.session.waitingForOwnerNote')}
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* In Progress */}
        {sessionStatus?.status === 'in_progress' && participantUuid && mySheet && (
          <div className="space-y-6">
            {/* Status Bar */}
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">
                    {t('step2.progress.round', { current: sessionStatus.current_round, total: sessionStatus.total_sheets })}
                  </p>
                  <p className="text-lg font-semibold text-gray-900">
                    {t('step2.progress.submitted', { count: sessionStatus.sheets_submitted, total: sessionStatus.total_sheets })}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-sm text-gray-600">{t('step2.progress.timeRemaining')}</p>
                  <p className="text-2xl font-bold text-blue-600">{formatTime(timeLeft)}</p>
                </div>
              </div>

              {/* Participants Status */}
              <div className="mt-4 flex flex-wrap gap-2">
                {sessionStatus.participants?.map((p) => (
                  <span
                    key={p.uuid}
                    className={`px-3 py-1 rounded-full text-xs font-medium ${
                      p.is_ai
                        ? 'bg-blue-100 text-blue-800'
                        : 'bg-green-100 text-green-800'
                    }`}
                  >
                    {p.is_ai ? '🤖' : '👤'} {p.name}
                  </span>
                ))}
              </div>
            </div>

            {/* Idea Sheet */}
            <IdeaSheet
              sheetData={mySheet}
              onSubmit={handleSubmitIdeas}
              submitting={submitting}
            />

            {/* Advance Round Button (only for session owner when all submitted) */}
            {canAdvance && (
              <div className="bg-white rounded-lg shadow p-6 space-y-3">
                <p className="text-green-700 font-medium mb-4">
                  ✓ {t('step2.progress.allSubmitted')}
                </p>
                {participantUuid === sessionStatus.owner_participant_uuid ? (
                  <>
                    <button
                      onClick={handleAdvanceRound}
                      disabled={loading}
                      className="w-full bg-blue-600 text-white py-3 px-6 rounded-md hover:bg-blue-700 disabled:bg-gray-300 transition-colors font-medium"
                    >
                      {sessionStatus.current_round >= 6
                        ? t('step2.progress.completeSession')
                        : t('step2.progress.advanceRound', { next: sessionStatus.current_round + 1 })}
                    </button>
                    <button
                      onClick={handleSkipSession}
                      disabled={loading}
                      className="w-full bg-gray-200 text-gray-700 py-2 px-6 rounded-md hover:bg-gray-300 disabled:bg-gray-100 transition-colors font-medium text-sm"
                    >
                      {t('step2.progress.skipRemaining')}
                    </button>
                  </>
                ) : (
                  <p className="text-blue-600 text-center">
                    {t('step2.progress.waitingForOwnerAdvance')}
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Complete */}
        {sessionStatus?.status === 'complete' && (
          <div className="max-w-2xl mx-auto bg-white rounded-lg shadow-lg p-8 text-center">
            <div className="text-green-600 mb-4">
              <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              {t('step2.complete.title')}
            </h2>
            <p className="text-gray-600 mb-6">
              {t('step2.complete.message')}
            </p>
            <button
              onClick={() => navigate(`/session/${sessionUuid}/step3`)}
              className="bg-blue-600 text-white py-3 px-8 rounded-md hover:bg-blue-700 transition-colors font-medium"
            >
              {t('step2.complete.continueButton')}
            </button>
          </div>
        )}

        {/* Navigation */}
        <div className="mt-8 flex justify-start">
          <button
            onClick={() => navigate(`/session/${sessionUuid}/step1b`)}
            className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
          >
            {t('step2.backStep1')}
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

export default Step2Page;
