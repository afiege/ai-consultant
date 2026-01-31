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
      <span className="bg-blue-100 text-blue-800 text-xs font-medium mr-2 px-2 py-0.5 rounded">
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

const CostEstimationFindingsSidebar = ({ findings }) => {
  const { t } = useTranslation();

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
        <h3 className="font-semibold text-blue-800 text-sm">
          {t('step5.costsFindings.title')}
        </h3>
        <p className="text-xs text-blue-600 mt-1">{t('step5.costsFindings.subtitle')}</p>
      </div>

      {/* Complexity */}
      <FindingCard
        number="1"
        title={t('step5.costsFindings.complexity')}
        content={findings?.complexity}
        placeholder={t('step5.costsFindings.complexityPlaceholder')}
      />

      {/* Initial Investment */}
      <FindingCard
        number="2"
        title={t('step5.costsFindings.initialInvestment')}
        content={findings?.initial_investment}
        placeholder={t('step5.costsFindings.initialPlaceholder')}
      />

      {/* Recurring Costs */}
      <FindingCard
        number="3"
        title={t('step5.costsFindings.recurring')}
        content={findings?.recurring_costs}
        placeholder={t('step5.costsFindings.recurringPlaceholder')}
      />

      {/* TCO */}
      <FindingCard
        number="4"
        title={t('step5.costsFindings.tco')}
        content={findings?.tco}
        placeholder={t('step5.costsFindings.tcoPlaceholder')}
        highlight={true}
      />

      {/* ROI Analysis */}
      <FindingCard
        number="5"
        title={t('step5.costsFindings.roi')}
        content={findings?.roi_analysis}
        placeholder={t('step5.costsFindings.roiPlaceholder')}
      />

      {/* Cost Drivers */}
      <FindingCard
        number="6"
        title={t('step5.costsFindings.drivers')}
        content={findings?.cost_drivers}
        placeholder={t('step5.costsFindings.driversPlaceholder')}
      />

      {/* Optimization */}
      <FindingCard
        number="7"
        title={t('step5.costsFindings.optimization')}
        content={findings?.optimization}
        placeholder={t('step5.costsFindings.optimizationPlaceholder')}
      />
    </div>
  );
};

export default CostEstimationFindingsSidebar;
