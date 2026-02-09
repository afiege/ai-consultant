import React, { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, ReferenceLine, ReferenceArea, Label,
} from 'recharts';
import { levelToNumber, getMaturityStyle } from './helpers';

/** Tooltip shown when hovering a cluster dot on the scatter chart. */
const ScatterTooltip = ({ active, payload }) => {
  const { t } = useTranslation();
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    const maturityStyle = getMaturityStyle(data.maturity_appropriateness);
    return (
      <div className="bg-white rounded-xl shadow-2xl border-2 p-4 max-w-xs relative overflow-hidden" style={{ borderColor: maturityStyle.fill }}>
        <div className="absolute top-0 left-0 right-0 h-1.5" style={{ backgroundColor: maturityStyle.fill }} />
        <p className="font-bold text-gray-900 text-base pt-1 mb-2">{data.name}</p>
        {data.description && <p className="text-sm text-gray-600 mb-3 leading-relaxed">{data.description}</p>}
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
            <span className="font-semibold capitalize px-2 py-0.5 rounded-full text-white text-xs inline-flex items-center gap-1" style={{ backgroundColor: maturityStyle.fill }}>
              <span>{maturityStyle.icon}</span>
              <span>{data.maturity_appropriateness}</span>
            </span>
          </div>
        </div>
        {data.impact_rationale && (
          <p className="text-xs text-gray-500 italic mt-3 pt-3 border-t border-gray-100">"{data.impact_rationale}"</p>
        )}
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

/** Interactive scatter chart for cluster-level prioritization (Phase 1). */
const ClusterScatterPlot = ({ clusters, onClusterClick, selectedClusterId }) => {
  const { t } = useTranslation();
  const [hoveredId, setHoveredId] = useState(null);
  const [recentlyClicked, setRecentlyClicked] = useState(null);
  const [showVoteToast, setShowVoteToast] = useState(false);

  const scatterData = useMemo(() => {
    return clusters.map(cluster => ({
      ...cluster,
      x: levelToNumber(cluster.implementation_effort),
      y: levelToNumber(cluster.business_impact),
      xJitter: levelToNumber(cluster.implementation_effort) + (Math.random() - 0.5) * 0.3,
      yJitter: levelToNumber(cluster.business_impact) + (Math.random() - 0.5) * 0.3,
    }));
  }, [clusters]);

  const hasEffortImpactData = clusters.some(c => c.implementation_effort && c.business_impact);
  if (!hasEffortImpactData) return null;

  const handleClusterClick = (clusterId) => {
    setRecentlyClicked(clusterId);
    setShowVoteToast(true);
    setTimeout(() => setRecentlyClicked(null), 400);
    setTimeout(() => setShowVoteToast(false), 1500);
    onClusterClick && onClusterClick(clusterId);
  };

  const isMobile = typeof window !== 'undefined' && window.innerWidth < 640;
  const baseRadius = isMobile ? 18 : 14;
  const hoverRadius = isMobile ? 22 : 18;
  const clickRadius = isMobile ? 26 : 22;

  return (
    <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-5 mb-6 relative">
      {showVoteToast && (
        <div className="absolute top-4 right-4 bg-green-600 text-white px-4 py-2.5 rounded-lg shadow-xl flex items-center gap-2 z-50 animate-pulse">
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
          </svg>
          <span className="font-medium text-sm">{t('step3.scatter.voteAdded', 'Vote added!')}</span>
        </div>
      )}

      <h3 className="text-xl font-bold text-gray-900 mb-1">{t('step3.scatter.title', 'Cluster Prioritization Matrix')}</h3>
      <p className="text-sm text-gray-600 mb-5">{t('step3.scatter.subtitle', 'Click on clusters to vote. Colors indicate maturity fit.')}</p>

      <div className="flex flex-wrap gap-4 mb-5 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded-full bg-green-600 flex items-center justify-center"><span className="text-[10px] text-white font-bold">✓</span></div>
          <span className="text-gray-700">{t('step3.maturity.high', 'Well-suited')}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded-full bg-yellow-600 flex items-center justify-center"><span className="text-[10px] text-white font-bold">◐</span></div>
          <span className="text-gray-700">{t('step3.maturity.medium', 'Moderate effort')}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded-full bg-red-600 flex items-center justify-center"><span className="text-[10px] text-white font-bold">!</span></div>
          <span className="text-gray-700">{t('step3.maturity.low', 'Ambitious')}</span>
        </div>
      </div>

      <div className="relative">
        <ResponsiveContainer width="100%" height={isMobile ? 400 : 360}>
          <ScatterChart margin={{ top: 30, right: 30, bottom: 50, left: 50 }}>
            <defs>
              <linearGradient id="quickWinsGradient" x1="0" y1="1" x2="0" y2="0">
                <stop offset="0%" stopColor="#dcfce7" stopOpacity="0.7"/><stop offset="100%" stopColor="#dcfce7" stopOpacity="0.3"/>
              </linearGradient>
              <linearGradient id="strategicGradient" x1="0" y1="1" x2="0" y2="0">
                <stop offset="0%" stopColor="#dbeafe" stopOpacity="0.6"/><stop offset="100%" stopColor="#dbeafe" stopOpacity="0.2"/>
              </linearGradient>
              <linearGradient id="avoidGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#fee2e2" stopOpacity="0.6"/><stop offset="100%" stopColor="#fee2e2" stopOpacity="0.2"/>
              </linearGradient>
              <linearGradient id="fillInGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f3f4f6" stopOpacity="0.5"/><stop offset="100%" stopColor="#f3f4f6" stopOpacity="0.2"/>
              </linearGradient>
            </defs>

            <ReferenceArea x1={0.5} x2={2} y1={2} y2={3.5} fill="url(#quickWinsGradient)" fillOpacity={1} />
            <ReferenceArea x1={2} x2={3.5} y1={2} y2={3.5} fill="url(#strategicGradient)" fillOpacity={1} />
            <ReferenceArea x1={2} x2={3.5} y1={0.5} y2={2} fill="url(#avoidGradient)" fillOpacity={1} />
            <ReferenceArea x1={0.5} x2={2} y1={0.5} y2={2} fill="url(#fillInGradient)" fillOpacity={1} />

            <CartesianGrid strokeDasharray="3 3" stroke="#d1d5db" strokeOpacity={0.5} />
            <ReferenceLine x={2} stroke="#9ca3af" strokeDasharray="8 4" strokeWidth={2} />
            <ReferenceLine y={2} stroke="#9ca3af" strokeDasharray="8 4" strokeWidth={2} />

            <XAxis type="number" dataKey="xJitter" domain={[0.5, 3.5]} ticks={[1, 2, 3]}
              tickFormatter={(v) => isMobile ? ['', 'L', 'M', 'H'][v] || '' : ['', t('step3.scatter.low', 'Low'), t('step3.scatter.medium', 'Medium'), t('step3.scatter.high', 'High')][v] || ''}
              tick={{ fontSize: isMobile ? 11 : 12, fill: '#4b5563' }} axisLine={{ stroke: '#9ca3af' }}>
              <Label value={t('step3.scatter.effortAxis', 'Implementation Effort →')} position="bottom" offset={25} style={{ fontSize: 13, fill: '#374151', fontWeight: 500 }} />
            </XAxis>

            <YAxis type="number" dataKey="yJitter" domain={[0.5, 3.5]} ticks={[1, 2, 3]}
              tickFormatter={(v) => isMobile ? ['', 'L', 'M', 'H'][v] || '' : ['', t('step3.scatter.low', 'Low'), t('step3.scatter.medium', 'Medium'), t('step3.scatter.high', 'High')][v] || ''}
              tick={{ fontSize: isMobile ? 11 : 12, fill: '#4b5563' }} axisLine={{ stroke: '#9ca3af' }}>
              <Label value={t('step3.scatter.impactAxis', '↑ Business Impact')} position="left" angle={-90} offset={15} style={{ fontSize: 13, fill: '#374151', fontWeight: 500, textAnchor: 'middle' }} />
            </YAxis>

            <Tooltip content={<ScatterTooltip />} />

            <Scatter data={scatterData} onClick={(data) => handleClusterClick(data.id)} cursor="pointer"
              onMouseEnter={(data) => setHoveredId(data?.id)} onMouseLeave={() => setHoveredId(null)}>
              {scatterData.map((entry, index) => {
                const isHovered = hoveredId === entry.id;
                const isSelected = selectedClusterId === entry.id;
                const isRecentClick = recentlyClicked === entry.id;
                const maturityStyle = getMaturityStyle(entry.maturity_appropriateness);
                return (
                  <Cell key={`cell-${index}`}
                    fill={isHovered ? maturityStyle.fillHover : maturityStyle.fill}
                    stroke={isRecentClick ? '#10b981' : isHovered ? '#3b82f6' : isSelected ? '#2563eb' : '#ffffff'}
                    strokeWidth={isRecentClick ? 4 : isHovered || isSelected ? 3 : 2}
                    r={isRecentClick ? clickRadius : isHovered ? hoverRadius : isSelected ? hoverRadius - 2 : baseRadius}
                    style={{
                      filter: isHovered || isRecentClick ? 'drop-shadow(0 4px 8px rgba(0,0,0,0.25))' : 'drop-shadow(0 2px 4px rgba(0,0,0,0.1))',
                      transition: 'all 0.2s ease-out', cursor: 'pointer',
                    }}
                  />
                );
              })}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>

        <div className="absolute top-10 left-16 text-xs text-gray-400 font-medium opacity-70">{t('step3.scatter.quadrantFillIn', 'Fill-ins')}</div>
        <div className="absolute top-8 right-8 text-sm text-red-700 font-semibold bg-red-50 px-2.5 py-1 rounded border border-red-200 shadow-sm">⚠️ {t('step3.scatter.quadrantAvoid', 'Consider carefully')}</div>
        <div className="absolute bottom-16 left-14 text-base text-green-800 font-bold bg-gradient-to-br from-green-100 to-emerald-100 px-3 py-1.5 rounded-lg shadow border-2 border-green-400">⭐ {t('step3.scatter.quadrantQuickWins', 'Quick Wins')}</div>
        <div className="absolute bottom-16 right-8 text-sm text-blue-700 font-semibold bg-blue-50 px-2.5 py-1 rounded border border-blue-300 shadow-sm">🎯 {t('step3.scatter.quadrantStrategic', 'Strategic')}</div>
      </div>

      <div className="mt-6 pt-4 border-t border-gray-200">
        <p className="text-sm font-medium text-gray-700 mb-3">{t('step3.scatter.selectCluster', 'Select a cluster to vote:')}</p>
        <div className="flex flex-wrap gap-3">
          {scatterData.map((cluster) => {
            const isSelected = selectedClusterId === cluster.id;
            const isHovered = hoveredId === cluster.id;
            const maturityStyle = getMaturityStyle(cluster.maturity_appropriateness);
            return (
              <button key={cluster.id} onClick={() => handleClusterClick(cluster.id)}
                onMouseEnter={() => setHoveredId(cluster.id)} onMouseLeave={() => setHoveredId(null)}
                className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 border-2 min-h-[44px] ${
                  isSelected ? 'bg-blue-600 text-white border-blue-600 shadow-lg scale-105'
                    : isHovered ? 'bg-gray-50 text-gray-800 border-gray-300 shadow-md scale-102'
                    : 'bg-white text-gray-700 border-gray-200 hover:border-gray-300 hover:shadow-md'}`}>
                <span className="w-4 h-4 rounded-full flex items-center justify-center text-[9px] text-white font-bold flex-shrink-0" style={{ backgroundColor: maturityStyle.fill }}>{maturityStyle.icon}</span>
                <span className="truncate max-w-[150px]">{cluster.name}</span>
                {cluster.points > 0 && (
                  <span className={`ml-1 px-2 py-0.5 rounded-full text-xs font-bold ${isSelected ? 'bg-blue-500' : 'bg-blue-100 text-blue-700'}`}>{cluster.points}</span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default ClusterScatterPlot;
