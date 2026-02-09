import React from 'react';
import { WikiLinkMarkdown, RelatedSections } from '../common/WikiLinkMarkdown';
import { GenerateButton } from './SharedWidgets';

export const SwotTab = ({ findings, t, onNavigate, onGenerate, loading, error, crossReferences }) => {
  const swot = findings?.analysis?.swot_analysis;

  return (
    <div className="space-y-6">
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-md">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {!swot ? (
        <div className="text-center py-8">
          <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
          </svg>
          <p className="text-gray-600 mb-4">{t('step6.swot.notGenerated')}</p>
          <GenerateButton onClick={onGenerate} loading={loading} colorClass="bg-amber-600 hover:bg-amber-700">
            {loading ? t('step6.swot.generating') : t('step6.swot.generateButton')}
          </GenerateButton>
          <p className="text-xs text-gray-500 mt-3">{t('step6.swot.generateNote')}</p>
        </div>
      ) : (
        <div>
          <div className="flex justify-end mb-4">
            <button
              onClick={onGenerate}
              disabled={loading}
              className="text-sm text-amber-600 hover:text-amber-800 disabled:text-gray-400"
            >
              {loading ? t('step6.swot.regenerating') : t('step6.swot.regenerateButton')}
            </button>
          </div>
          <div className="bg-amber-50 rounded-lg p-6">
            <WikiLinkMarkdown
              content={swot.text}
              onNavigate={onNavigate}
              className="text-amber-800"
              crossReferences={crossReferences?.['swot_analysis'] || []}
            />
            <RelatedSections crossReferences={crossReferences?.['swot_analysis'] || []} onNavigate={onNavigate} />
          </div>
        </div>
      )}
    </div>
  );
};

export const BriefingTab = ({ findings, t, onNavigate, onGenerate, loading, error, crossReferences }) => {
  const briefing = findings?.analysis?.technical_briefing;

  return (
    <div className="space-y-6">
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-md">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {!briefing ? (
        <div className="text-center py-8">
          <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p className="text-gray-600 mb-4">{t('step6.briefing.notGenerated')}</p>
          <GenerateButton onClick={onGenerate} loading={loading} colorClass="bg-indigo-600 hover:bg-indigo-700">
            {loading ? t('step6.briefing.generating') : t('step6.briefing.generateButton')}
          </GenerateButton>
          <p className="text-xs text-gray-500 mt-3">{t('step6.briefing.generateNote')}</p>
        </div>
      ) : (
        <div>
          <div className="flex justify-end mb-4">
            <button
              onClick={onGenerate}
              disabled={loading}
              className="text-sm text-indigo-600 hover:text-indigo-800 disabled:text-gray-400"
            >
              {loading ? t('step6.briefing.regenerating') : t('step6.briefing.regenerateButton')}
            </button>
          </div>
          <div className="bg-indigo-50 rounded-lg p-6">
            <WikiLinkMarkdown
              content={briefing.text}
              onNavigate={onNavigate}
              className="text-indigo-800"
              crossReferences={crossReferences?.['technical_briefing'] || []}
            />
            <RelatedSections crossReferences={crossReferences?.['technical_briefing'] || []} onNavigate={onNavigate} />
          </div>
        </div>
      )}
    </div>
  );
};
