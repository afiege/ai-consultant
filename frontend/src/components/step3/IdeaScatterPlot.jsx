import React, { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, ReferenceLine, ReferenceArea, Label,
} from 'recharts';
import { levelToNumber } from './helpers';

/** Interactive scatter chart for idea-level prioritization (Phase 2). */
const IdeaScatterPlot = ({ ideas, onIdeaClick, selectedIdeaId, ideaVotes }) => {
  const { t } = useTranslation();
  const [hoveredId, setHoveredId] = useState(null);
  const [recentlyClicked, setRecentlyClicked] = useState(null);
  const [showVoteToast, setShowVoteToast] = useState(false);

  const scatterData = useMemo(() => {
    const seededRandom = (seed) => {
      const x = Math.sin(seed * 9301 + 49297) * 49297;
      return x - Math.floor(x);
    };
    return ideas.map((idea, index) => ({
      ...idea,
      x: levelToNumber(idea.implementation_effort),
      y: levelToNumber(idea.business_impact),
      xJitter: levelToNumber(idea.implementation_effort) + (seededRandom(idea.id) - 0.5) * 0.4,
      yJitter: levelToNumber(idea.business_impact) + (seededRandom(idea.id * 7) - 0.5) * 0.4,
      votes: ideaVotes[idea.id] || 0,
      shortLabel: `#${index + 1}`,
    }));
  }, [ideas, ideaVotes]);

  const hasEffortImpactData = ideas.some(i => i.implementation_effort && i.business_impact);
  if (!hasEffortImpactData || ideas.length === 0) return null;

  const handleIdeaClick = (ideaId) => {
    setRecentlyClicked(ideaId);
    setShowVoteToast(true);
    setTimeout(() => setRecentlyClicked(null), 400);
    setTimeout(() => setShowVoteToast(false), 1500);
    onIdeaClick && onIdeaClick(ideaId);
  };

  const isMobile = typeof window !== 'undefined' && window.innerWidth < 640;
  const baseRadius = isMobile ? 16 : 12;
  const hoverRadius = isMobile ? 20 : 16;
  const clickRadius = isMobile ? 24 : 20;

  const getIdeaColor = (votes) => {
    if (votes >= 2) return '#7c3aed';
    if (votes === 1) return '#a78bfa';
    return '#8b5cf6';
  };

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
            <p className="text-xs text-gray-500 italic mt-3 pt-3 border-t border-gray-100">"{data.impact_rationale}"</p>
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
      {showVoteToast && (
        <div className="absolute top-4 right-4 bg-purple-600 text-white px-4 py-2.5 rounded-lg shadow-xl flex items-center gap-2 z-50 animate-pulse">
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
          </svg>
          <span className="font-medium text-sm">{t('step3.scatter.voteAdded', 'Vote added!')}</span>
        </div>
      )}

      <h3 className="text-xl font-bold text-gray-900 mb-1">{t('step3.ideaScatter.title', 'Idea Prioritization Matrix')}</h3>
      <p className="text-sm text-gray-600 mb-5">{t('step3.ideaScatter.subtitle', 'Click on ideas to vote. Position shows effort vs impact.')}</p>

      <div className="relative">
        <ResponsiveContainer width="100%" height={isMobile ? 400 : 360}>
          <ScatterChart margin={{ top: 30, right: 30, bottom: 50, left: 50 }}>
            <defs>
              <linearGradient id="ideaQuickWinsGradient" x1="0" y1="1" x2="0" y2="0">
                <stop offset="0%" stopColor="#f3e8ff" stopOpacity="0.7"/><stop offset="100%" stopColor="#f3e8ff" stopOpacity="0.3"/>
              </linearGradient>
              <linearGradient id="ideaStrategicGradient" x1="0" y1="1" x2="0" y2="0">
                <stop offset="0%" stopColor="#ede9fe" stopOpacity="0.6"/><stop offset="100%" stopColor="#ede9fe" stopOpacity="0.2"/>
              </linearGradient>
              <linearGradient id="ideaAvoidGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#fef2f2" stopOpacity="0.6"/><stop offset="100%" stopColor="#fef2f2" stopOpacity="0.2"/>
              </linearGradient>
              <linearGradient id="ideaFillInGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f9fafb" stopOpacity="0.5"/><stop offset="100%" stopColor="#f9fafb" stopOpacity="0.2"/>
              </linearGradient>
            </defs>

            <ReferenceArea x1={0.5} x2={2} y1={2} y2={3.5} fill="url(#ideaQuickWinsGradient)" fillOpacity={1} />
            <ReferenceArea x1={2} x2={3.5} y1={2} y2={3.5} fill="url(#ideaStrategicGradient)" fillOpacity={1} />
            <ReferenceArea x1={2} x2={3.5} y1={0.5} y2={2} fill="url(#ideaAvoidGradient)" fillOpacity={1} />
            <ReferenceArea x1={0.5} x2={2} y1={0.5} y2={2} fill="url(#ideaFillInGradient)" fillOpacity={1} />

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

            <Tooltip content={<IdeaTooltip />} />

            <Scatter data={scatterData} onClick={(data) => handleIdeaClick(data.id)} cursor="pointer"
              onMouseEnter={(data) => setHoveredId(data?.id)} onMouseLeave={() => setHoveredId(null)}>
              {scatterData.map((entry, index) => {
                const isHovered = hoveredId === entry.id;
                const isSelected = selectedIdeaId === entry.id;
                const isRecentClick = recentlyClicked === entry.id;
                const hasVotes = entry.votes > 0;
                return (
                  <Cell key={`cell-${index}`}
                    fill={getIdeaColor(entry.votes)}
                    stroke={isRecentClick ? '#10b981' : isHovered ? '#7c3aed' : isSelected ? '#5b21b6' : '#ffffff'}
                    strokeWidth={isRecentClick ? 4 : isHovered || isSelected ? 3 : 2}
                    r={isRecentClick ? clickRadius : isHovered ? hoverRadius : hasVotes ? baseRadius + 3 : baseRadius}
                    style={{
                      filter: isHovered || isRecentClick ? 'drop-shadow(0 4px 8px rgba(124,58,237,0.35))' : 'drop-shadow(0 2px 4px rgba(0,0,0,0.1))',
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
        <div className="absolute bottom-16 left-14 text-base text-purple-800 font-bold bg-gradient-to-br from-purple-100 to-violet-100 px-3 py-1.5 rounded-lg shadow border-2 border-purple-400">⭐ {t('step3.scatter.quadrantQuickWins', 'Quick Wins')}</div>
        <div className="absolute bottom-16 right-8 text-sm text-purple-700 font-semibold bg-purple-50 px-2.5 py-1 rounded border border-purple-300 shadow-sm">🎯 {t('step3.scatter.quadrantStrategic', 'Strategic')}</div>
      </div>

      <div className="mt-6 pt-4 border-t border-gray-200">
        <p className="text-sm font-medium text-gray-700 mb-3">{t('step3.ideaScatter.selectIdea', 'Select an idea to vote:')}</p>
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {scatterData.map((idea, index) => {
            const isSelected = selectedIdeaId === idea.id;
            const isHovered = hoveredId === idea.id;
            return (
              <button key={idea.id} onClick={() => handleIdeaClick(idea.id)}
                onMouseEnter={() => setHoveredId(idea.id)} onMouseLeave={() => setHoveredId(null)}
                className={`w-full text-left flex items-start gap-3 px-4 py-3 rounded-lg text-sm transition-all duration-200 border-2 min-h-[44px] ${
                  isSelected ? 'bg-purple-600 text-white border-purple-600 shadow-lg'
                    : isHovered ? 'bg-purple-50 text-gray-800 border-purple-300 shadow-md'
                    : 'bg-white text-gray-700 border-gray-200 hover:border-purple-200 hover:shadow-md'}`}>
                <span className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${isSelected ? 'bg-purple-500 text-white' : 'bg-purple-100 text-purple-700'}`}>{index + 1}</span>
                <span className="flex-1 line-clamp-2">{idea.content}</span>
                {idea.votes > 0 && (
                  <span className={`flex-shrink-0 px-2 py-0.5 rounded-full text-xs font-bold ${isSelected ? 'bg-purple-500' : 'bg-purple-100 text-purple-700'}`}>{idea.votes}</span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default IdeaScatterPlot;
