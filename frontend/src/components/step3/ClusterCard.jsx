import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getCardColorClasses } from './helpers';
import { VoteBadge, MaturityBadge, PointsIndicator, IdeaMarkdown } from './VotingWidgets';

/** Expandable card for a single cluster with voting controls. */
const ClusterCard = ({ cluster, votes, totalPoints, onAddPoint, onRemovePoint, canAddPoint, forceExpanded = false }) => {
  const [localExpanded, setLocalExpanded] = useState(false);
  const { t } = useTranslation();

  const expanded = forceExpanded || localExpanded;
  const hasIdeas = cluster.ideas && cluster.ideas.length > 0;
  const ideaCount = cluster.idea_ids?.length || cluster.ideas?.length || 0;

  return (
    <div className={`relative rounded-lg shadow border-2 transition-all duration-200 ${getCardColorClasses(votes, 'blue')}`}>
      <VoteBadge votes={votes} color="blue" />
      <div className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-semibold text-gray-900 text-lg">{cluster.name}</h3>
              <MaturityBadge level={cluster.maturity_appropriateness} rationale={cluster.maturity_rationale} />
            </div>
            <p className="text-gray-600 mt-1">{cluster.description}</p>
            <div className="flex items-center gap-3 mt-3">
              {ideaCount > 0 && (
                <button onClick={() => setLocalExpanded(!localExpanded)}
                  className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${expanded ? 'bg-blue-100 text-blue-700 hover:bg-blue-200' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}>
                  <svg className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                  {expanded ? t('step3.phase1.hideIdeas', 'Hide ideas') : t('step3.phase1.showIdeas', 'Show ideas')}
                  <span className="bg-white px-1.5 py-0.5 rounded-full text-xs">{ideaCount}</span>
                </button>
              )}
            </div>
          </div>
          <div className="flex flex-col items-center gap-2">
            <div className="flex items-center gap-2">
              <button onClick={onRemovePoint} disabled={votes === 0}
                className="w-10 h-10 rounded-full bg-gray-200 text-gray-700 hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center font-bold transition-colors"
                aria-label="Remove point">-</button>
              <div className="w-12 flex justify-center">
                <PointsIndicator current={votes} total={totalPoints} color="blue" />
              </div>
              <button onClick={onAddPoint} disabled={!canAddPoint}
                className="w-10 h-10 rounded-full bg-blue-600 text-white hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center font-bold transition-colors"
                aria-label="Add point">+</button>
            </div>
            {votes > 0 && (
              <span className="text-xs text-blue-600 font-medium">
                {votes} {votes === 1 ? t('step3.voting.point', 'point') : t('step3.voting.points', 'points')}
              </span>
            )}
          </div>
        </div>
      </div>
      {expanded && ideaCount > 0 && (
        <div className="border-t border-gray-200 bg-gray-50 p-4">
          <p className="text-xs text-gray-500 mb-3 font-medium uppercase tracking-wide">
            {t('step3.phase1.ideasInCluster', 'Ideas in this cluster')} ({ideaCount})
          </p>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {cluster.ideas && cluster.ideas.length > 0 ? (
              cluster.ideas.map((idea, index) => (
                <div key={idea.id || index} className="bg-white rounded-md p-3 border border-gray-200 shadow-sm">
                  <div className="flex items-start gap-2">
                    <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-xs font-medium">{index + 1}</span>
                    <IdeaMarkdown content={idea.content} className="text-sm text-gray-700 flex-1" />
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm text-gray-500 italic">{t('step3.phase1.noIdeaDetails', 'Idea details not available')}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default ClusterCard;
