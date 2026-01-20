import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';

const IdeaSheet = ({ sheetData, onSubmit, submitting }) => {
  const { t } = useTranslation();
  const [ideas, setIdeas] = useState(['', '', '']);

  useEffect(() => {
    // Reset ideas when sheet changes
    setIdeas(['', '', '']);
  }, [sheetData?.sheet_id]);

  const handleIdeaChange = (index, value) => {
    const newIdeas = [...ideas];
    newIdeas[index] = value;
    setIdeas(newIdeas);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (ideas.every(idea => idea.trim())) {
      onSubmit(ideas);
    }
  };

  const allIdeasFilled = ideas.every(idea => idea.trim());

  // Group ideas by round
  const ideaByRound = {};
  if (sheetData?.all_ideas) {
    sheetData.all_ideas.forEach(idea => {
      if (!ideaByRound[idea.round_number]) {
        ideaByRound[idea.round_number] = [];
      }
      ideaByRound[idea.round_number].push(idea);
    });
  }

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-bold text-gray-900">
            {t('step2.ideaSheet.sheetNumber', { number: sheetData?.sheet_number || '?' })}
          </h3>
          <div className="text-sm text-gray-600">
            {t('step2.ideaSheet.roundOf', { current: sheetData?.current_round || 1, total: 6 })}
          </div>
        </div>

        {/* Previous Ideas */}
        {Object.keys(ideaByRound).length > 0 && sheetData.current_round > 1 && (
          <div className="mb-6 space-y-4">
            <h4 className="font-semibold text-gray-900">{t('step2.ideaSheet.previousIdeas')}</h4>
            {Object.keys(ideaByRound)
              .filter(round => parseInt(round) < sheetData.current_round)
              .sort((a, b) => parseInt(a) - parseInt(b))
              .map(round => (
                <div key={round} className="border-l-4 border-blue-500 pl-4">
                  <p className="text-xs font-medium text-gray-500 mb-2">
                    {t('step2.ideaSheet.roundLabel', { number: round })}
                  </p>
                  <div className="space-y-2">
                    {ideaByRound[round].map((idea, idx) => (
                      <div key={idx} className="bg-gray-50 p-3 rounded">
                        <div className="flex items-start justify-between">
                          <div className="text-sm text-gray-700 prose prose-sm max-w-none">
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
                              {idea.content}
                            </ReactMarkdown>
                          </div>
                          <span className="text-xs text-gray-500 ml-2 whitespace-nowrap">
                            {idea.participant_name}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
          </div>
        )}

        {/* Current Round - Input Fields */}
        {!sheetData?.has_submitted_current_round ? (
          <form onSubmit={handleSubmit}>
            <h4 className="font-semibold text-gray-900 mb-3">
              {t('step2.ideaSheet.yourIdeasFor', { round: sheetData?.current_round || 1 })}
            </h4>
            <div className="space-y-4">
              {ideas.map((idea, index) => (
                <div key={index}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('step2.ideaSheet.idea', { number: index + 1 })}
                  </label>
                  <textarea
                    value={idea}
                    onChange={(e) => handleIdeaChange(index, e.target.value)}
                    placeholder={t('step2.ideaSheet.ideaPlaceholder')}
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    disabled={submitting}
                  />
                </div>
              ))}
            </div>

            <button
              type="submit"
              disabled={!allIdeasFilled || submitting}
              className="mt-6 w-full bg-blue-600 text-white py-3 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {submitting ? t('step2.ideaSheet.submitting') : t('step2.ideaSheet.submitIdeas')}
            </button>
          </form>
        ) : (
          <div className="bg-green-50 border border-green-200 rounded-md p-4">
            <p className="text-green-800 font-medium">
              ✓ {t('step2.ideaSheet.submittedMessage')}
            </p>
            <p className="text-sm text-green-700 mt-1">
              {t('step2.ideaSheet.waitingForOthers')}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default IdeaSheet;
