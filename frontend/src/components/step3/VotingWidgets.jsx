import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';

/** Renders markdown content for an idea with compact styling. */
export const IdeaMarkdown = ({ content, className = '' }) => (
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

/** Badge showing maturity level (high/medium/low) with tooltip rationale. */
export const MaturityBadge = ({ level, rationale }) => {
  const [showTooltip, setShowTooltip] = useState(false);
  const { t } = useTranslation();

  if (!level) return null;

  const badgeConfig = {
    high: { bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-300', icon: '✓', label: t('step3.maturity.high', 'Well-suited') },
    medium: { bg: 'bg-yellow-100', text: 'text-yellow-800', border: 'border-yellow-300', icon: '○', label: t('step3.maturity.medium', 'Moderate effort') },
    low: { bg: 'bg-red-100', text: 'text-red-800', border: 'border-red-300', icon: '△', label: t('step3.maturity.low', 'Ambitious') },
  };

  const config = badgeConfig[level] || badgeConfig.medium;

  return (
    <div className="relative inline-block">
      <span
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border cursor-help ${config.bg} ${config.text} ${config.border}`}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        <span>{config.icon}</span>
        <span>{config.label}</span>
      </span>
      {showTooltip && rationale && (
        <div className="absolute z-20 bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-64 p-3 bg-gray-900 text-white text-xs rounded-lg shadow-lg">
          <div className="font-medium mb-1">{t('step3.maturity.tooltip', 'Maturity Assessment')}</div>
          <div className="text-gray-300">{rationale}</div>
          <div className="absolute top-full left-1/2 transform -translate-x-1/2 -mt-1">
            <div className="border-4 border-transparent border-t-gray-900"></div>
          </div>
        </div>
      )}
    </div>
  );
};

/** Visual dot indicator showing current / total points. */
export const PointsIndicator = ({ current, total, color = 'blue' }) => {
  const colorClasses = {
    blue: { filled: 'bg-blue-500', empty: 'bg-gray-300' },
    purple: { filled: 'bg-purple-500', empty: 'bg-gray-300' },
    green: { filled: 'bg-green-500', empty: 'bg-gray-300' },
  };
  const colors = colorClasses[color] || colorClasses.blue;

  return (
    <div className="flex items-center gap-1.5">
      {Array.from({ length: total }).map((_, index) => (
        <div
          key={index}
          className={`w-3 h-3 rounded-full transition-colors ${index < current ? colors.filled : colors.empty}`}
        />
      ))}
    </div>
  );
};

/** Horizontal progress bar showing vote distribution. */
export const VoteDistributionBar = ({ points, maxPoints, color = 'blue', isTop = false }) => {
  const percentage = maxPoints > 0 ? (points / maxPoints) * 100 : 0;
  const colorClasses = {
    blue: isTop ? 'bg-gradient-to-r from-yellow-400 to-yellow-500' : 'bg-blue-500',
    purple: isTop ? 'bg-gradient-to-r from-yellow-400 to-yellow-500' : 'bg-purple-500',
  };

  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${colorClasses[color] || colorClasses.blue}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className={`text-sm font-semibold min-w-[24px] text-right ${isTop ? 'text-yellow-600' : color === 'purple' ? 'text-purple-600' : 'text-blue-600'}`}>
        {points}
      </span>
    </div>
  );
};

/** Small badge overlay showing vote count on a card. */
export const VoteBadge = ({ votes, color = 'blue' }) => {
  if (votes === 0) return null;
  const colorClasses = {
    blue: 'bg-blue-600 text-white',
    purple: 'bg-purple-600 text-white',
  };
  return (
    <div className={`absolute -top-2 -right-2 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shadow-md ${colorClasses[color] || colorClasses.blue}`}>
      {votes}
    </div>
  );
};
