import React from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';

const FindingCard = ({ number, title, content, placeholder }) => (
  <div className="bg-white rounded-lg shadow p-4">
    <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
      <span className="bg-blue-100 text-blue-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">
        {number}
      </span>
      {title}
    </h3>
    {content ? (
      <div className="text-sm text-gray-700 prose prose-sm max-w-none">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    ) : (
      <p className="text-sm text-gray-400 italic">{placeholder}</p>
    )}
  </div>
);

const CrispDmFindingsSidebar = ({ findings, ideas = [] }) => {
  const { t } = useTranslation();
  const safeIdeas = ideas || [];

  return (
    <div className="space-y-4">
      {/* CRISP-DM Header */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
        <h3 className="font-semibold text-blue-800 text-sm">
          {t('step4.findings.crispDmTitle')}
        </h3>
        <p className="text-xs text-blue-600 mt-1">
          {t('step4.findings.crispDmSubtitle')}
        </p>
      </div>

      {/* 1. Business Objectives */}
      <FindingCard
        number="1"
        title={t('step4.findings.businessObjectives')}
        content={findings?.business_objectives}
        placeholder={t('step4.findings.businessObjectivesPlaceholder')}
      />

      {/* 2. Situation Assessment */}
      <FindingCard
        number="2"
        title={t('step4.findings.situationAssessment')}
        content={findings?.situation_assessment}
        placeholder={t('step4.findings.situationPlaceholder')}
      />

      {/* 3. AI/Data Mining Goals */}
      <FindingCard
        number="3"
        title={t('step4.findings.aiGoals')}
        content={findings?.ai_goals}
        placeholder={t('step4.findings.aiGoalsPlaceholder')}
      />

      {/* 4. Project Plan */}
      <FindingCard
        number="4"
        title={t('step4.findings.projectPlan')}
        content={findings?.project_plan}
        placeholder={t('step4.findings.projectPlanPlaceholder')}
      />

      {/* Ideas summary */}
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="font-semibold text-gray-900 mb-2">
          {t('step4.findings.ideas')} ({safeIdeas.length})
        </h3>
        <div className="space-y-1 max-h-40 overflow-y-auto">
          {safeIdeas.slice(0, 5).map((idea) => (
            <p key={idea.id} className="text-xs text-gray-600 truncate">
              - {idea.content}
            </p>
          ))}
          {safeIdeas.length > 5 && (
            <p className="text-xs text-gray-400">
              {t('step4.findings.moreIdeas', { count: safeIdeas.length - 5 })}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default CrispDmFindingsSidebar;
