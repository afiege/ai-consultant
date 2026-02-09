import React from 'react';
import { EmptyState } from './SharedWidgets';

export const IdeasTab = ({ findings, t }) => {
  const brainstorming = findings?.brainstorming;

  if (!brainstorming?.sheets?.length) {
    return <EmptyState message={t('step6.incomplete.ideas')} />;
  }

  const allIdeas = [];
  brainstorming.sheets.forEach(sheet => {
    sheet.ideas.forEach(idea => {
      allIdeas.push(idea);
    });
  });

  const ideasByRound = {};
  allIdeas.forEach(idea => {
    const round = idea.round_number || 1;
    if (!ideasByRound[round]) {
      ideasByRound[round] = [];
    }
    ideasByRound[round].push(idea);
  });

  const sortedRounds = Object.keys(ideasByRound).sort((a, b) => a - b);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">{t('step6.ideas.title')}</h3>
        <span className="text-sm text-gray-500">
          {brainstorming.total_ideas} {t('step6.ideas.totalIdeas')}
        </span>
      </div>

      {sortedRounds.map(round => (
        <div key={round} className="bg-yellow-50 rounded-lg p-4">
          <h4 className="font-medium text-yellow-800 mb-3">
            Round {round}
          </h4>
          <div className="space-y-2">
            {ideasByRound[round].map((idea) => (
              <div key={idea.id} className="flex items-start gap-3 bg-white/50 rounded p-2">
                <p className="text-sm text-gray-700 flex-1">{idea.content}</p>
                {idea.participant_name && (
                  <span className="text-xs text-yellow-600 whitespace-nowrap">
                    {idea.participant_name}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};

export const PrioritizationTab = ({ findings, t }) => {
  const prioritization = findings?.prioritization;

  if (!prioritization?.results?.length) {
    return <EmptyState message={t('step6.incomplete.prioritization')} />;
  }

  const ideaScores = {};
  prioritization.results.forEach(vote => {
    if (!vote.idea_id) return;
    if (!ideaScores[vote.idea_id]) {
      ideaScores[vote.idea_id] = {
        idea_content: vote.idea_content,
        votes: [],
        totalScore: 0,
        voteCount: 0
      };
    }
    ideaScores[vote.idea_id].votes.push(vote);
    ideaScores[vote.idea_id].totalScore += vote.score || 0;
    ideaScores[vote.idea_id].voteCount += 1;
  });

  const sortedIdeas = Object.entries(ideaScores)
    .sort((a, b) => b[1].totalScore - a[1].totalScore);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">{t('step6.prioritization.title')}</h3>
        <span className="text-sm text-gray-500">
          {prioritization.total_votes} {t('step6.prioritization.totalVotes')}
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-purple-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-purple-700 uppercase tracking-wider">
                {t('step6.prioritization.rank')}
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-purple-700 uppercase tracking-wider">
                {t('step6.prioritization.idea')}
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium text-purple-700 uppercase tracking-wider">
                {t('step6.prioritization.total')}
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {sortedIdeas.map(([ideaId, data], index) => (
              <tr key={ideaId} className={index === 0 ? 'bg-purple-50' : ''}>
                <td className="px-4 py-3 whitespace-nowrap">
                  <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${
                    index === 0 ? 'bg-purple-600 text-white' : 'bg-gray-200 text-gray-600'
                  }`}>
                    {index + 1}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-gray-900">
                  {data.idea_content}
                  <span className="text-xs text-gray-400 ml-2">({data.voteCount} votes)</span>
                </td>
                <td className="px-4 py-3 text-center text-sm font-semibold text-purple-700">
                  {data.totalScore}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export const TranscriptsTab = ({ findings, t }) => {
  const transcripts = findings?.transcripts;
  const [activeTranscript, setActiveTranscript] = React.useState('consultation');

  const hasConsultation = transcripts?.consultation?.length > 0;
  const hasBusinessCase = transcripts?.business_case?.length > 0;
  const hasCostEstimation = transcripts?.cost_estimation?.length > 0;

  if (!hasConsultation && !hasBusinessCase && !hasCostEstimation) {
    return <EmptyState message={t('step6.incomplete.transcripts')} />;
  }

  const transcriptOptions = [
    { id: 'consultation', label: t('step6.transcripts.consultation'), has: hasConsultation },
    { id: 'business_case', label: t('step6.transcripts.businessCase'), has: hasBusinessCase },
    { id: 'cost_estimation', label: t('step6.transcripts.costEstimation'), has: hasCostEstimation },
  ].filter(opt => opt.has);

  const currentMessages = transcripts?.[activeTranscript] || [];

  return (
    <div className="space-y-4">
      <div className="flex gap-2 border-b border-gray-200 pb-3">
        {transcriptOptions.map(opt => (
          <button
            key={opt.id}
            onClick={() => setActiveTranscript(opt.id)}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
              activeTranscript === opt.id
                ? 'bg-gray-800 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <div className="space-y-3 max-h-[600px] overflow-y-auto">
        {currentMessages.map((msg, index) => (
          <div
            key={index}
            className={`p-3 rounded-lg ${
              msg.role === 'user'
                ? 'bg-blue-50 ml-8'
                : msg.role === 'assistant'
                ? 'bg-gray-50 mr-8'
                : 'bg-yellow-50'
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-xs font-medium ${
                msg.role === 'user' ? 'text-blue-600' : 'text-gray-600'
              }`}>
                {msg.role === 'user' ? t('step6.transcripts.user') : t('step6.transcripts.assistant')}
              </span>
              {msg.created_at && (
                <span className="text-xs text-gray-400">
                  {new Date(msg.created_at).toLocaleString()}
                </span>
              )}
            </div>
            <p className="text-sm text-gray-700 whitespace-pre-wrap">{msg.content}</p>
          </div>
        ))}
      </div>
    </div>
  );
};
