import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, ReferenceLine, ReferenceArea, Label } from 'recharts';
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

// Maturity badge component with tooltip
const MaturityBadge = ({ level, rationale }) => {
  const [showTooltip, setShowTooltip] = useState(false);
  const { t } = useTranslation();

  if (!level) return null;

  const badgeConfig = {
    high: {
      bg: 'bg-green-100',
      text: 'text-green-800',
      border: 'border-green-300',
      icon: '✓',
      label: t('step3.maturity.high', 'Well-suited')
    },
    medium: {
      bg: 'bg-yellow-100',
      text: 'text-yellow-800',
      border: 'border-yellow-300',
      icon: '○',
      label: t('step3.maturity.medium', 'Moderate effort')
    },
    low: {
      bg: 'bg-red-100',
      text: 'text-red-800',
      border: 'border-red-300',
      icon: '△',
      label: t('step3.maturity.low', 'Ambitious')
    }
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

// Visual points indicator - shows dots instead of numbers
const PointsIndicator = ({ current, total, color = 'blue' }) => {
  const colorClasses = {
    blue: { filled: 'bg-blue-500', empty: 'bg-gray-300' },
    purple: { filled: 'bg-purple-500', empty: 'bg-gray-300' },
    green: { filled: 'bg-green-500', empty: 'bg-gray-300' }
  };

  const colors = colorClasses[color] || colorClasses.blue;

  return (
    <div className="flex items-center gap-1.5">
      {Array.from({ length: total }).map((_, index) => (
        <div
          key={index}
          className={`w-3 h-3 rounded-full transition-colors ${
            index < current ? colors.filled : colors.empty
          }`}
        />
      ))}
    </div>
  );
};

// Vote distribution bar - horizontal progress bar for results
const VoteDistributionBar = ({ points, maxPoints, color = 'blue', isTop = false }) => {
  const percentage = maxPoints > 0 ? (points / maxPoints) * 100 : 0;

  const colorClasses = {
    blue: isTop ? 'bg-gradient-to-r from-yellow-400 to-yellow-500' : 'bg-blue-500',
    purple: isTop ? 'bg-gradient-to-r from-yellow-400 to-yellow-500' : 'bg-purple-500'
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

// Truncated text with tooltip on hover
const TruncatedText = ({ text, maxLength = 80, className = '' }) => {
  const [showTooltip, setShowTooltip] = useState(false);
  const isTruncated = text && text.length > maxLength;
  const displayText = isTruncated ? text.slice(0, maxLength) + '...' : text;

  if (!isTruncated) {
    return <span className={className}>{text}</span>;
  }

  return (
    <span className="relative inline-block">
      <span
        className={`cursor-help ${className}`}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        {displayText}
      </span>
      {showTooltip && (
        <div className="absolute z-30 bottom-full left-0 mb-2 w-72 p-3 bg-gray-900 text-white text-sm rounded-lg shadow-lg">
          {text}
          <div className="absolute top-full left-4 -mt-1">
            <div className="border-4 border-transparent border-t-gray-900"></div>
          </div>
        </div>
      )}
    </span>
  );
};

// Vote count badge overlay
const VoteBadge = ({ votes, color = 'blue' }) => {
  if (votes === 0) return null;

  const colorClasses = {
    blue: 'bg-blue-600 text-white',
    purple: 'bg-purple-600 text-white'
  };

  return (
    <div className={`absolute -top-2 -right-2 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shadow-md ${colorClasses[color] || colorClasses.blue}`}>
      {votes}
    </div>
  );
};

// Helper function to get card color classes based on vote count
const getCardColorClasses = (votes, baseColor = 'blue') => {
  if (baseColor === 'blue') {
    if (votes === 0) return 'border-transparent bg-white hover:border-gray-200';
    if (votes === 1) return 'border-blue-300 bg-blue-50';
    return 'border-blue-500 bg-blue-100'; // 2+ votes
  } else {
    if (votes === 0) return 'border-transparent bg-white hover:border-gray-200';
    if (votes === 1) return 'border-purple-300 bg-purple-50';
    return 'border-purple-500 bg-purple-100'; // 2+ votes
  }
};

// Convert low/medium/high to numeric values for scatter plot
const levelToNumber = (level) => {
  const mapping = { low: 1, medium: 2, high: 3 };
  return mapping[level] || 2;
};

// Enhanced maturity style with accessible colors and icons
const getMaturityStyle = (level) => {
  const styles = {
    high: {
      fill: '#16a34a',      // green-600 (darker for better contrast)
      fillHover: '#15803d', // green-700
      icon: '✓',
      label: 'Well-suited'
    },
    medium: {
      fill: '#ca8a04',      // yellow-600 (darker for accessibility)
      fillHover: '#a16207', // yellow-700
      icon: '◐',
      label: 'Moderate'
    },
    low: {
      fill: '#dc2626',      // red-600
      fillHover: '#b91c1c', // red-700
      icon: '!',
      label: 'Ambitious'
    }
  };
  return styles[level] || styles.medium;
};

// Enhanced tooltip for scatter plot
const ScatterTooltip = ({ active, payload }) => {
  const { t } = useTranslation();
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    const maturityStyle = getMaturityStyle(data.maturity_appropriateness);

    return (
      <div
        className="bg-white rounded-xl shadow-2xl border-2 p-4 max-w-xs relative overflow-hidden"
        style={{ borderColor: maturityStyle.fill }}
      >
        {/* Color accent bar at top */}
        <div
          className="absolute top-0 left-0 right-0 h-1.5"
          style={{ backgroundColor: maturityStyle.fill }}
        />

        <p className="font-bold text-gray-900 text-base pt-1 mb-2">{data.name}</p>

        {data.description && (
          <p className="text-sm text-gray-600 mb-3 leading-relaxed">{data.description}</p>
        )}

        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-2">
            <span className="text-gray-500 font-medium min-w-[90px]">{t('step3.scatter.impact', 'Impact')}:</span>
            <span className="font-semibold text-gray-900 capitalize">{data.business_impact}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-gray-500 font-medium min-w-[90px]">{t('step3.scatter.effort', 'Effort')}:</span>
            <span className="font-semibold text-gray-900 capitalize">{data.implementation_effort}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-gray-500 font-medium min-w-[90px]">{t('step3.scatter.maturity', 'Maturity fit')}:</span>
            <span
              className="font-semibold capitalize px-2 py-0.5 rounded-full text-white text-xs inline-flex items-center gap-1"
              style={{ backgroundColor: maturityStyle.fill }}
            >
              <span>{maturityStyle.icon}</span>
              <span>{data.maturity_appropriateness}</span>
            </span>
          </div>
        </div>

        {data.impact_rationale && (
          <p className="text-xs text-gray-500 italic mt-3 pt-3 border-t border-gray-100">
            "{data.impact_rationale}"
          </p>
        )}

        {/* Click to vote indicator */}
        <div className="mt-3 pt-3 border-t border-gray-100 flex items-center gap-2 text-blue-600">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
          </svg>
          <span className="text-xs font-medium">{t('step3.scatter.clickToVote', 'Click to vote for this cluster')}</span>
        </div>
      </div>
    );
  }
  return null;
};

// Cluster scatter plot component - Impact vs Effort matrix with enhanced UX
const ClusterScatterPlot = ({ clusters, onClusterClick, selectedClusterId }) => {
  const { t } = useTranslation();
  const [hoveredId, setHoveredId] = useState(null);
  const [recentlyClicked, setRecentlyClicked] = useState(null);
  const [showVoteToast, setShowVoteToast] = useState(false);

  // Transform cluster data for scatter plot
  const scatterData = useMemo(() => {
    return clusters.map(cluster => ({
      ...cluster,
      x: levelToNumber(cluster.implementation_effort),
      y: levelToNumber(cluster.business_impact),
      // Add some jitter to prevent overlapping points
      xJitter: levelToNumber(cluster.implementation_effort) + (Math.random() - 0.5) * 0.3,
      yJitter: levelToNumber(cluster.business_impact) + (Math.random() - 0.5) * 0.3,
    }));
  }, [clusters]);

  // Check if we have effort/impact data
  const hasEffortImpactData = clusters.some(c => c.implementation_effort && c.business_impact);

  if (!hasEffortImpactData) {
    return null;
  }

  // Handle cluster click with animation feedback
  const handleClusterClick = (clusterId) => {
    setRecentlyClicked(clusterId);
    setShowVoteToast(true);
    setTimeout(() => setRecentlyClicked(null), 400);
    setTimeout(() => setShowVoteToast(false), 1500);
    onClusterClick && onClusterClick(clusterId);
  };

  // Responsive sizing for mobile touch targets (44px minimum)
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 640;
  const baseRadius = isMobile ? 18 : 14;
  const hoverRadius = isMobile ? 22 : 18;
  const clickRadius = isMobile ? 26 : 22;

  return (
    <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-5 mb-6 relative">
      {/* Vote toast notification */}
      {showVoteToast && (
        <div className="absolute top-4 right-4 bg-green-600 text-white px-4 py-2.5 rounded-lg shadow-xl flex items-center gap-2 z-50 animate-pulse">
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
          </svg>
          <span className="font-medium text-sm">{t('step3.scatter.voteAdded', 'Vote added!')}</span>
        </div>
      )}

      <h3 className="text-xl font-bold text-gray-900 mb-1">
        {t('step3.scatter.title', 'Cluster Prioritization Matrix')}
      </h3>
      <p className="text-sm text-gray-600 mb-5">
        {t('step3.scatter.subtitle', 'Click on clusters to vote. Colors indicate maturity fit.')}
      </p>

      {/* Enhanced Legend with icons for colorblind accessibility */}
      <div className="flex flex-wrap gap-4 mb-5 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded-full bg-green-600 flex items-center justify-center">
            <span className="text-[10px] text-white font-bold">✓</span>
          </div>
          <span className="text-gray-700">{t('step3.maturity.high', 'Well-suited')}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded-full bg-yellow-600 flex items-center justify-center">
            <span className="text-[10px] text-white font-bold">◐</span>
          </div>
          <span className="text-gray-700">{t('step3.maturity.medium', 'Moderate effort')}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded-full bg-red-600 flex items-center justify-center">
            <span className="text-[10px] text-white font-bold">!</span>
          </div>
          <span className="text-gray-700">{t('step3.maturity.low', 'Ambitious')}</span>
        </div>
      </div>

      {/* Chart with quadrant backgrounds */}
      <div className="relative">
        <ResponsiveContainer width="100%" height={isMobile ? 400 : 360}>
          <ScatterChart margin={{ top: 30, right: 30, bottom: 50, left: 50 }}>
            {/* Gradient definitions for quadrant backgrounds */}
            <defs>
              <linearGradient id="quickWinsGradient" x1="0" y1="1" x2="0" y2="0">
                <stop offset="0%" stopColor="#dcfce7" stopOpacity="0.7"/>
                <stop offset="100%" stopColor="#dcfce7" stopOpacity="0.3"/>
              </linearGradient>
              <linearGradient id="strategicGradient" x1="0" y1="1" x2="0" y2="0">
                <stop offset="0%" stopColor="#dbeafe" stopOpacity="0.6"/>
                <stop offset="100%" stopColor="#dbeafe" stopOpacity="0.2"/>
              </linearGradient>
              <linearGradient id="avoidGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#fee2e2" stopOpacity="0.6"/>
                <stop offset="100%" stopColor="#fee2e2" stopOpacity="0.2"/>
              </linearGradient>
              <linearGradient id="fillInGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f3f4f6" stopOpacity="0.5"/>
                <stop offset="100%" stopColor="#f3f4f6" stopOpacity="0.2"/>
              </linearGradient>
            </defs>

            {/* Quadrant backgrounds */}
            <ReferenceArea x1={0.5} x2={2} y1={2} y2={3.5} fill="url(#quickWinsGradient)" fillOpacity={1} />
            <ReferenceArea x1={2} x2={3.5} y1={2} y2={3.5} fill="url(#strategicGradient)" fillOpacity={1} />
            <ReferenceArea x1={2} x2={3.5} y1={0.5} y2={2} fill="url(#avoidGradient)" fillOpacity={1} />
            <ReferenceArea x1={0.5} x2={2} y1={0.5} y2={2} fill="url(#fillInGradient)" fillOpacity={1} />

            <CartesianGrid strokeDasharray="3 3" stroke="#d1d5db" strokeOpacity={0.5} />

            {/* Reference lines to create quadrants */}
            <ReferenceLine x={2} stroke="#9ca3af" strokeDasharray="8 4" strokeWidth={2} />
            <ReferenceLine y={2} stroke="#9ca3af" strokeDasharray="8 4" strokeWidth={2} />

            <XAxis
              type="number"
              dataKey="xJitter"
              domain={[0.5, 3.5]}
              ticks={[1, 2, 3]}
              tickFormatter={(v) => isMobile
                ? ['', 'L', 'M', 'H'][v] || ''
                : ['', t('step3.scatter.low', 'Low'), t('step3.scatter.medium', 'Medium'), t('step3.scatter.high', 'High')][v] || ''
              }
              tick={{ fontSize: isMobile ? 11 : 12, fill: '#4b5563' }}
              axisLine={{ stroke: '#9ca3af' }}
            >
              <Label
                value={t('step3.scatter.effortAxis', 'Implementation Effort →')}
                position="bottom"
                offset={25}
                style={{ fontSize: 13, fill: '#374151', fontWeight: 500 }}
              />
            </XAxis>

            <YAxis
              type="number"
              dataKey="yJitter"
              domain={[0.5, 3.5]}
              ticks={[1, 2, 3]}
              tickFormatter={(v) => isMobile
                ? ['', 'L', 'M', 'H'][v] || ''
                : ['', t('step3.scatter.low', 'Low'), t('step3.scatter.medium', 'Medium'), t('step3.scatter.high', 'High')][v] || ''
              }
              tick={{ fontSize: isMobile ? 11 : 12, fill: '#4b5563' }}
              axisLine={{ stroke: '#9ca3af' }}
            >
              <Label
                value={t('step3.scatter.impactAxis', '↑ Business Impact')}
                position="left"
                angle={-90}
                offset={15}
                style={{ fontSize: 13, fill: '#374151', fontWeight: 500, textAnchor: 'middle' }}
              />
            </YAxis>

            <Tooltip content={<ScatterTooltip />} />

            <Scatter
              data={scatterData}
              onClick={(data) => handleClusterClick(data.id)}
              cursor="pointer"
              onMouseEnter={(data) => setHoveredId(data?.id)}
              onMouseLeave={() => setHoveredId(null)}
            >
              {scatterData.map((entry, index) => {
                const isHovered = hoveredId === entry.id;
                const isSelected = selectedClusterId === entry.id;
                const isRecentClick = recentlyClicked === entry.id;
                const maturityStyle = getMaturityStyle(entry.maturity_appropriateness);

                return (
                  <Cell
                    key={`cell-${index}`}
                    fill={isHovered ? maturityStyle.fillHover : maturityStyle.fill}
                    stroke={
                      isRecentClick ? '#10b981'
                        : isHovered ? '#3b82f6'
                        : isSelected ? '#2563eb'
                        : '#ffffff'
                    }
                    strokeWidth={isRecentClick ? 4 : isHovered || isSelected ? 3 : 2}
                    r={isRecentClick ? clickRadius : isHovered ? hoverRadius : isSelected ? hoverRadius - 2 : baseRadius}
                    style={{
                      filter: isHovered || isRecentClick ? 'drop-shadow(0 4px 8px rgba(0,0,0,0.25))' : 'drop-shadow(0 2px 4px rgba(0,0,0,0.1))',
                      transition: 'all 0.2s ease-out',
                      cursor: 'pointer'
                    }}
                  />
                );
              })}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>

        {/* Enhanced Quadrant labels overlay with visual hierarchy */}
        <div className="absolute top-10 left-16 text-xs text-gray-400 font-medium opacity-70">
          {t('step3.scatter.quadrantFillIn', 'Fill-ins')}
        </div>
        <div className="absolute top-8 right-8 text-sm text-red-700 font-semibold bg-red-50 px-2.5 py-1 rounded border border-red-200 shadow-sm">
          ⚠️ {t('step3.scatter.quadrantAvoid', 'Consider carefully')}
        </div>
        <div className="absolute bottom-16 left-14 text-base text-green-800 font-bold bg-gradient-to-br from-green-100 to-emerald-100 px-3 py-1.5 rounded-lg shadow border-2 border-green-400">
          ⭐ {t('step3.scatter.quadrantQuickWins', 'Quick Wins')}
        </div>
        <div className="absolute bottom-16 right-8 text-sm text-blue-700 font-semibold bg-blue-50 px-2.5 py-1 rounded border border-blue-300 shadow-sm">
          🎯 {t('step3.scatter.quadrantStrategic', 'Strategic')}
        </div>
      </div>

      {/* Enhanced Cluster name pills below chart */}
      <div className="mt-6 pt-4 border-t border-gray-200">
        <p className="text-sm font-medium text-gray-700 mb-3">
          {t('step3.scatter.selectCluster', 'Select a cluster to vote:')}
        </p>
        <div className="flex flex-wrap gap-3">
          {scatterData.map((cluster) => {
            const isSelected = selectedClusterId === cluster.id;
            const isHovered = hoveredId === cluster.id;
            const maturityStyle = getMaturityStyle(cluster.maturity_appropriateness);

            return (
              <button
                key={cluster.id}
                onClick={() => handleClusterClick(cluster.id)}
                onMouseEnter={() => setHoveredId(cluster.id)}
                onMouseLeave={() => setHoveredId(null)}
                className={`
                  inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium
                  transition-all duration-200 border-2 min-h-[44px]
                  ${isSelected
                    ? 'bg-blue-600 text-white border-blue-600 shadow-lg scale-105'
                    : isHovered
                      ? 'bg-gray-50 text-gray-800 border-gray-300 shadow-md scale-102'
                      : 'bg-white text-gray-700 border-gray-200 hover:border-gray-300 hover:shadow-md'
                  }
                `}
              >
                <span
                  className="w-4 h-4 rounded-full flex items-center justify-center text-[9px] text-white font-bold flex-shrink-0"
                  style={{ backgroundColor: maturityStyle.fill }}
                >
                  {maturityStyle.icon}
                </span>
                <span className="truncate max-w-[150px]">{cluster.name}</span>
                {cluster.points > 0 && (
                  <span className={`
                    ml-1 px-2 py-0.5 rounded-full text-xs font-bold
                    ${isSelected ? 'bg-blue-500' : 'bg-blue-100 text-blue-700'}
                  `}>
                    {cluster.points}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};

// Idea scatter plot component - Impact vs Effort matrix for Phase 2
const IdeaScatterPlot = ({ ideas, onIdeaClick, selectedIdeaId, ideaVotes }) => {
  const { t } = useTranslation();
  const [hoveredId, setHoveredId] = useState(null);
  const [recentlyClicked, setRecentlyClicked] = useState(null);
  const [showVoteToast, setShowVoteToast] = useState(false);

  // Transform idea data for scatter plot
  const scatterData = useMemo(() => {
    return ideas.map((idea, index) => ({
      ...idea,
      x: levelToNumber(idea.implementation_effort),
      y: levelToNumber(idea.business_impact),
      // Add jitter to prevent overlapping
      xJitter: levelToNumber(idea.implementation_effort) + (Math.random() - 0.5) * 0.4,
      yJitter: levelToNumber(idea.business_impact) + (Math.random() - 0.5) * 0.4,
      votes: ideaVotes[idea.id] || 0,
      shortLabel: `#${index + 1}`,
    }));
  }, [ideas, ideaVotes]);

  // Check if we have effort/impact data
  const hasEffortImpactData = ideas.some(i => i.implementation_effort && i.business_impact);

  if (!hasEffortImpactData || ideas.length === 0) {
    return null;
  }

  // Handle idea click with animation feedback
  const handleIdeaClick = (ideaId) => {
    setRecentlyClicked(ideaId);
    setShowVoteToast(true);
    setTimeout(() => setRecentlyClicked(null), 400);
    setTimeout(() => setShowVoteToast(false), 1500);
    onIdeaClick && onIdeaClick(ideaId);
  };

  // Responsive sizing for mobile touch targets
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 640;
  const baseRadius = isMobile ? 16 : 12;
  const hoverRadius = isMobile ? 20 : 16;
  const clickRadius = isMobile ? 24 : 20;

  // Color based on votes
  const getIdeaColor = (votes) => {
    if (votes >= 2) return '#7c3aed'; // purple-600
    if (votes === 1) return '#a78bfa'; // purple-400
    return '#8b5cf6'; // purple-500
  };

  // Custom tooltip for ideas
  const IdeaTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white rounded-xl shadow-2xl border-2 border-purple-400 p-4 max-w-sm relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-1.5 bg-purple-500" />
          <p className="font-bold text-gray-900 text-sm pt-1 mb-2 line-clamp-3">{data.content}</p>
          <p className="text-xs text-gray-500 mb-3">{t('step3.results.by')} {data.participant_name}</p>
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-gray-500 font-medium min-w-[70px]">{t('step3.scatter.impact', 'Impact')}:</span>
              <span className="font-semibold text-gray-900 capitalize">{data.business_impact}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-gray-500 font-medium min-w-[70px]">{t('step3.scatter.effort', 'Effort')}:</span>
              <span className="font-semibold text-gray-900 capitalize">{data.implementation_effort}</span>
            </div>
          </div>
          {data.impact_rationale && (
            <p className="text-xs text-gray-500 italic mt-3 pt-3 border-t border-gray-100">
              "{data.impact_rationale}"
            </p>
          )}
          <div className="mt-3 pt-3 border-t border-gray-100 flex items-center gap-2 text-purple-600">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
            </svg>
            <span className="text-xs font-medium">{t('step3.ideaScatter.clickToVote', 'Click to vote for this idea')}</span>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-5 mb-6 relative">
      {/* Vote toast notification */}
      {showVoteToast && (
        <div className="absolute top-4 right-4 bg-purple-600 text-white px-4 py-2.5 rounded-lg shadow-xl flex items-center gap-2 z-50 animate-pulse">
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
          </svg>
          <span className="font-medium text-sm">{t('step3.scatter.voteAdded', 'Vote added!')}</span>
        </div>
      )}

      <h3 className="text-xl font-bold text-gray-900 mb-1">
        {t('step3.ideaScatter.title', 'Idea Prioritization Matrix')}
      </h3>
      <p className="text-sm text-gray-600 mb-5">
        {t('step3.ideaScatter.subtitle', 'Click on ideas to vote. Position shows effort vs impact.')}
      </p>

      {/* Chart */}
      <div className="relative">
        <ResponsiveContainer width="100%" height={isMobile ? 400 : 360}>
          <ScatterChart margin={{ top: 30, right: 30, bottom: 50, left: 50 }}>
            {/* Gradient definitions for quadrant backgrounds */}
            <defs>
              <linearGradient id="ideaQuickWinsGradient" x1="0" y1="1" x2="0" y2="0">
                <stop offset="0%" stopColor="#f3e8ff" stopOpacity="0.7"/>
                <stop offset="100%" stopColor="#f3e8ff" stopOpacity="0.3"/>
              </linearGradient>
              <linearGradient id="ideaStrategicGradient" x1="0" y1="1" x2="0" y2="0">
                <stop offset="0%" stopColor="#ede9fe" stopOpacity="0.6"/>
                <stop offset="100%" stopColor="#ede9fe" stopOpacity="0.2"/>
              </linearGradient>
              <linearGradient id="ideaAvoidGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#fef2f2" stopOpacity="0.6"/>
                <stop offset="100%" stopColor="#fef2f2" stopOpacity="0.2"/>
              </linearGradient>
              <linearGradient id="ideaFillInGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f9fafb" stopOpacity="0.5"/>
                <stop offset="100%" stopColor="#f9fafb" stopOpacity="0.2"/>
              </linearGradient>
            </defs>

            {/* Quadrant backgrounds */}
            <ReferenceArea x1={0.5} x2={2} y1={2} y2={3.5} fill="url(#ideaQuickWinsGradient)" fillOpacity={1} />
            <ReferenceArea x1={2} x2={3.5} y1={2} y2={3.5} fill="url(#ideaStrategicGradient)" fillOpacity={1} />
            <ReferenceArea x1={2} x2={3.5} y1={0.5} y2={2} fill="url(#ideaAvoidGradient)" fillOpacity={1} />
            <ReferenceArea x1={0.5} x2={2} y1={0.5} y2={2} fill="url(#ideaFillInGradient)" fillOpacity={1} />

            <CartesianGrid strokeDasharray="3 3" stroke="#d1d5db" strokeOpacity={0.5} />
            <ReferenceLine x={2} stroke="#9ca3af" strokeDasharray="8 4" strokeWidth={2} />
            <ReferenceLine y={2} stroke="#9ca3af" strokeDasharray="8 4" strokeWidth={2} />

            <XAxis
              type="number"
              dataKey="xJitter"
              domain={[0.5, 3.5]}
              ticks={[1, 2, 3]}
              tickFormatter={(v) => isMobile
                ? ['', 'L', 'M', 'H'][v] || ''
                : ['', t('step3.scatter.low', 'Low'), t('step3.scatter.medium', 'Medium'), t('step3.scatter.high', 'High')][v] || ''
              }
              tick={{ fontSize: isMobile ? 11 : 12, fill: '#4b5563' }}
              axisLine={{ stroke: '#9ca3af' }}
            >
              <Label
                value={t('step3.scatter.effortAxis', 'Implementation Effort →')}
                position="bottom"
                offset={25}
                style={{ fontSize: 13, fill: '#374151', fontWeight: 500 }}
              />
            </XAxis>

            <YAxis
              type="number"
              dataKey="yJitter"
              domain={[0.5, 3.5]}
              ticks={[1, 2, 3]}
              tickFormatter={(v) => isMobile
                ? ['', 'L', 'M', 'H'][v] || ''
                : ['', t('step3.scatter.low', 'Low'), t('step3.scatter.medium', 'Medium'), t('step3.scatter.high', 'High')][v] || ''
              }
              tick={{ fontSize: isMobile ? 11 : 12, fill: '#4b5563' }}
              axisLine={{ stroke: '#9ca3af' }}
            >
              <Label
                value={t('step3.scatter.impactAxis', '↑ Business Impact')}
                position="left"
                angle={-90}
                offset={15}
                style={{ fontSize: 13, fill: '#374151', fontWeight: 500, textAnchor: 'middle' }}
              />
            </YAxis>

            <Tooltip content={<IdeaTooltip />} />

            <Scatter
              data={scatterData}
              onClick={(data) => handleIdeaClick(data.id)}
              cursor="pointer"
              onMouseEnter={(data) => setHoveredId(data?.id)}
              onMouseLeave={() => setHoveredId(null)}
            >
              {scatterData.map((entry, index) => {
                const isHovered = hoveredId === entry.id;
                const isSelected = selectedIdeaId === entry.id;
                const isRecentClick = recentlyClicked === entry.id;
                const hasVotes = entry.votes > 0;

                return (
                  <Cell
                    key={`cell-${index}`}
                    fill={getIdeaColor(entry.votes)}
                    stroke={
                      isRecentClick ? '#10b981'
                        : isHovered ? '#7c3aed'
                        : isSelected ? '#5b21b6'
                        : '#ffffff'
                    }
                    strokeWidth={isRecentClick ? 4 : isHovered || isSelected ? 3 : 2}
                    r={isRecentClick ? clickRadius : isHovered ? hoverRadius : hasVotes ? baseRadius + 3 : baseRadius}
                    style={{
                      filter: isHovered || isRecentClick ? 'drop-shadow(0 4px 8px rgba(124,58,237,0.35))' : 'drop-shadow(0 2px 4px rgba(0,0,0,0.1))',
                      transition: 'all 0.2s ease-out',
                      cursor: 'pointer'
                    }}
                  />
                );
              })}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>

        {/* Quadrant labels overlay */}
        <div className="absolute top-10 left-16 text-xs text-gray-400 font-medium opacity-70">
          {t('step3.scatter.quadrantFillIn', 'Fill-ins')}
        </div>
        <div className="absolute top-8 right-8 text-sm text-red-700 font-semibold bg-red-50 px-2.5 py-1 rounded border border-red-200 shadow-sm">
          ⚠️ {t('step3.scatter.quadrantAvoid', 'Consider carefully')}
        </div>
        <div className="absolute bottom-16 left-14 text-base text-purple-800 font-bold bg-gradient-to-br from-purple-100 to-violet-100 px-3 py-1.5 rounded-lg shadow border-2 border-purple-400">
          ⭐ {t('step3.scatter.quadrantQuickWins', 'Quick Wins')}
        </div>
        <div className="absolute bottom-16 right-8 text-sm text-purple-700 font-semibold bg-purple-50 px-2.5 py-1 rounded border border-purple-300 shadow-sm">
          🎯 {t('step3.scatter.quadrantStrategic', 'Strategic')}
        </div>
      </div>

      {/* Ideas list below chart */}
      <div className="mt-6 pt-4 border-t border-gray-200">
        <p className="text-sm font-medium text-gray-700 mb-3">
          {t('step3.ideaScatter.selectIdea', 'Select an idea to vote:')}
        </p>
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {scatterData.map((idea, index) => {
            const isSelected = selectedIdeaId === idea.id;
            const isHovered = hoveredId === idea.id;

            return (
              <button
                key={idea.id}
                onClick={() => handleIdeaClick(idea.id)}
                onMouseEnter={() => setHoveredId(idea.id)}
                onMouseLeave={() => setHoveredId(null)}
                className={`
                  w-full text-left flex items-start gap-3 px-4 py-3 rounded-lg text-sm
                  transition-all duration-200 border-2 min-h-[44px]
                  ${isSelected
                    ? 'bg-purple-600 text-white border-purple-600 shadow-lg'
                    : isHovered
                      ? 'bg-purple-50 text-gray-800 border-purple-300 shadow-md'
                      : 'bg-white text-gray-700 border-gray-200 hover:border-purple-200 hover:shadow-md'
                  }
                `}
              >
                <span className={`
                  flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold
                  ${isSelected ? 'bg-purple-500 text-white' : 'bg-purple-100 text-purple-700'}
                `}>
                  {index + 1}
                </span>
                <span className="flex-1 line-clamp-2">{idea.content}</span>
                {idea.votes > 0 && (
                  <span className={`
                    flex-shrink-0 px-2 py-0.5 rounded-full text-xs font-bold
                    ${isSelected ? 'bg-purple-500' : 'bg-purple-100 text-purple-700'}
                  `}>
                    {idea.votes}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};

// Expandable cluster card component
const ClusterCard = ({ cluster, votes, totalPoints, onAddPoint, onRemovePoint, canAddPoint, forceExpanded = false }) => {
  const [localExpanded, setLocalExpanded] = useState(false);
  const { t } = useTranslation();

  // Use forceExpanded if set, otherwise use local state
  const expanded = forceExpanded || localExpanded;

  const hasIdeas = cluster.ideas && cluster.ideas.length > 0;
  const ideaCount = cluster.idea_ids?.length || cluster.ideas?.length || 0;

  return (
    <div
      className={`relative rounded-lg shadow border-2 transition-all duration-200 ${getCardColorClasses(votes, 'blue')}`}
    >
      {/* Vote badge overlay */}
      <VoteBadge votes={votes} color="blue" />
      {/* Main card content */}
      <div className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            {/* Header with name and maturity badge */}
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-semibold text-gray-900 text-lg">{cluster.name}</h3>
              <MaturityBadge
                level={cluster.maturity_appropriateness}
                rationale={cluster.maturity_rationale}
              />
            </div>
            <p className="text-gray-600 mt-1">{cluster.description}</p>

            {/* Idea count and expand toggle */}
            <div className="flex items-center gap-3 mt-3">
              {ideaCount > 0 && (
                <button
                  onClick={() => setLocalExpanded(!localExpanded)}
                  className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                    expanded
                      ? 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  <svg className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                  {expanded
                    ? t('step3.phase1.hideIdeas', 'Hide ideas')
                    : t('step3.phase1.showIdeas', 'Show ideas')
                  }
                  <span className="bg-white px-1.5 py-0.5 rounded-full text-xs">
                    {ideaCount}
                  </span>
                </button>
              )}
            </div>
          </div>

          {/* Voting controls */}
          <div className="flex flex-col items-center gap-2">
            <div className="flex items-center gap-2">
              <button
                onClick={onRemovePoint}
                disabled={votes === 0}
                className="w-10 h-10 rounded-full bg-gray-200 text-gray-700 hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center font-bold transition-colors"
                aria-label="Remove point"
              >
                -
              </button>
              <div className="w-12 flex justify-center">
                <PointsIndicator current={votes} total={totalPoints} color="blue" />
              </div>
              <button
                onClick={onAddPoint}
                disabled={!canAddPoint}
                className="w-10 h-10 rounded-full bg-blue-600 text-white hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center font-bold transition-colors"
                aria-label="Add point"
              >
                +
              </button>
            </div>
            {votes > 0 && (
              <span className="text-xs text-blue-600 font-medium">
                {votes} {votes === 1 ? t('step3.voting.point', 'point') : t('step3.voting.points', 'points')}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Expandable ideas section */}
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
                    <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-xs font-medium">
                      {index + 1}
                    </span>
                    <IdeaMarkdown content={idea.content} className="text-sm text-gray-700 flex-1" />
                  </div>
                </div>
              ))
            ) : cluster.idea_ids && cluster.idea_ids.length > 0 ? (
              <p className="text-sm text-amber-600">
                {t('step3.phase1.ideasLoadingError', 'Could not load idea details. Try regenerating clusters.')}
              </p>
            ) : (
              <p className="text-sm text-gray-500 italic">
                {t('step3.phase1.noIdeas', 'No ideas in this cluster')}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

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

  // Assessed ideas state (for scatter plot)
  const [assessedIdeas, setAssessedIdeas] = useState([]);
  const [assessingIdeas, setAssessingIdeas] = useState(false);

  // Expand all clusters toggle
  const [expandAllClusters, setExpandAllClusters] = useState(false);

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
          const loadedIdeas = clusterIdeasResponse.data.ideas || [];
          setClusterIdeas(loadedIdeas);
          // Set unassessed ideas first so UI can render immediately
          setAssessedIdeas(loadedIdeas);

          // Load assessed ideas in background (don't block UI)
          prioritizationAPI.assessClusterIdeas(sessionUuid, apiKeyManager.get())
            .then(assessResponse => {
              setAssessedIdeas(assessResponse.data.ideas || loadedIdeas);
            })
            .catch(assessErr => {
              console.error('Failed to assess ideas:', assessErr);
              // Keep unassessed ideas as fallback (already set)
            });
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
      const loadedIdeas = clusterIdeasResponse.data.ideas || [];
      setClusterIdeas(loadedIdeas);

      // Auto-assess ideas for scatter plot
      setAssessingIdeas(true);
      try {
        const assessResponse = await prioritizationAPI.assessClusterIdeas(sessionUuid, apiKeyManager.get());
        setAssessedIdeas(assessResponse.data.ideas || []);
      } catch (assessErr) {
        console.error('Failed to assess ideas:', assessErr);
        // Fall back to unassessed ideas
        setAssessedIdeas(loadedIdeas);
      } finally {
        setAssessingIdeas(false);
      }

      setActiveTab('ideas');
    } catch (err) {
      setError(err.response?.data?.detail || t('step3.errors.selectFailed'));
    } finally {
      setSubmitting(false);
    }
  };

  // Function to manually re-assess ideas
  const handleAssessIdeas = async () => {
    setAssessingIdeas(true);
    setError(null);
    try {
      const assessResponse = await prioritizationAPI.assessClusterIdeas(sessionUuid, apiKeyManager.get());
      setAssessedIdeas(assessResponse.data.ideas || []);
    } catch (err) {
      setError(err.response?.data?.detail || t('step3.errors.assessFailed', 'Failed to assess ideas'));
    } finally {
      setAssessingIdeas(false);
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
                {/* Fallback clustering notice */}
                {clusters.some(c => c.maturity_rationale?.includes('Auto-grouped') || c.maturity_rationale?.includes('Automatisch gruppiert')) && (
                  <div className="mb-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
                    <div className="flex items-start gap-3">
                      <svg className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <div>
                        <h4 className="font-medium text-amber-800">{t('step3.fallbackClustering.title')}</h4>
                        <p className="text-sm text-amber-700 mt-1">{t('step3.fallbackClustering.message')}</p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Scatter Plot - Impact vs Effort Matrix */}
                <ClusterScatterPlot
                  clusters={clusters}
                  onClusterClick={(clusterId) => {
                    // Add a point to clicked cluster if we have points remaining
                    if (remainingClusterPoints > 0) {
                      handleAddClusterPoint(clusterId);
                    }
                  }}
                  selectedClusterId={null}
                />

                {/* Points indicator */}
                <div className="bg-white rounded-lg shadow p-4 mb-6 sticky top-4 z-10">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div>
                        <p className="text-sm font-medium text-gray-700 mb-1">
                          {t('step3.voting.pointsRemaining')}
                        </p>
                        <div className="flex items-center gap-3">
                          <PointsIndicator
                            current={usedClusterPoints}
                            total={totalPoints}
                            color={remainingClusterPoints === 0 ? 'green' : 'blue'}
                          />
                          <span className={`text-sm font-semibold ${remainingClusterPoints === 0 ? 'text-green-600' : 'text-blue-600'}`}>
                            {usedClusterPoints} / {totalPoints} {t('step3.voting.allocated', 'allocated')}
                          </span>
                        </div>
                      </div>
                      <p className="text-sm text-gray-500 border-l border-gray-200 pl-4">{t('step3.phase1.voteHint')}</p>
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

                {/* Clusters list with expand all toggle */}
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-800">
                    {t('step3.phase1.clusterList', 'Cluster List')}
                  </h3>
                  <button
                    onClick={() => setExpandAllClusters(!expandAllClusters)}
                    className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1 font-medium"
                  >
                    {expandAllClusters ? (
                      <>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                        </svg>
                        {t('step3.phase1.collapseAll', 'Collapse all')}
                      </>
                    ) : (
                      <>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                        {t('step3.phase1.expandAll', 'Show all ideas')}
                      </>
                    )}
                  </button>
                </div>
                <div className="space-y-4">
                  {clusters.map((cluster) => (
                    <ClusterCard
                      key={cluster.id}
                      cluster={cluster}
                      votes={clusterVotes[cluster.id] || 0}
                      totalPoints={totalPoints}
                      onAddPoint={() => handleAddClusterPoint(cluster.id)}
                      onRemovePoint={() => handleRemoveClusterPoint(cluster.id)}
                      canAddPoint={remainingClusterPoints > 0}
                      forceExpanded={expandAllClusters}
                    />
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

                {/* Full ranking with vote distribution */}
                <div className="bg-white rounded-lg shadow">
                  <div className="px-4 py-3 border-b border-gray-200">
                    <h3 className="text-lg font-semibold text-gray-900">{t('step3.phase1.allRanked')}</h3>
                  </div>
                  <div className="divide-y divide-gray-100">
                    {clusterResults.ranked_clusters?.map((cluster) => {
                      const maxPoints = clusterResults.ranked_clusters[0]?.total_points || 1;
                      const isTop = cluster.rank === 1;
                      return (
                        <div key={cluster.cluster_id} className={`px-4 py-3 flex items-center gap-4 ${isTop ? 'bg-yellow-50' : ''}`}>
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                            isTop ? 'bg-yellow-400 text-yellow-900' : 'bg-gray-200 text-gray-700'
                          }`}>
                            #{cluster.rank}
                          </div>
                          <div className="flex-1 min-w-0">
                            <h4 className={`font-medium ${isTop ? 'text-yellow-900' : 'text-gray-900'}`}>{cluster.cluster_name}</h4>
                            <p className="text-sm text-gray-500">{cluster.idea_count} {t('step3.phase1.ideas')}</p>
                          </div>
                          <VoteDistributionBar
                            points={cluster.total_points}
                            maxPoints={maxPoints}
                            color="blue"
                            isTop={isTop}
                          />
                          {!selectedClusterId && (
                            <button
                              onClick={() => handleSelectCluster(cluster.cluster_id)}
                              disabled={submitting}
                              className={`py-1 px-3 rounded-md text-sm ${isTop ? 'bg-yellow-400 text-yellow-900 hover:bg-yellow-500' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
                            >
                              {t('step3.phase1.select')}
                            </button>
                          )}
                        </div>
                      );
                    })}
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

            {/* Idea Scatter Plot - Impact vs Effort Matrix */}
            {!hasVotedIdeas && clusterIdeas.length > 0 && (
              <>
                {assessingIdeas ? (
                  <div className="bg-purple-50 border border-purple-200 rounded-lg p-6 mb-6 text-center">
                    <div className="flex items-center justify-center gap-3">
                      <svg className="animate-spin h-5 w-5 text-purple-600" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      <span className="text-purple-700 font-medium">{t('step3.ideaScatter.analyzing', 'Analyzing ideas...')}</span>
                    </div>
                  </div>
                ) : assessedIdeas.length > 0 && assessedIdeas.some(i => i.implementation_effort && i.business_impact) ? (
                  <IdeaScatterPlot
                    ideas={assessedIdeas}
                    onIdeaClick={(ideaId) => {
                      if (remainingIdeaPoints > 0) {
                        handleAddIdeaPoint(ideaId);
                      }
                    }}
                    selectedIdeaId={null}
                    ideaVotes={ideaVotes}
                  />
                ) : (
                  <div className="bg-purple-50 border border-purple-200 rounded-lg p-6 mb-6">
                    <div className="text-center">
                      <h3 className="text-lg font-semibold text-purple-900 mb-2">
                        {t('step3.ideaScatter.title', 'Idea Prioritization Matrix')}
                      </h3>
                      <p className="text-purple-700 mb-4">
                        {t('step3.ideaScatter.analyzeHint', 'Analyze ideas to see them on an Impact vs Effort matrix and find the best opportunities.')}
                      </p>
                      <button
                        onClick={handleAssessIdeas}
                        disabled={!apiKeyManager.get()}
                        className="bg-purple-600 text-white py-2 px-6 rounded-md hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium inline-flex items-center gap-2"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                        </svg>
                        {t('step3.ideaScatter.analyzeButton', 'Analyze Ideas')}
                      </button>
                      {!apiKeyManager.get() && (
                        <p className="text-sm text-gray-500 mt-2">
                          {t('step3.ideaScatter.apiKeyRequired', 'API key required for analysis')}
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Idea Voting */}
            {!hasVotedIdeas && (
              <>
                {/* Points indicator */}
                <div className="bg-white rounded-lg shadow p-4 mb-6 sticky top-4 z-10">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div>
                        <p className="text-sm font-medium text-gray-700 mb-1">
                          {t('step3.voting.pointsRemaining')}
                        </p>
                        <div className="flex items-center gap-3">
                          <PointsIndicator
                            current={usedIdeaPoints}
                            total={totalPoints}
                            color={remainingIdeaPoints === 0 ? 'green' : 'purple'}
                          />
                          <span className={`text-sm font-semibold ${remainingIdeaPoints === 0 ? 'text-green-600' : 'text-purple-600'}`}>
                            {usedIdeaPoints} / {totalPoints} {t('step3.voting.allocated', 'allocated')}
                          </span>
                        </div>
                      </div>
                      <p className="text-sm text-gray-500 border-l border-gray-200 pl-4">{t('step3.phase2.voteHint')}</p>
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
                  {clusterIdeas.map((idea) => {
                    const votes = ideaVotes[idea.id] || 0;
                    return (
                      <div
                        key={idea.id}
                        className={`relative rounded-lg shadow p-4 border-2 transition-all duration-200 ${getCardColorClasses(votes, 'purple')}`}
                      >
                        {/* Vote badge overlay */}
                        <VoteBadge votes={votes} color="purple" />
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1">
                            <IdeaMarkdown content={idea.content} className="text-gray-900" />
                            <p className="text-sm text-gray-500 mt-2">
                              {t('step3.results.by')} {idea.participant_name} ({t('step3.results.round')} {idea.round_number})
                            </p>
                          </div>
                          <div className="flex flex-col items-center gap-2">
                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => handleRemoveIdeaPoint(idea.id)}
                                disabled={votes === 0}
                                className="w-10 h-10 rounded-full bg-gray-200 text-gray-700 hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center font-bold transition-colors"
                                aria-label="Remove point"
                              >
                                -
                              </button>
                              <div className="w-12 flex justify-center">
                                <PointsIndicator current={votes} total={totalPoints} color="purple" />
                              </div>
                              <button
                                onClick={() => handleAddIdeaPoint(idea.id)}
                                disabled={remainingIdeaPoints <= 0}
                                className="w-10 h-10 rounded-full bg-purple-600 text-white hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center font-bold transition-colors"
                                aria-label="Add point"
                              >
                                +
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
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

                {/* Full ranking with vote distribution */}
                <div className="bg-white rounded-lg shadow">
                  <div className="px-4 py-3 border-b border-gray-200">
                    <h3 className="text-lg font-semibold text-gray-900">{t('step3.results.allRanked')}</h3>
                  </div>
                  <div className="divide-y divide-gray-100">
                    {ideaResults.ranked_ideas?.map((idea) => {
                      const maxPoints = ideaResults.ranked_ideas[0]?.total_points || 1;
                      const isTop = idea.rank === 1;
                      return (
                        <div key={idea.idea_id} className={`px-4 py-3 flex items-center gap-4 ${isTop ? 'bg-yellow-50' : ''}`}>
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 ${
                            isTop ? 'bg-yellow-400 text-yellow-900' : 'bg-gray-200 text-gray-700'
                          }`}>
                            #{idea.rank}
                          </div>
                          <div className="flex-1 min-w-0">
                            <IdeaMarkdown content={idea.idea_content} className={isTop ? 'text-yellow-900' : 'text-gray-900'} />
                            <p className="text-sm text-gray-500">{t('step3.results.by')} {idea.participant_name}</p>
                          </div>
                          <VoteDistributionBar
                            points={idea.total_points}
                            maxPoints={maxPoints}
                            color="purple"
                            isTop={isTop}
                          />
                        </div>
                      );
                    })}
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
