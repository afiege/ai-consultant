import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import { sixThreeFiveAPI, prioritizationAPI } from '../services/api';
import { PageHeader, ExplanationBox } from '../components/common';

// Reusable markdown components for idea content
const IdeaMarkdown = ({ content, className = '' }) => (
  <div className={`prose prose-sm max-w-none ${className}`}>
    <ReactMarkdown
      components={{
        p: ({children}) => <p className="mb-1 last:mb-0">{children}</p>,
        strong: ({children}) => <strong className="font-semibold">{children}</strong>,
        em: ({children}) => <em className="italic">{children}</em>,
        ul: ({children}) => <ul className="list-disc ml-4 mb-1">{children}</ul>,
        ol: ({children}) => <ol className="list-decimal ml-4 mb-1">{children}</ol>,
        li: ({children}) => <li className="mb-0.5">{children}</li>,
      }}
    >
      {content}
    </ReactMarkdown>
  </div>
);

const Step3Page = () => {
  const { t } = useTranslation();
  const { sessionUuid } = useParams();
  const navigate = useNavigate();

  const [ideas, setIdeas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Voting state: { ideaId: points }
  const [votes, setVotes] = useState({});
  const [hasVoted, setHasVoted] = useState(false);
  const [results, setResults] = useState(null);

  // Get participant UUID from localStorage
  const participantUuid = localStorage.getItem(`participant_${sessionUuid}`);

  // Calculate remaining points
  const totalPoints = 3;
  const usedPoints = Object.values(votes).reduce((sum, p) => sum + p, 0);
  const remainingPoints = totalPoints - usedPoints;

  useEffect(() => {
    loadIdeas();
  }, [sessionUuid]);

  const loadIdeas = async () => {
    try {
      const response = await sixThreeFiveAPI.getIdeas(sessionUuid);
      setIdeas(response.data);

      // Check if this participant already voted (try loading results)
      try {
        const resultsResponse = await prioritizationAPI.getResults(sessionUuid);
        if (resultsResponse.data.ranked_ideas?.some(i => i.total_points > 0)) {
          setResults(resultsResponse.data);
          setHasVoted(true);
        }
      } catch (e) {
        // No results yet, that's fine
      }
    } catch (err) {
      console.error('Failed to load ideas:', err);
      setError('Failed to load ideas');
    } finally {
      setLoading(false);
    }
  };

  const handleAddPoint = (ideaId) => {
    if (remainingPoints <= 0) return;

    setVotes(prev => ({
      ...prev,
      [ideaId]: (prev[ideaId] || 0) + 1
    }));
  };

  const handleRemovePoint = (ideaId) => {
    if (!votes[ideaId] || votes[ideaId] <= 0) return;

    setVotes(prev => {
      const newVotes = { ...prev };
      newVotes[ideaId] = (newVotes[ideaId] || 0) - 1;
      if (newVotes[ideaId] === 0) {
        delete newVotes[ideaId];
      }
      return newVotes;
    });
  };

  const handleSubmitVotes = async () => {
    if (remainingPoints !== 0) {
      setError(`Please allocate all ${totalPoints} points. You have ${remainingPoints} remaining.`);
      return;
    }

    if (!participantUuid) {
      setError('No participant found. Please go back to Step 2 and join the session first.');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await prioritizationAPI.submitVote(sessionUuid, {
        participant_uuid: participantUuid,
        votes: votes
      });

      // Load results
      const resultsResponse = await prioritizationAPI.getResults(sessionUuid);
      setResults(resultsResponse.data);
      setHasVoted(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit votes');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">{t('common.loading')}</p>
      </div>
    );
  }

  // If no ideas exist, skip prioritization
  if (ideas.length === 0) {
    return (
      <div className="min-h-screen bg-gray-50">
        <PageHeader
          title={t('step3.title')}
          subtitle={t('step3.subtitle', { points: totalPoints })}
          sessionUuid={sessionUuid}
        />
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
            <h2 className="text-lg font-semibold text-yellow-800 mb-2">{t('step3.noIdeas.title')}</h2>
            <p className="text-yellow-700 mb-6">
              {t('step3.noIdeas.message')}
            </p>
            <button
              onClick={() => navigate(`/session/${sessionUuid}/step4`)}
              className="bg-blue-600 text-white py-2 px-6 rounded-md hover:bg-blue-700 transition-colors"
            >
              {t('step3.noIdeas.continueButton')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <PageHeader
        title={t('step3.title')}
        subtitle={t('step3.subtitle', { points: totalPoints })}
        sessionUuid={sessionUuid}
      />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* Explanation */}
        {!hasVoted && (
          <ExplanationBox
            title={t('step3.explanation.title')}
            description={t('step3.explanation.description')}
            bullets={[
              t('step3.explanation.bullet1'),
              t('step3.explanation.bullet2'),
              t('step3.explanation.bullet3'),
            ]}
            tip={t('step3.explanation.tip')}
            variant="yellow"
            defaultOpen={true}
          />
        )}

        {!hasVoted ? (
          <>
            {/* Points indicator */}
            <div className="bg-white rounded-lg shadow p-4 mb-6 sticky top-4 z-10">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-lg font-semibold text-gray-900">
                    {t('step3.voting.pointsRemaining')} <span className={remainingPoints === 0 ? 'text-green-600' : 'text-blue-600'}>{remainingPoints}</span> / {totalPoints}
                  </p>
                  <p className="text-sm text-gray-600">
                    {t('step3.voting.clickToAdd')}
                  </p>
                </div>
                <button
                  onClick={handleSubmitVotes}
                  disabled={remainingPoints !== 0 || submitting}
                  className="bg-green-600 text-white py-2 px-6 rounded-md hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium"
                >
                  {submitting ? t('step3.voting.submitting') : t('step3.voting.submitVotes')}
                </button>
              </div>
            </div>

            {/* Ideas list */}
            <div className="space-y-4">
              {ideas.map((idea) => (
                <div
                  key={idea.id}
                  className={`bg-white rounded-lg shadow p-4 border-2 transition-colors ${
                    votes[idea.id] ? 'border-blue-400 bg-blue-50' : 'border-transparent'
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <IdeaMarkdown content={idea.content} className="text-gray-900" />
                      <p className="text-sm text-gray-500 mt-2">
                        {t('step3.results.by')} {idea.participant_name} ({t('step3.results.round')} {idea.round_number})
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleRemovePoint(idea.id)}
                        disabled={!votes[idea.id]}
                        className="w-8 h-8 rounded-full bg-gray-200 text-gray-700 hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center font-bold"
                      >
                        -
                      </button>
                      <span className="w-8 text-center text-lg font-bold text-blue-600">
                        {votes[idea.id] || 0}
                      </span>
                      <button
                        onClick={() => handleAddPoint(idea.id)}
                        disabled={remainingPoints <= 0}
                        className="w-8 h-8 rounded-full bg-blue-600 text-white hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center font-bold"
                      >
                        +
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <>
            {/* Results view */}
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-6">
              <p className="text-green-800 font-medium">
                {t('step3.results.votesRecorded')}
              </p>
            </div>

            {/* Top idea(s) highlight */}
            {results?.top_ideas?.length > 0 && (
              <div className="bg-yellow-50 border-2 border-yellow-400 rounded-lg p-6 mb-6">
                <h3 className="text-lg font-bold text-yellow-800 mb-3">
                  {results.top_ideas.length > 1 ? t('step3.results.topIdeas') : t('step3.results.topIdea')} ({results.top_ideas[0].total_points} {t('step3.results.points')})
                </h3>
                {results.top_ideas.map((idea) => (
                  <div key={idea.idea_id} className="bg-white rounded-lg p-4 mb-2 last:mb-0">
                    <IdeaMarkdown content={idea.idea_content} className="text-gray-900 font-medium" />
                    <p className="text-sm text-gray-500 mt-1">{t('step3.results.by')} {idea.participant_name}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Full ranking */}
            <div className="bg-white rounded-lg shadow">
              <div className="px-4 py-3 border-b border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900">{t('step3.results.allRanked')}</h3>
              </div>
              <div className="divide-y divide-gray-100">
                {results?.ranked_ideas?.map((idea, index) => (
                  <div key={idea.idea_id} className="px-4 py-3 flex items-center gap-4">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                      idea.rank === 1 ? 'bg-yellow-400 text-yellow-900' : 'bg-gray-200 text-gray-700'
                    }`}>
                      #{idea.rank}
                    </div>
                    <div className="flex-1">
                      <IdeaMarkdown content={idea.idea_content} className="text-gray-900" />
                      <p className="text-sm text-gray-500">{t('step3.results.by')} {idea.participant_name}</p>
                    </div>
                    <div className="text-right">
                      <span className="text-lg font-bold text-blue-600">{idea.total_points}</span>
                      <p className="text-xs text-gray-500">{t('step3.results.points')}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Continue button */}
            <div className="mt-8 text-center">
              <button
                onClick={() => navigate(`/session/${sessionUuid}/step4`)}
                className="bg-blue-600 text-white py-3 px-8 rounded-md hover:bg-blue-700 transition-colors font-medium"
              >
                {t('step3.continueStep4')}
              </button>
            </div>
          </>
        )}

        {/* Navigation */}
        <div className="mt-8 flex justify-between items-center">
          <button
            onClick={() => navigate(`/session/${sessionUuid}/step2`)}
            className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
          >
            {t('step3.backStep2')}
          </button>
          <div className="flex gap-4">
            {!hasVoted && (
              <button
                onClick={() => navigate(`/session/${sessionUuid}/step4`)}
                className="px-6 py-2 text-gray-500 hover:text-gray-700"
              >
                {t('step3.skipToConsultation')}
              </button>
            )}
            <button
              onClick={() => navigate(`/session/${sessionUuid}/export`)}
              className="px-6 py-2 text-green-600 hover:text-green-800 font-medium"
            >
              {t('common.exportReport')} →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Step3Page;
