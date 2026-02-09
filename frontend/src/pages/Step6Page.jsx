import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  sessionAPI,
  exportAPI,
  apiKeyManager,
  findingsAPI
} from '../services/api';
import { PageHeader } from '../components/common';
import ApiKeyPrompt from '../components/common/ApiKeyPrompt';
import { WikiLinkMarkdown, RelatedSections } from '../components/common/WikiLinkMarkdown';
import { extractApiError } from '../utils';
import {
  CompanyProfileTab,
  CrispDmTab,
  BusinessCaseTab,
  CostsTab,
  SwotTab,
  BriefingTab,
  IdeasTab,
  PrioritizationTab,
  TranscriptsTab,
  ExportTab,
} from '../components/step6';

const ALL_TABS = [
  { id: 'company_profile', icon: 'building', color: 'blue' },
  { id: 'crisp_dm', icon: 'clipboard', color: 'green' },
  { id: 'business_case', icon: 'calculator', color: 'orange' },
  { id: 'costs', icon: 'currency', color: 'red' },
  { id: 'swot', icon: 'grid', color: 'amber' },
  { id: 'briefing', icon: 'document', color: 'indigo' },
  { id: 'ideas', icon: 'lightbulb', color: 'yellow' },
  { id: 'prioritization', icon: 'star', color: 'purple' },
  { id: 'transcripts', icon: 'chat', color: 'gray' },
  { id: 'export', icon: 'download', color: 'emerald' },
];

// Role-based tab ordering (P5 / DP6)
// business_owner: business impact first; technical_advisor: technical detail first
const TAB_ORDER_BY_ROLE = {
  consultant: null, // default order
  business_owner: ['swot', 'business_case', 'company_profile', 'briefing', 'costs',
    'crisp_dm', 'prioritization', 'ideas', 'transcripts', 'export'],
  technical_advisor: ['crisp_dm', 'costs', 'briefing', 'business_case', 'company_profile',
    'swot', 'ideas', 'prioritization', 'transcripts', 'export'],
};

const Step6Page = () => {
  const { t, i18n } = useTranslation();
  const { sessionUuid } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [session, setSession] = useState(null);
  const [allFindings, setAllFindings] = useState(null);

  // Active tab state
  const [activeTab, setActiveTab] = useState('company_profile');

  // Cross-references
  const [crossReferences, setCrossReferences] = useState({});
  const [crossRefLoading, setCrossRefLoading] = useState(false);

  // Generation states
  const [swotLoading, setSwotLoading] = useState(false);
  const [swotError, setSwotError] = useState(null);
  const [briefingLoading, setBriefingLoading] = useState(false);
  const [briefingError, setBriefingError] = useState(null);
  const [exporting, setExporting] = useState(false);

  // API key prompt
  const [showApiKeyPrompt, setShowApiKeyPrompt] = useState(false);

  // Role-based tab ordering (P5 / DP6)
  const TABS = useMemo(() => {
    const role = session?.user_role;
    const order = role && TAB_ORDER_BY_ROLE[role];
    if (!order) return ALL_TABS;
    const tabMap = Object.fromEntries(ALL_TABS.map(t => [t.id, t]));
    return order.map(id => tabMap[id]).filter(Boolean);
  }, [session?.user_role]);
  const [pendingAction, setPendingAction] = useState(null);

  useEffect(() => {
    loadAllData();
  }, [sessionUuid]);

  const loadAllData = async () => {
    setLoading(true);
    try {
      // Load session
      const sessionRes = await sessionAPI.get(sessionUuid);
      setSession(sessionRes.data);

      // Load all findings from the new endpoint
      const findingsRes = await findingsAPI.getAll(sessionUuid);
      setAllFindings(findingsRes.data);

      // Auto-generate SWOT and Technical Briefing if they don't exist and API key is available
      const hasSwot = findingsRes.data?.analysis?.swot_analysis?.text;
      const hasBriefing = findingsRes.data?.analysis?.technical_briefing?.text;

      if (apiKeyManager.isSet()) {
        const language = t('common.languageCode') || 'en';

        // Auto-generate SWOT if missing
        if (!hasSwot) {
          setSwotLoading(true);
          try {
            await exportAPI.generateSwotAnalysis(sessionUuid, { language });
          } catch (swotErr) {
            console.error('Auto-generate SWOT failed:', swotErr);
          } finally {
            setSwotLoading(false);
          }
        }

        // Auto-generate Technical Briefing if missing
        if (!hasBriefing) {
          setBriefingLoading(true);
          try {
            await exportAPI.generateTransitionBriefing(sessionUuid, { language });
          } catch (briefingErr) {
            console.error('Auto-generate briefing failed:', briefingErr);
          } finally {
            setBriefingLoading(false);
          }
        }

        // Reload findings if we generated anything
        if (!hasSwot || !hasBriefing) {
          const updatedFindings = await findingsAPI.getAll(sessionUuid);
          setAllFindings(updatedFindings.data);
        }

        // Extract and load cross-references
        setCrossRefLoading(true);
        try {
          await exportAPI.extractCrossReferences(sessionUuid, {
            language,
          });
          const crossRefRes = await exportAPI.getCrossReferences(sessionUuid);
          setCrossReferences(crossRefRes.data?.cross_references || {});
        } catch (crossRefErr) {
          console.error('Cross-reference extraction failed:', crossRefErr);
        } finally {
          setCrossRefLoading(false);
        }
      } else {
        // Try loading existing cross-references even without API key
        try {
          const crossRefRes = await exportAPI.getCrossReferences(sessionUuid);
          setCrossReferences(crossRefRes.data?.cross_references || {});
        } catch (crossRefErr) {
          // Cross-references not available yet — that's fine
        }
      }

    } catch (err) {
      setError(extractApiError(err, i18n.language));
    } finally {
      setLoading(false);
    }
  };

  const handleNavigate = useCallback((tab, subTarget) => {
    setActiveTab(tab);
    // If subTarget provided, scroll to that section
    if (subTarget) {
      setTimeout(() => {
        const element = document.getElementById(`finding-${subTarget}`);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 100);
    }
  }, []);

  const handleGenerateBriefing = async () => {
    if (!apiKeyManager.isSet()) {
      setPendingAction('generate_briefing');
      setShowApiKeyPrompt(true);
      return;
    }

    setBriefingLoading(true);
    setBriefingError(null);

    try {
      await exportAPI.generateTransitionBriefing(sessionUuid, {
        language: t('common.languageCode') || 'en',
      });
      // Reload findings to get updated briefing
      const findingsRes = await findingsAPI.getAll(sessionUuid);
      setAllFindings(findingsRes.data);
    } catch (err) {
      setBriefingError(extractApiError(err, i18n.language));
    } finally {
      setBriefingLoading(false);
    }
  };

  const handleGenerateSwot = async () => {
    if (!apiKeyManager.isSet()) {
      setPendingAction('generate_swot');
      setShowApiKeyPrompt(true);
      return;
    }

    setSwotLoading(true);
    setSwotError(null);

    try {
      await exportAPI.generateSwotAnalysis(sessionUuid, {
        language: t('common.languageCode') || 'en',
      });
      // Reload findings to get updated SWOT
      const findingsRes = await findingsAPI.getAll(sessionUuid);
      setAllFindings(findingsRes.data);
    } catch (err) {
      setSwotError(extractApiError(err, i18n.language));
    } finally {
      setSwotLoading(false);
    }
  };

  const handleExportPDF = async () => {
    setExporting(true);
    try {
      const response = await exportAPI.generatePDF(sessionUuid);

      // Create download link
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `consultation-report-${sessionUuid.slice(0, 8)}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(extractApiError(err, i18n.language));
    } finally {
      setExporting(false);
    }
  };

  const handleApiKeySet = () => {
    setShowApiKeyPrompt(false);
    if (pendingAction === 'generate_briefing') {
      handleGenerateBriefing();
    } else if (pendingAction === 'generate_swot') {
      handleGenerateSwot();
    }
    setPendingAction(null);
  };

  // Check completeness for status indicators
  const hasCompanyProfile = allFindings?.company_info?.structured_profile || allFindings?.company_info?.raw_info?.length > 0 || !!allFindings?.maturity;
  const hasCrispDm = allFindings?.crisp_dm?.business_objectives?.text || allFindings?.crisp_dm?.situation_assessment?.text || allFindings?.crisp_dm?.ai_goals?.text || allFindings?.crisp_dm?.project_plan?.text;
  const hasBusinessCase = allFindings?.business_case?.classification?.text || allFindings?.business_case?.calculation?.text || allFindings?.business_case?.validation_questions?.text || allFindings?.business_case?.management_pitch?.text;
  const hasCosts = allFindings?.costs?.complexity?.text || allFindings?.costs?.tco?.text || allFindings?.costs?.initial_investment?.text;
  const hasSwot = !!allFindings?.analysis?.swot_analysis?.text;
  const hasBriefing = !!allFindings?.analysis?.technical_briefing?.text;
  const hasIdeas = allFindings?.brainstorming?.total_ideas > 0;
  const hasPrioritization = allFindings?.prioritization?.total_votes > 0;
  const hasTranscripts = allFindings?.transcripts?.consultation?.length > 0 || allFindings?.transcripts?.business_case?.length > 0 || allFindings?.transcripts?.cost_estimation?.length > 0;

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">{t('common.loading')}</p>
      </div>
    );
  }

  const renderTabIcon = (iconName) => {
    const icons = {
      building: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />,
      chart: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />,
      clipboard: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />,
      calculator: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />,
      currency: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />,
      grid: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />,
      document: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />,
      download: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />,
      lightbulb: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />,
      star: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />,
      chat: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />,
    };
    return icons[iconName] || icons.document;
  };

  const getTabStatus = (tabId) => {
    switch (tabId) {
      case 'company_profile': return hasCompanyProfile;
      case 'crisp_dm': return hasCrispDm;
      case 'business_case': return hasBusinessCase;
      case 'costs': return hasCosts;
      case 'swot': return hasSwot;
      case 'briefing': return hasBriefing;
      case 'ideas': return hasIdeas;
      case 'prioritization': return hasPrioritization;
      case 'transcripts': return hasTranscripts;
      case 'export': return true;
      default: return false;
    }
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case 'company_profile':
        return <CompanyProfileTab findings={allFindings} session={session} t={t} onNavigate={handleNavigate} crossReferences={crossReferences} />;
      case 'crisp_dm':
        return <CrispDmTab findings={allFindings} t={t} onNavigate={handleNavigate} crossReferences={crossReferences} />;
      case 'business_case':
        return <BusinessCaseTab findings={allFindings} t={t} onNavigate={handleNavigate} crossReferences={crossReferences} />;
      case 'costs':
        return <CostsTab findings={allFindings} t={t} onNavigate={handleNavigate} crossReferences={crossReferences} />;
      case 'swot':
        return (
          <SwotTab
            findings={allFindings}
            t={t}
            onNavigate={handleNavigate}
            onGenerate={handleGenerateSwot}
            loading={swotLoading}
            error={swotError}
            crossReferences={crossReferences}
          />
        );
      case 'briefing':
        return (
          <BriefingTab
            findings={allFindings}
            t={t}
            onNavigate={handleNavigate}
            onGenerate={handleGenerateBriefing}
            loading={briefingLoading}
            error={briefingError}
            crossReferences={crossReferences}
          />
        );
      case 'ideas':
        return <IdeasTab findings={allFindings} t={t} />;
      case 'prioritization':
        return <PrioritizationTab findings={allFindings} t={t} />;
      case 'transcripts':
        return <TranscriptsTab findings={allFindings} t={t} />;
      case 'export':
        return (
          <ExportTab
            t={t}
            onExportPDF={handleExportPDF}
            exporting={exporting}
            hasAllFindings={{
              hasCompanyProfile, hasCrispDm,
              hasBusinessCase, hasCosts, hasSwot, hasBriefing,
              hasIdeas, hasPrioritization, hasTranscripts
            }}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <PageHeader
        title={t('step6.title')}
        subtitle={t('step6.subtitle')}
        sessionUuid={sessionUuid}
      />

      {/* Main Content */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="bg-white rounded-lg shadow-md mb-6">
          <div className="border-b border-gray-200 overflow-x-auto">
            <nav className="flex -mb-px min-w-max">
              {TABS.map((tab) => {
                const isActive = activeTab === tab.id;
                const isComplete = getTabStatus(tab.id);
                const colorClasses = {
                  blue: isActive ? 'border-blue-500 text-blue-600' : '',
                  purple: isActive ? 'border-purple-500 text-purple-600' : '',
                  green: isActive ? 'border-green-500 text-green-600' : '',
                  orange: isActive ? 'border-orange-500 text-orange-600' : '',
                  red: isActive ? 'border-red-500 text-red-600' : '',
                  amber: isActive ? 'border-amber-500 text-amber-600' : '',
                  indigo: isActive ? 'border-indigo-500 text-indigo-600' : '',
                  emerald: isActive ? 'border-emerald-500 text-emerald-600' : '',
                  yellow: isActive ? 'border-yellow-500 text-yellow-600' : '',
                  gray: isActive ? 'border-gray-500 text-gray-600' : '',
                };
                return (
                  <button
                    key={tab.id}
                    onClick={() => handleNavigate(tab.id)}
                    className={`
                      flex items-center gap-2 px-4 py-3 border-b-2 font-medium text-sm transition-colors whitespace-nowrap
                      ${isActive
                        ? colorClasses[tab.color]
                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                      }
                    `}
                  >
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      {renderTabIcon(tab.icon)}
                    </svg>
                    <span className="hidden sm:inline">{t(`step6.tabs.${tab.id}`)}</span>
                    {isComplete && tab.id !== 'export' && (
                      <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </button>
                );
              })}
            </nav>
          </div>

          {/* Tab Content */}
          <div className="p-6">
            {renderTabContent()}
          </div>
        </div>
      </div>

      {/* API Key Prompt Modal */}
      <ApiKeyPrompt
        isOpen={showApiKeyPrompt}
        onClose={() => setShowApiKeyPrompt(false)}
        onApiKeySet={handleApiKeySet}
      />
    </div>
  );
};

export default Step6Page;
