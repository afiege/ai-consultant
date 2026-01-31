import React from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const markdownComponents = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="list-disc ml-4 mb-2">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal ml-4 mb-2">{children}</ol>,
  li: ({ children }) => <li className="mb-1">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  table: ({ children }) => (
    <div className="overflow-x-auto my-2">
      <table className="min-w-full border border-gray-300 text-xs">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-gray-100">{children}</thead>,
  tbody: ({ children }) => <tbody>{children}</tbody>,
  tr: ({ children }) => <tr className="border-b border-gray-200">{children}</tr>,
  th: ({ children }) => (
    <th className="px-2 py-1 text-left font-semibold border-r border-gray-200 last:border-r-0">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-2 py-1 border-r border-gray-200 last:border-r-0">{children}</td>
  ),
};

const FindingCard = ({ number, title, content, placeholder, highlight = false }) => (
  <div className="bg-white rounded-lg shadow p-4">
    <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
      <span className="bg-green-100 text-green-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">
        {number}
      </span>
      {title}
    </h3>
    {content ? (
      <div className={`text-sm text-gray-700 prose prose-sm max-w-none ${highlight ? 'font-medium' : ''}`}>
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
          {content}
        </ReactMarkdown>
      </div>
    ) : (
      <p className="text-sm text-gray-400 italic">{placeholder}</p>
    )}
  </div>
);

const BusinessCaseFindingsSidebar = ({ findings }) => {
  const { t } = useTranslation();

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-green-50 border border-green-200 rounded-lg p-3">
        <h3 className="font-semibold text-green-800 text-sm">
          {t('step5.findings.title')}
        </h3>
        <p className="text-xs text-green-600 mt-1">{t('step5.findings.subtitle')}</p>
      </div>

      {/* Classification */}
      <FindingCard
        number="1"
        title={t('step5.findings.classification')}
        content={findings?.classification}
        placeholder={t('step5.findings.classificationPlaceholder')}
      />

      {/* Calculation */}
      <FindingCard
        number="2"
        title={t('step5.findings.calculation')}
        content={findings?.calculation}
        placeholder={t('step5.findings.calculationPlaceholder')}
      />

      {/* Validation Questions */}
      <FindingCard
        number="3"
        title={t('step5.findings.validationQuestions')}
        content={findings?.validation_questions}
        placeholder={t('step5.findings.validationPlaceholder')}
      />

      {/* Management Pitch */}
      <FindingCard
        number="4"
        title={t('step5.findings.managementPitch')}
        content={findings?.management_pitch}
        placeholder={t('step5.findings.managementPitchPlaceholder')}
        highlight={true}
      />

      {/* 5-Level Framework Reference */}
      <div className="bg-gray-50 rounded-lg p-3">
        <h4 className="text-xs font-semibold text-gray-700 mb-2">
          {t('step5.framework.title')}
        </h4>
        <div className="text-xs text-gray-600 space-y-1">
          <p><span className="font-medium">1.</span> {t('step5.framework.level1')}</p>
          <p><span className="font-medium">2.</span> {t('step5.framework.level2')}</p>
          <p><span className="font-medium">3.</span> {t('step5.framework.level3')}</p>
          <p><span className="font-medium">4.</span> {t('step5.framework.level4')}</p>
          <p><span className="font-medium">5.</span> {t('step5.framework.level5')}</p>
        </div>
      </div>
    </div>
  );
};

export default BusinessCaseFindingsSidebar;
