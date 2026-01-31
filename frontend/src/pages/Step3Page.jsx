import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import { sixThreeFiveAPI, prioritizationAPI, apiKeyManager } from '../services/api';
import { PageHeader, ExplanationBox } from '../components/common';
import Step3TestModePanel from '../components/common/Step3TestModePanel';
import { useTestMode } from '../hooks/useTestMode';

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

  // Active tab: 'clusters' (Phase 1) or 'ideas' (Phase 2)
  const [activeTab, setActiveTab] = useState('clusters');

  // Loading states
  const [loading, setLoading] = useState(true);
  const [clustering, setClustering] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Data
  const [ideas, setIdeas] = useState([]);
  const [clusters, setClusters] = useState([]);
  const [selectedClusterId, setSelectedClusterId] = useState(null);
  const [clusterIdeas, setClusterIdeas] = useState([]);

  // Phase 1 voting state
  const [clusterVotes, setClusterVotes] = useState({});
  const [hasVotedClusters, setHasVotedClusters] = useState(false);
  const [clusterResults, setClusterResults] = useState(null);

  // Phase 2 voting state
  const [ideaVotes, setIdeaVotes] = useState({});
  const [hasVotedIdeas, setHasVotedIdeas] = useState(false);
  const [ideaResults, setIdeaResults] = useState(null);

  // Get participant UUID from localStorage
  const participantUuid = localStorage.getItem(`participant_${sessionUuid}`);

  // Test mode
  const testModeEnabled = useTestMode();

  // Calculate remaining points for each phase
  const totalPoints = 3;
  const usedClusterPoints = Object.values(clusterVotes).reduce((sum, p) => sum + p, 0);
  const remainingClusterPoints = totalPoints - usedClusterPoints;
  const usedIdeaPoints = Object.values(ideaVotes).reduce((sum, p) => sum + p, 0);
  const remainingIdeaPoints = totalPoints - usedIdeaPoints;

  useEffect(() => {
    loadData();
  }, [sessionUuid]);

  const loadData = async () => {
    try {
      setLoading(true);

      // Load all ideas
      const ideasResponse = await sixThreeFiveAPI.getIdeas(sessionUuid);
      setIdeas(ideasResponse.data);

      // Load existing clusters
      const clustersResponse = await prioritizationAPI.getClusters(sessionUuid);
      setClusters(clustersResponse.data.clusters || []);
      setSelectedClusterId(clustersResponse.data.selected_cluster_id);

      // Check if clusters exist and we have a selected cluster
      if (clustersResponse.data.selected_cluster_id) {
        setActiveTab('ideas');

        // Load cluster ideas for Phase 2
        try {
          const clusterIdeasResponse = await prioritizationAPI.getClusterIdeas(sessionUuid);
          setClusterIdeas(clusterIdeasResponse.data.ideas || []);
        } catch (e) {
          console.error('Failed to load cluster ideas:', e);
        }

        // Check for Phase 2 results
        try {
          const ideaResultsResponse = await prioritizationAPI.getIdeaResults(sessionUuid);
          if (ideaResultsResponse.data.ranked_ideas?.some(i => i.total_points > 0)) {
            setIdeaResults(ideaResultsResponse.data);
            setHasVotedIdeas(true);
          }
        } catch (e) {
          // No results yet
        }
      } else if (clustersResponse.data.clusters?.length > 0) {
        // Clusters exist, check for Phase 1 results
        try {
          const clusterResultsResponse = await prioritizationAPI.getClusterResults(sessionUuid);
          if (clusterResultsResponse.data.ranked_clusters?.some(c => c.total_points > 0)) {
            setClusterResults(clusterResultsResponse.data);
            setHasVotedClusters(true);
          }
        } catch (e) {
          // No results yet
        }
      }
    } catch (err) {
      console.error('Failed to load data:', err);
      setError(t('step3.errors.loadFailed'));
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateClusters = async () => {
    setClustering(true);
    setError(null);

    try {
      const response = await prioritizationAPI.generateClusters(sessionUuid, apiKeyManager.get());
      setClusters(response.data.clusters || []);
      setClusterVotes({});
      setHasVotedClusters(false);
      setClusterResults(null);
    } catch (err) {
      console.error('Failed to generate clusters:', err);
      setError(err.response?.data?.detail || t('step3.errors.clusterFailed'));
    } finally {
      setClustering(false);
    }
  };

  // Phase 1: Cluster voting
  const handleAddClusterPoint = (clusterId) => {
    if (remainingClusterPoints <= 0) return;
    setClusterVotes(prev => ({
      ...prev,
      [clusterId]: (prev[clusterId] || 0) + 1
    }));
  };

  const handleRemoveClusterPoint = (clusterId) => {
    if (!clusterVotes[clusterId] || clusterVotes[clusterId] <= 0) return;
    setClusterVotes(prev => {
      const newVotes = { ...prev };
      newVotes[clusterId] = (newVotes[clusterId] || 0) - 1;
      if (newVotes[clusterId] === 0) delete newVotes[clusterId];
      return newVotes;
    });
  };

  const handleSubmitClusterVotes = async () => {
    if (remainingClusterPoints !== 0) {
      setError(t('step3.errors.allocateAllPoints', { total: totalPoints, remaining: remainingClusterPoints }));
      return;
    }

    if (!participantUuid) {
      setError(t('step3.errors.noParticipant'));
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await prioritizationAPI.submitClusterVote(sessionUuid, {
        participant_uuid: participantUuid,
        votes: clusterVotes
      });

      // Load cluster results
      const resultsResponse = await prioritizationAPI.getClusterResults(sessionUuid);
      setClusterResults(resultsResponse.data);
      setHasVotedClusters(true);
    } catch (err) {
      setError(err.response?.data?.detail || t('step3.errors.voteFailed'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleSelectCluster = async (clusterId) => {
    setSubmitting(true);
    setError(null);

    try {
      await prioritizationAPI.selectCluster(sessionUuid, clusterId);
      setSelectedClusterId(clusterId);

      // Load cluster ideas for Phase 2
      const clusterIdeasResponse = await prioritizationAPI.getClusterIdeas(sessionUuid);
      setClusterIdeas(clusterIdeasResponse.data.ideas || []);

      setActiveTab('ideas');
    } catch (err) {
      setError(err.response?.data?.detail || t('step3.errors.selectFailed'));
    } finally {
      setSubmitting(false);
    }
  };

  // Phase 2: Idea voting
  const handleAddIdeaPoint = (ideaId) => {
    if (remainingIdeaPoints <= 0) return;
    setIdeaVotes(prev => ({
      ...prev,
      [ideaId]: (prev[ideaId] || 0) + 1
    }));
  };

  const handleRemoveIdeaPoint = (ideaId) => {
    if (!ideaVotes[ideaId] || ideaVotes[ideaId] <= 0) return;
    setIdeaVotes(prev => {
      const newVotes = { ...prev };
      newVotes[ideaId] = (newVotes[ideaId] || 0) - 1;
      if (newVotes[ideaId] === 0) delete newVotes[ideaId];
      return newVotes;
    });
  };

  const handleSubmitIdeaVotes = async () => {
    if (remainingIdeaPoints !== 0) {
      setError(t('step3.errors.allocateAllPoints', { total: totalPoints, remaining: remainingIdeaPoints }));
      return;
    }

    if (!participantUuid) {
      setError(t('step3.errors.noParticipant'));
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await prioritizationAPI.submitIdeaVote(sessionUuid, {
        participant_uuid: participantUuid,
        votes: ideaVotes
      });

      // Load idea results
      const resultsResponse = await prioritizationAPI.getIdeaResults(sessionUuid);
      setIdeaResults(resultsResponse.data);
      setHasVotedIdeas(true);
    } catch (err) {
      setError(err.response?.data?.detail || t('step3.errors.voteFailed'));
    } finally {
      setSubmitting(false);
    }
  };

  // Handle test mode generated votes
  const handleTestModeVotes = (votes) => {
    if (activeTab === 'clusters') {
      setClusterVotes(votes);
    } else {
      setIdeaVotes(votes);
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
            <p className="text-yellow-700 mb-6">{t('step3.noIdeas.message')}</p>
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

  // Get selected cluster info
  const selectedCluster = clusters.find(c => c.id === selectedClusterId);

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

        {/* Tab Navigation */}
        <div className="border-b border-gray-200 mb-6">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('clusters')}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors flex items-center gap-2 ${
                activeTab === 'clusters'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${
                activeTab === 'clusters' ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-600'
              }`}>
                3a
              </span>
              {t('step3.tabs.clusters')}
              {hasVotedClusters && selectedClusterId && (
                <svg className="w-5 h-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
              )}
            </button>
            <button
              onClick={() => selectedClusterId && setActiveTab('ideas')}
              disabled={!selectedClusterId}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors flex items-center gap-2 ${
                activeTab === 'ideas'
                  ? 'border-purple-500 text-purple-600'
                  : !selectedClusterId
                    ? 'border-transparent text-gray-300 cursor-not-allowed'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${
                activeTab === 'ideas' ? 'bg-purple-100 text-purple-600' : 'bg-gray-100 text-gray-400'
              }`}>
                3b
              </span>
              {t('step3.tabs.ideas')}
              {hasVotedIdeas && (
                <svg className="w-5 h-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
              )}
            </button>
          </nav>
        </div>

        {/* Phase 1: Cluster Prioritization */}
        {activeTab === 'clusters' && (
          <div>
            {/* Explanation */}
            <ExplanationBox
              title={t('step3.phase1.explanation.title')}
              description={t('step3.phase1.explanation.description')}
              bullets={[
                t('step3.phase1.explanation.bullet1'),
                t('step3.phase1.explanation.bullet2'),
                t('step3.phase1.explanation.bullet3'),
              ]}
              tip={t('step3.phase1.explanation.tip')}
              variant="blue"
              defaultOpen={clusters.length === 0}
            />

            {/* Generate Clusters Button */}
            {clusters.length === 0 && (
              <div className="mt-6 text-center">
                <button
                  onClick={handleGenerateClusters}
                  disabled={clustering}
                  className="bg-blue-600 text-white py-3 px-8 rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium"
                >
                  {clustering ? (
                    <span className="flex items-center gap-2">
                      <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      {t('step3.phase1.generating')}
                    </span>
                  ) : (
                    t('step3.phase1.generateButton')
                  )}
                </button>
                <p className="mt-2 text-sm text-gray-500">{t('step3.phase1.generateHint')}</p>
              </div>
            )}

            {/* Cluster Voting */}
            {clusters.length > 0 && !hasVotedClusters && (
              <>
                {/* Points indicator */}
                <div className="bg-white rounded-lg shadow p-4 mb-6 sticky top-4 z-10">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-lg font-semibold text-gray-900">
                        {t('step3.voting.pointsRemaining')} <span className={remainingClusterPoints === 0 ? 'text-green-600' : 'text-blue-600'}>{remainingClusterPoints}</span> / {totalPoints}
                      </p>
                      <p className="text-sm text-gray-600">{t('step3.phase1.voteHint')}</p>
                    </div>
                    <button
                      onClick={handleSubmitClusterVotes}
                      disabled={remainingClusterPoints !== 0 || submitting}
                      className="bg-green-600 text-white py-2 px-6 rounded-md hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium"
                    >
                      {submitting ? t('step3.voting.submitting') : t('step3.voting.submitVotes')}
                    </button>
                  </div>
                </div>

                {/* Clusters list */}
                <div className="space-y-4">
                  {clusters.map((cluster) => (
                    <div
                      key={cluster.id}
                      className={`bg-white rounded-lg shadow p-4 border-2 transition-colors ${
                        clusterVotes[cluster.id] ? 'border-blue-400 bg-blue-50' : 'border-transparent'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <h3 className="font-semibold text-gray-900 text-lg">{cluster.name}</h3>
                          <p className="text-gray-600 mt-1">{cluster.description}</p>
                          <p className="text-sm text-gray-500 mt-2">
                            {t('step3.phase1.ideaCount', { count: cluster.idea_ids?.length || 0 })}
                          </p>
                          {/* Show ideas in cluster */}
                          {cluster.ideas && cluster.ideas.length > 0 && (
                            <div className="mt-3 pl-4 border-l-2 border-gray-200">
                              <p className="text-xs text-gray-500 mb-1">{t('step3.phase1.ideasInCluster')}</p>
                              <ul className="text-sm text-gray-700 space-y-1">
                                {cluster.ideas.slice(0, 3).map((idea, idx) => (
                                  <li key={idea.id} className="truncate">• {idea.content}</li>
                                ))}
                                {cluster.ideas.length > 3 && (
                                  <li className="text-gray-500 italic">
                                    {t('step3.phase1.moreIdeas', { count: cluster.ideas.length - 3 })}
                                  </li>
                                )}
                              </ul>
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleRemoveClusterPoint(cluster.id)}
                            disabled={!clusterVotes[cluster.id]}
                            className="w-8 h-8 rounded-full bg-gray-200 text-gray-700 hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center font-bold"
                          >
                            -
                          </button>
                          <span className="w-8 text-center text-lg font-bold text-blue-600">
                            {clusterVotes[cluster.id] || 0}
                          </span>
                          <button
                            onClick={() => handleAddClusterPoint(cluster.id)}
                            disabled={remainingClusterPoints <= 0}
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
            )}

            {/* Cluster Results */}
            {hasVotedClusters && clusterResults && (
              <>
                <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-6">
                  <p className="text-green-800 font-medium">{t('step3.phase1.votesRecorded')}</p>
                </div>

                {/* Top cluster(s) */}
                {clusterResults.top_clusters?.length > 0 && (
                  <div className="bg-yellow-50 border-2 border-yellow-400 rounded-lg p-6 mb-6">
                    <h3 className="text-lg font-bold text-yellow-800 mb-3">
                      {clusterResults.top_clusters.length > 1 ? t('step3.phase1.topClusters') : t('step3.phase1.topCluster')}
                      {' '}({clusterResults.top_clusters[0].total_points} {t('step3.results.points')})
                    </h3>
                    {clusterResults.top_clusters.map((cluster) => (
                      <div key={cluster.cluster_id} className="bg-white rounded-lg p-4 mb-2 last:mb-0">
                        <h4 className="font-semibold text-gray-900">{cluster.cluster_name}</h4>
                        <p className="text-gray-600 text-sm">{cluster.cluster_description}</p>
                        {!selectedClusterId && (
                          <button
                            onClick={() => handleSelectCluster(cluster.cluster_id)}
                            disabled={submitting}
                            className="mt-3 bg-blue-600 text-white py-1 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-300 text-sm"
                          >
                            {t('step3.phase1.selectCluster')}
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Full ranking */}
                <div className="bg-white rounded-lg shadow">
                  <div className="px-4 py-3 border-b border-gray-200">
                    <h3 className="text-lg font-semibold text-gray-900">{t('step3.phase1.allRanked')}</h3>
                  </div>
                  <div className="divide-y divide-gray-100">
                    {clusterResults.ranked_clusters?.map((cluster) => (
                      <div key={cluster.cluster_id} className="px-4 py-3 flex items-center gap-4">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                          cluster.rank === 1 ? 'bg-yellow-400 text-yellow-900' : 'bg-gray-200 text-gray-700'
                        }`}>
                          #{cluster.rank}
                        </div>
                        <div className="flex-1">
                          <h4 className="font-medium text-gray-900">{cluster.cluster_name}</h4>
                          <p className="text-sm text-gray-500">{cluster.idea_count} {t('step3.phase1.ideas')}</p>
                        </div>
                        <div className="text-right">
                          <span className="text-lg font-bold text-blue-600">{cluster.total_points}</span>
                          <p className="text-xs text-gray-500">{t('step3.results.points')}</p>
                        </div>
                        {!selectedClusterId && (
                          <button
                            onClick={() => handleSelectCluster(cluster.cluster_id)}
                            disabled={submitting}
                            className="bg-gray-100 text-gray-700 py-1 px-3 rounded-md hover:bg-gray-200 text-sm"
                          >
                            {t('step3.phase1.select')}
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Continue to Phase 2 button */}
                {selectedClusterId && (
                  <div className="mt-6 text-center">
                    <button
                      onClick={() => setActiveTab('ideas')}
                      className="bg-purple-600 text-white py-3 px-8 rounded-md hover:bg-purple-700 transition-colors font-medium"
                    >
                      {t('step3.phase1.continueToPhase2')}
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Phase 2: Idea Prioritization */}
        {activeTab === 'ideas' && selectedClusterId && (
          <div>
            {/* Selected cluster info */}
            {selectedCluster && (
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 mb-6">
                <h3 className="font-semibold text-purple-900">{t('step3.phase2.selectedCluster')}: {selectedCluster.name}</h3>
                <p className="text-purple-700 text-sm">{selectedCluster.description}</p>
              </div>
            )}

            {/* Explanation */}
            {!hasVotedIdeas && (
              <ExplanationBox
                title={t('step3.phase2.explanation.title')}
                description={t('step3.phase2.explanation.description')}
                bullets={[
                  t('step3.phase2.explanation.bullet1'),
                  t('step3.phase2.explanation.bullet2'),
                  t('step3.phase2.explanation.bullet3'),
                ]}
                tip={t('step3.phase2.explanation.tip')}
                variant="purple"
                defaultOpen={true}
              />
            )}

            {/* Idea Voting */}
            {!hasVotedIdeas && (
              <>
                {/* Points indicator */}
                <div className="bg-white rounded-lg shadow p-4 mb-6 sticky top-4 z-10">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-lg font-semibold text-gray-900">
                        {t('step3.voting.pointsRemaining')} <span className={remainingIdeaPoints === 0 ? 'text-green-600' : 'text-purple-600'}>{remainingIdeaPoints}</span> / {totalPoints}
                      </p>
                      <p className="text-sm text-gray-600">{t('step3.phase2.voteHint')}</p>
                    </div>
                    <button
                      onClick={handleSubmitIdeaVotes}
                      disabled={remainingIdeaPoints !== 0 || submitting}
                      className="bg-green-600 text-white py-2 px-6 rounded-md hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium"
                    >
                      {submitting ? t('step3.voting.submitting') : t('step3.voting.submitVotes')}
                    </button>
                  </div>
                </div>

                {/* Ideas list */}
                <div className="space-y-4">
                  {clusterIdeas.map((idea) => (
                    <div
                      key={idea.id}
                      className={`bg-white rounded-lg shadow p-4 border-2 transition-colors ${
                        ideaVotes[idea.id] ? 'border-purple-400 bg-purple-50' : 'border-transparent'
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
                            onClick={() => handleRemoveIdeaPoint(idea.id)}
                            disabled={!ideaVotes[idea.id]}
                            className="w-8 h-8 rounded-full bg-gray-200 text-gray-700 hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center font-bold"
                          >
                            -
                          </button>
                          <span className="w-8 text-center text-lg font-bold text-purple-600">
                            {ideaVotes[idea.id] || 0}
                          </span>
                          <button
                            onClick={() => handleAddIdeaPoint(idea.id)}
                            disabled={remainingIdeaPoints <= 0}
                            className="w-8 h-8 rounded-full bg-purple-600 text-white hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center font-bold"
                          >
                            +
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}

            {/* Idea Results */}
            {hasVotedIdeas && ideaResults && (
              <>
                <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-6">
                  <p className="text-green-800 font-medium">{t('step3.results.votesRecorded')}</p>
                </div>

                {/* Top idea(s) */}
                {ideaResults.top_ideas?.length > 0 && (
                  <div className="bg-yellow-50 border-2 border-yellow-400 rounded-lg p-6 mb-6">
                    <h3 className="text-lg font-bold text-yellow-800 mb-3">
                      {ideaResults.top_ideas.length > 1 ? t('step3.results.topIdeas') : t('step3.results.topIdea')}
                      {' '}({ideaResults.top_ideas[0].total_points} {t('step3.results.points')})
                    </h3>
                    {ideaResults.top_ideas.map((idea) => (
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
                    {ideaResults.ranked_ideas?.map((idea) => (
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
                          <span className="text-lg font-bold text-purple-600">{idea.total_points}</span>
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
          </div>
        )}
      </div>

      {/* Test Mode Panel */}
      {testModeEnabled && clusters.length > 0 && (
        <Step3TestModePanel
          sessionUuid={sessionUuid}
          activeTab={activeTab}
          onVotesGenerated={handleTestModeVotes}
          hasVoted={activeTab === 'clusters' ? hasVotedClusters : hasVotedIdeas}
          disabled={submitting}
        />
      )}
    </div>
  );
};

export default Step3Page;
