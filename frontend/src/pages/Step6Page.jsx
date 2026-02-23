import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  sessionAPI,
  exportAPI,
  apiKeyManager,
  findingsAPI
} from '../services/api';
import { PageHeader } from '../components/common';
import ApiKeyPrompt from '../components/common/ApiKeyPrompt';
import { WikiLinkMarkdown } from '../components/common/WikiLinkMarkdown';

const TABS = [
  { id: 'company_profile', icon: 'building', color: 'blue' },
  { id: 'crisp_dm', icon: 'clipboard', color: 'green' },
  { id: 'business_case', icon: 'calculator', color: 'orange' },
  { id: 'costs', icon: 'currency', color: 'red' },
  { id: 'swot', icon: 'grid', color: 'amber' },
  { id: 'briefing', icon: 'document', color: 'indigo' },
  { id: 'tic', icon: 'canvas', color: 'teal' },
  { id: 'ideas', icon: 'lightbulb', color: 'yellow' },
  { id: 'prioritization', icon: 'star', color: 'purple' },
  { id: 'transcripts', icon: 'chat', color: 'gray' },
  { id: 'export', icon: 'download', color: 'emerald' },
];

const Step6Page = () => {
  const { t } = useTranslation();
  const { sessionUuid } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [session, setSession] = useState(null);
  const [allFindings, setAllFindings] = useState(null);

  // Active tab state
  const [activeTab, setActiveTab] = useState('company_profile');

  // Generation states
  const [swotLoading, setSwotLoading] = useState(false);
  const [swotError, setSwotError] = useState(null);
  const [briefingLoading, setBriefingLoading] = useState(false);
  const [briefingError, setBriefingError] = useState(null);
  const [exporting, setExporting] = useState(false);

  // API key prompt
  const [showApiKeyPrompt, setShowApiKeyPrompt] = useState(false);
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
      }

    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load data');
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
      setBriefingError(err.response?.data?.detail || 'Failed to generate briefing');
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
      setSwotError(err.response?.data?.detail || 'Failed to generate SWOT analysis');
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
      setError(err.response?.data?.detail || 'Failed to export PDF');
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
  const hasTic = hasIdeas || hasPrioritization || hasCrispDm || hasBusinessCase;
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
      canvas: <><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1V5z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V5z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" /></>,
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
      case 'tic': return hasTic;
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
        return <CompanyProfileTab findings={allFindings} session={session} t={t} onNavigate={handleNavigate} />;
      case 'crisp_dm':
        return <CrispDmTab findings={allFindings} t={t} onNavigate={handleNavigate} />;
      case 'business_case':
        return <BusinessCaseTab findings={allFindings} t={t} onNavigate={handleNavigate} />;
      case 'costs':
        return <CostsTab findings={allFindings} t={t} onNavigate={handleNavigate} />;
      case 'swot':
        return (
          <SwotTab
            findings={allFindings}
            t={t}
            onNavigate={handleNavigate}
            onGenerate={handleGenerateSwot}
            loading={swotLoading}
            error={swotError}
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
          />
        );
      case 'tic':
        return <TicCanvasTab findings={allFindings} t={t} />;
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
                  teal: isActive ? 'border-teal-500 text-teal-600' : '',
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

// Tab Content Components

const CompanyProfileTab = ({ findings, session, t, onNavigate }) => {
  const structuredProfile = findings?.company_info?.structured_profile;
  const rawInfo = findings?.company_info?.raw_info || [];
  const maturity = findings?.maturity;

  if (!structuredProfile && rawInfo.length === 0 && !maturity) {
    return <EmptyState message={t('step6.incomplete.companyProfile')} />;
  }

  const getScoreColor = (score) => {
    if (score < 2) return 'bg-red-500';
    if (score < 3) return 'bg-orange-500';
    if (score < 4) return 'bg-yellow-500';
    if (score < 5) return 'bg-blue-500';
    return 'bg-green-500';
  };

  // Helper to render a profile field
  const ProfileField = ({ label, value }) => {
    if (!value) return null;
    const displayValue = Array.isArray(value) ? value.join(', ') : value;
    return (
      <div className="py-2 border-b border-gray-100 last:border-0">
        <dt className="text-sm font-medium text-gray-500">{label}</dt>
        <dd className="mt-1 text-sm text-gray-900">{displayValue}</dd>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Company Name Header */}
      <h3 className="text-lg font-semibold text-gray-900">
        {structuredProfile?.name || session?.company_name || t('step6.unknownCompany')}
      </h3>

      {/* Structured Profile Display */}
      {structuredProfile && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Basic Information */}
          <div className="bg-blue-50 rounded-lg p-4">
            <h4 className="font-medium text-blue-800 mb-3">{t('companyProfile.sections.basic')}</h4>
            <dl>
              <ProfileField label={t('companyProfile.fields.industry')} value={structuredProfile.industry} />
              <ProfileField label={t('companyProfile.fields.subIndustry')} value={structuredProfile.sub_industry} />
              <ProfileField label={t('companyProfile.fields.employeeCount')} value={structuredProfile.employee_count} />
              <ProfileField label={t('companyProfile.fields.foundingYear')} value={structuredProfile.founding_year} />
              <ProfileField label={t('companyProfile.fields.ownership')} value={structuredProfile.ownership} />
            </dl>
          </div>

          {/* Location & Markets */}
          <div className="bg-blue-50 rounded-lg p-4">
            <h4 className="font-medium text-blue-800 mb-3">{t('companyProfile.sections.location')}</h4>
            <dl>
              <ProfileField label={t('companyProfile.fields.headquarters')} value={structuredProfile.headquarters} />
              <ProfileField label={t('companyProfile.fields.otherLocations')} value={structuredProfile.other_locations} />
              <ProfileField label={t('companyProfile.fields.marketsServed')} value={structuredProfile.markets_served} />
            </dl>
          </div>

          {/* Financial KPIs */}
          {(structuredProfile.annual_revenue || structuredProfile.profit_margin || structuredProfile.growth_rate) && (
            <div className="bg-blue-50 rounded-lg p-4">
              <h4 className="font-medium text-blue-800 mb-3">{t('companyProfile.sections.financial')}</h4>
              <dl>
                <ProfileField label={t('companyProfile.fields.annualRevenue')} value={structuredProfile.annual_revenue} />
                <ProfileField label={t('companyProfile.fields.profitMargin')} value={structuredProfile.profit_margin} />
                <ProfileField label={t('companyProfile.fields.growthRate')} value={structuredProfile.growth_rate} />
                <ProfileField label={t('companyProfile.fields.cashFlowStatus')} value={structuredProfile.cash_flow_status} />
              </dl>
            </div>
          )}

          {/* Operational KPIs */}
          {(structuredProfile.production_volume || structuredProfile.capacity_utilization) && (
            <div className="bg-blue-50 rounded-lg p-4">
              <h4 className="font-medium text-blue-800 mb-3">{t('companyProfile.sections.operational')}</h4>
              <dl>
                <ProfileField label={t('companyProfile.fields.productionVolume')} value={structuredProfile.production_volume} />
                <ProfileField label={t('companyProfile.fields.capacityUtilization')} value={structuredProfile.capacity_utilization} />
              </dl>
            </div>
          )}

          {/* Business Model */}
          <div className="bg-blue-50 rounded-lg p-4">
            <h4 className="font-medium text-blue-800 mb-3">{t('companyProfile.sections.business')}</h4>
            <dl>
              <ProfileField label={t('companyProfile.fields.coreBusiness')} value={structuredProfile.core_business} />
              <ProfileField label={t('companyProfile.fields.productsServices')} value={structuredProfile.products_services} />
              <ProfileField label={t('companyProfile.fields.customerSegments')} value={structuredProfile.customer_segments} />
              <ProfileField label={t('companyProfile.fields.keyProcesses')} value={structuredProfile.key_processes} />
            </dl>
          </div>

          {/* Technology & Systems */}
          {(structuredProfile.current_systems || structuredProfile.data_sources || structuredProfile.automation_level) && (
            <div className="bg-blue-50 rounded-lg p-4">
              <h4 className="font-medium text-blue-800 mb-3">{t('companyProfile.sections.technology')}</h4>
              <dl>
                <ProfileField label={t('companyProfile.fields.currentSystems')} value={structuredProfile.current_systems} />
                <ProfileField label={t('companyProfile.fields.dataSources')} value={structuredProfile.data_sources} />
                <ProfileField label={t('companyProfile.fields.automationLevel')} value={structuredProfile.automation_level} />
              </dl>
            </div>
          )}

          {/* Challenges & Goals */}
          {(structuredProfile.pain_points || structuredProfile.digitalization_goals || structuredProfile.competitive_pressures) && (
            <div className="bg-blue-50 rounded-lg p-4 lg:col-span-2">
              <h4 className="font-medium text-blue-800 mb-3">{t('companyProfile.sections.challenges')}</h4>
              <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-4">
                <ProfileField label={t('companyProfile.fields.painPoints')} value={structuredProfile.pain_points} />
                <ProfileField label={t('companyProfile.fields.digitalizationGoals')} value={structuredProfile.digitalization_goals} />
                <ProfileField label={t('companyProfile.fields.competitivePressures')} value={structuredProfile.competitive_pressures} />
              </dl>
            </div>
          )}
        </div>
      )}

      {/* Maturity Assessment Section */}
      {maturity && (
        <div className="bg-purple-50 rounded-lg p-4">
          <h4 className="font-medium text-purple-800 mb-4">{t('step6.sections.maturity')}</h4>
          <div className="flex items-center gap-4 mb-4">
            <span className={`px-4 py-2 rounded-full text-white font-bold text-lg ${getScoreColor(maturity.overall_score)}`}>
              {maturity.overall_score?.toFixed(1)}/6
            </span>
            <span className="text-xl font-medium text-gray-700">{maturity.maturity_level}</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <DimensionScore label={t('step6.maturity.resources')} score={maturity.resources_score} />
            <DimensionScore label={t('step6.maturity.infoSystems')} score={maturity.information_systems_score} />
            <DimensionScore label={t('step6.maturity.culture')} score={maturity.culture_score} />
            <DimensionScore label={t('step6.maturity.orgStructure')} score={maturity.organizational_structure_score} />
          </div>
        </div>
      )}

      {/* Raw Info Fallback (if no structured profile but has raw info) */}
      {!structuredProfile && rawInfo.length > 0 && (
        <div className="space-y-4">
          <h4 className="font-medium text-gray-800">{t('step6.rawInfo')}</h4>
          {rawInfo.map((info, index) => (
            <div key={index} className="bg-gray-50 rounded-lg p-4">
              <p className="text-sm font-medium text-gray-600 mb-1">{info.info_type}</p>
              <p className="text-gray-700 whitespace-pre-wrap">{info.content}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const DimensionScore = ({ label, score }) => (
  <div className="bg-white/50 rounded-lg p-3">
    <p className="text-sm text-gray-600 mb-1">{label}</p>
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-200 rounded-full h-2">
        <div
          className="bg-purple-500 h-2 rounded-full"
          style={{ width: `${(score / 6) * 100}%` }}
        />
      </div>
      <span className="font-medium text-gray-700">{score?.toFixed(1)}</span>
    </div>
  </div>
);

const CrispDmTab = ({ findings, t, onNavigate }) => {
  const crisp = findings?.crisp_dm;

  const sections = [
    { id: 'business_objectives', key: 'objectives', data: crisp?.business_objectives },
    { id: 'situation_assessment', key: 'situation', data: crisp?.situation_assessment },
    { id: 'ai_goals', key: 'aiGoals', data: crisp?.ai_goals },
    { id: 'project_plan', key: 'projectPlan', data: crisp?.project_plan },
  ];

  // Check if any section has data with text content
  const hasAnyData = sections.some(section => section.data?.text);

  if (!hasAnyData) {
    return <EmptyState message={t('step6.incomplete.crispDm')} />;
  }

  return (
    <div className="space-y-6">
      {sections.map(section => section.data?.text && (
        <div key={section.id} id={`finding-${section.id}`} className="bg-green-50 rounded-lg p-4">
          <h4 className="font-medium text-green-800 mb-2">{t(`step6.crispDm.${section.key}`)}</h4>
          <WikiLinkMarkdown
            content={section.data.text}
            onNavigate={onNavigate}
            className="text-green-700"
          />
        </div>
      ))}
    </div>
  );
};

const BusinessCaseTab = ({ findings, t, onNavigate }) => {
  const bc = findings?.business_case;

  const sections = [
    { id: 'classification', key: 'classification', data: bc?.classification },
    { id: 'calculation', key: 'calculation', data: bc?.calculation },
    { id: 'validation_questions', key: 'validation', data: bc?.validation_questions },
    { id: 'management_pitch', key: 'pitch', data: bc?.management_pitch },
  ];

  const hasAnyData = sections.some(section => section.data?.text);

  if (!hasAnyData) {
    return <EmptyState message={t('step6.incomplete.businessCase')} />;
  }

  return (
    <div className="space-y-6">
      {sections.map(section => section.data?.text && (
        <div key={section.id} id={`finding-${section.id}`} className="bg-orange-50 rounded-lg p-4">
          <h4 className="font-medium text-orange-800 mb-2">{t(`step6.businessCase.${section.key}`)}</h4>
          <WikiLinkMarkdown
            content={section.data.text}
            onNavigate={onNavigate}
            className="text-orange-700"
          />
        </div>
      ))}
    </div>
  );
};

const CostsTab = ({ findings, t, onNavigate }) => {
  const costs = findings?.costs;

  const sections = [
    { id: 'complexity', key: 'complexity', data: costs?.complexity },
    { id: 'initial_investment', key: 'initial', data: costs?.initial_investment },
    { id: 'recurring_costs', key: 'recurring', data: costs?.recurring_costs },
    { id: 'maintenance', key: 'maintenance', data: costs?.maintenance },
    { id: 'tco', key: 'tco', data: costs?.tco },
    { id: 'cost_drivers', key: 'drivers', data: costs?.cost_drivers },
    { id: 'optimization', key: 'optimization', data: costs?.optimization },
    { id: 'roi_analysis', key: 'roi', data: costs?.roi_analysis },
  ];

  const hasAnyData = sections.some(section => section.data?.text);

  if (!hasAnyData) {
    return <EmptyState message={t('step6.incomplete.costs')} />;
  }

  return (
    <div className="space-y-6">
      {sections.map(section => section.data?.text && (
        <div key={section.id} id={`finding-${section.id}`} className="bg-red-50 rounded-lg p-4">
          <h4 className="font-medium text-red-800 mb-2">{t(`step6.costs.${section.key}`)}</h4>
          <WikiLinkMarkdown
            content={section.data.text}
            onNavigate={onNavigate}
            className="text-red-700"
          />
        </div>
      ))}
    </div>
  );
};

const SwotTab = ({ findings, t, onNavigate, onGenerate, loading, error }) => {
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
            />
          </div>
        </div>
      )}
    </div>
  );
};

const BriefingTab = ({ findings, t, onNavigate, onGenerate, loading, error }) => {
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
            />
          </div>
        </div>
      )}
    </div>
  );
};

// Helper: extract a named section from markdown text (mirrors _extract_section in pdf_generator.py)
const extractSection = (text, name) => {
  if (!text) return '';
  const pattern = new RegExp(`(?:^|\\n)#{1,3}\\s*${name}\\s*\\n([\\s\\S]*?)(?=\\n#{1,3}\\s|$)`, 'i');
  const m = text.match(pattern);
  return m ? m[1].trim() : '';
};

const truncate = (text, maxLen) => {
  if (!text) return '';
  return text.length > maxLen ? text.slice(0, maxLen) + '…' : text;
};

const TicCanvasTab = ({ findings, t }) => {
  // Build scored ideas list — same logic as pdf_generator.py _collect_data()
  const ideaScores = {};
  findings?.prioritization?.results?.forEach(vote => {
    if (!vote.idea_id || !vote.idea_content) return;
    if (!ideaScores[vote.idea_id]) {
      ideaScores[vote.idea_id] = { content: vote.idea_content, score: 0 };
    }
    ideaScores[vote.idea_id].score += vote.score || 0;
  });
  const rankedIdeas = Object.values(ideaScores).sort((a, b) => b.score - a.score);

  // Fallback top idea if no prioritization
  const topIdea = rankedIdeas[0]?.content
    || findings?.brainstorming?.sheets?.[0]?.ideas?.[0]?.content
    || null;

  // Findings — identical keys as PDF template
  const businessObjectives = findings?.crisp_dm?.business_objectives?.text;
  const aiGoals            = findings?.crisp_dm?.ai_goals?.text;
  const situationAssessment = findings?.crisp_dm?.situation_assessment?.text;
  const bcClassification   = findings?.business_case?.classification?.text;
  const bcPitch            = findings?.business_case?.management_pitch?.text;
  const projectPlan        = findings?.crisp_dm?.project_plan?.text;
  const firstSteps         = extractSection(findings?.analysis?.technical_briefing?.text || '', 'First Steps');

  const hasAnyData = topIdea || businessObjectives || aiGoals || bcClassification || projectPlan;

  if (!hasAnyData) {
    return <EmptyState message={t('step6.incomplete.tic')} />;
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500 italic">
        {t('step6.tic.subtitle')}
      </p>

      {/* Column axis headers */}
      <div style={{ display: 'grid', gridTemplateColumns: '40px 1fr 1fr', gap: 0 }}>
        <div />
        <div className="bg-blue-900 text-white text-center text-xs font-bold py-2 px-3 border-r border-blue-700">
          Use Cases &amp; Problems
        </div>
        <div className="bg-blue-900 text-white text-center text-xs font-bold py-2 px-3">
          Options &amp; Solutions
        </div>
      </div>

      {/* Row axis + 2×2 grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '40px 1fr 1fr', gap: 0 }}>

        {/* Row labels — vertical text */}
        <div style={{ display: 'flex', flexDirection: 'column', borderRight: '2px solid #1e3a8a' }}>
          <div className="flex-1 bg-blue-900 flex items-center justify-center"
               style={{ borderBottom: '1px solid #1d4ed8', minHeight: '120px' }}>
            <span className="text-white text-xs font-bold whitespace-nowrap"
                  style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)', letterSpacing: '0.05em' }}>
              Collect
            </span>
          </div>
          <div className="flex-1 bg-blue-900 flex items-center justify-center"
               style={{ minHeight: '120px' }}>
            <span className="text-white text-xs font-bold whitespace-nowrap"
                  style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)', letterSpacing: '0.05em' }}>
              Connect
            </span>
          </div>
        </div>

        {/* 2×2 grid with diamond overlay — col-span-2 */}
        <div className="relative" style={{ gridColumn: 'span 2', border: '2px solid #1e3a8a' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gridTemplateRows: 'auto auto' }}>

            {/* Top-left: Collect / Use Cases & Problems */}
            <div className="p-3 bg-blue-50 border-r border-b border-blue-200" style={{ minHeight: '130px' }}>
              <div className="text-xs font-bold text-blue-900 uppercase tracking-wide mb-2">
                Potential Use Cases &amp; Requirements
              </div>
              {rankedIdeas.slice(0, 4).map((idea, i) => (
                <p key={i} className="text-xs text-gray-700 mb-1">▸ {truncate(idea.content, 75)}</p>
              ))}
              {businessObjectives && (
                <p className="text-xs text-gray-500 italic mt-2">{truncate(businessObjectives, 120)}</p>
              )}
              {rankedIdeas.length === 0 && !businessObjectives && (
                <p className="text-xs text-gray-400 italic">{t('step6.tic.emptyUseCases')}</p>
              )}
            </div>

            {/* Top-right: Collect / Options & Solutions */}
            <div className="p-3 bg-blue-50 border-b border-blue-200" style={{ minHeight: '130px' }}>
              <div className="text-xs font-bold text-blue-900 uppercase tracking-wide mb-2">
                Possible Solutions &amp; Knowledge Base
              </div>
              {aiGoals && (
                <p className="text-xs text-gray-700 mb-2">{truncate(aiGoals, 280)}</p>
              )}
              {situationAssessment && (
                <p className="text-xs text-gray-500 italic">{truncate(situationAssessment, 100)}</p>
              )}
              {!aiGoals && !situationAssessment && (
                <p className="text-xs text-gray-400 italic">{t('step6.tic.emptySolutions')}</p>
              )}
            </div>

            {/* Bottom-left: Connect / Use Cases & Problems — Enriched Use Case */}
            <div className="p-3 bg-indigo-50 border-r border-blue-200" style={{ minHeight: '130px' }}>
              <div className="text-xs font-bold text-blue-900 uppercase tracking-wide mb-2">
                Enriched Use Case
              </div>
              {topIdea && (
                <p className="text-sm font-bold text-blue-900 mb-2">{truncate(topIdea, 90)}</p>
              )}
              {bcClassification ? (
                <p className="text-xs text-gray-700">{truncate(bcClassification, 220)}</p>
              ) : businessObjectives ? (
                <p className="text-xs text-gray-700">{truncate(businessObjectives, 200)}</p>
              ) : null}
              {!topIdea && !bcClassification && (
                <p className="text-xs text-gray-400 italic">{t('step6.tic.emptyEnriched')}</p>
              )}
            </div>

            {/* Bottom-right: Connect / Options & Solutions — Application-specific Knowledge */}
            <div className="p-3 bg-indigo-50" style={{ minHeight: '130px' }}>
              <div className="text-xs font-bold text-blue-900 uppercase tracking-wide mb-2">
                Application-specific Knowledge
              </div>
              {projectPlan ? (
                <p className="text-xs text-gray-700 mb-2">{truncate(projectPlan, 220)}</p>
              ) : bcPitch ? (
                <p className="text-xs text-gray-700 italic mb-2">{truncate(bcPitch, 200)}</p>
              ) : null}
              {firstSteps && (
                <p className="text-xs text-gray-500 mt-2">{truncate(firstSteps, 100)}</p>
              )}
              {!projectPlan && !bcPitch && !firstSteps && (
                <p className="text-xs text-gray-400 italic">{t('step6.tic.emptyKnowledge')}</p>
              )}
            </div>
          </div>

          {/* Center diamond — Cluster / Prioritize */}
          <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
            <div className="relative" style={{ width: '76px', height: '76px' }}>
              {/* Diamond shape */}
              <div className="absolute inset-0 bg-white border-2 border-blue-900"
                   style={{ transform: 'rotate(45deg)' }} />
              {/* Labels — positioned outside the rotation */}
              <div className="absolute w-full text-center text-xs font-bold text-blue-900 leading-none"
                   style={{ top: '6px' }}>
                ▲ Cluster
              </div>
              <div className="absolute w-full text-center text-xs font-bold text-blue-900 leading-none"
                   style={{ bottom: '6px' }}>
                ▼ Prioritize
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Selected & Prioritised Use Case callout */}
      {topIdea && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="text-xs font-bold text-blue-700 uppercase tracking-wide mb-1">
            {t('step6.tic.selectedUseCase')}
          </div>
          <p className="text-sm font-semibold text-blue-900">{topIdea}</p>
        </div>
      )}

      {/* Citation */}
      <p className="text-xs text-gray-400 text-center">
        Framework: Schneider, D. (2025). Technology Inquiry Canvas (TIC). DOI: 10.5281/zenodo.14760079. CC BY-SA 4.0.
      </p>
    </div>
  );
};

const IdeasTab = ({ findings, t }) => {
  const brainstorming = findings?.brainstorming;

  if (!brainstorming?.sheets?.length) {
    return <EmptyState message={t('step6.incomplete.ideas')} />;
  }

  // Collect all ideas and group by round
  const allIdeas = [];
  brainstorming.sheets.forEach(sheet => {
    sheet.ideas.forEach(idea => {
      allIdeas.push(idea);
    });
  });

  // Group by round
  const ideasByRound = {};
  allIdeas.forEach(idea => {
    const round = idea.round_number || 1;
    if (!ideasByRound[round]) {
      ideasByRound[round] = [];
    }
    ideasByRound[round].push(idea);
  });

  const sortedRounds = Object.keys(ideasByRound).sort((a, b) => a - b);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">{t('step6.ideas.title')}</h3>
        <span className="text-sm text-gray-500">
          {brainstorming.total_ideas} {t('step6.ideas.totalIdeas')}
        </span>
      </div>

      {sortedRounds.map(round => (
        <div key={round} className="bg-yellow-50 rounded-lg p-4">
          <h4 className="font-medium text-yellow-800 mb-3">
            Round {round}
          </h4>
          <div className="space-y-2">
            {ideasByRound[round].map((idea) => (
              <div key={idea.id} className="flex items-start gap-3 bg-white/50 rounded p-2">
                <p className="text-sm text-gray-700 flex-1">{idea.content}</p>
                {idea.participant_name && (
                  <span className="text-xs text-yellow-600 whitespace-nowrap">
                    {idea.participant_name}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};

const PrioritizationTab = ({ findings, t }) => {
  const prioritization = findings?.prioritization;

  if (!prioritization?.results?.length) {
    return <EmptyState message={t('step6.incomplete.prioritization')} />;
  }

  // Group by idea to aggregate scores
  const ideaScores = {};
  prioritization.results.forEach(vote => {
    if (!vote.idea_id) return;
    if (!ideaScores[vote.idea_id]) {
      ideaScores[vote.idea_id] = {
        idea_content: vote.idea_content,
        votes: [],
        totalScore: 0,
        voteCount: 0
      };
    }
    ideaScores[vote.idea_id].votes.push(vote);
    ideaScores[vote.idea_id].totalScore += vote.score || 0;
    ideaScores[vote.idea_id].voteCount += 1;
  });

  // Sort by total score
  const sortedIdeas = Object.entries(ideaScores)
    .sort((a, b) => b[1].totalScore - a[1].totalScore);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">{t('step6.prioritization.title')}</h3>
        <span className="text-sm text-gray-500">
          {prioritization.total_votes} {t('step6.prioritization.totalVotes')}
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-purple-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-purple-700 uppercase tracking-wider">
                {t('step6.prioritization.rank')}
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-purple-700 uppercase tracking-wider">
                {t('step6.prioritization.idea')}
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium text-purple-700 uppercase tracking-wider">
                {t('step6.prioritization.total')}
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {sortedIdeas.map(([ideaId, data], index) => (
              <tr key={ideaId} className={index === 0 ? 'bg-purple-50' : ''}>
                <td className="px-4 py-3 whitespace-nowrap">
                  <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${
                    index === 0 ? 'bg-purple-600 text-white' : 'bg-gray-200 text-gray-600'
                  }`}>
                    {index + 1}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-gray-900">
                  {data.idea_content}
                  <span className="text-xs text-gray-400 ml-2">({data.voteCount} votes)</span>
                </td>
                <td className="px-4 py-3 text-center text-sm font-semibold text-purple-700">
                  {data.totalScore}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const TranscriptsTab = ({ findings, t }) => {
  const transcripts = findings?.transcripts;
  const [activeTranscript, setActiveTranscript] = React.useState('consultation');

  const hasConsultation = transcripts?.consultation?.length > 0;
  const hasBusinessCase = transcripts?.business_case?.length > 0;
  const hasCostEstimation = transcripts?.cost_estimation?.length > 0;

  if (!hasConsultation && !hasBusinessCase && !hasCostEstimation) {
    return <EmptyState message={t('step6.incomplete.transcripts')} />;
  }

  const transcriptOptions = [
    { id: 'consultation', label: t('step6.transcripts.consultation'), has: hasConsultation },
    { id: 'business_case', label: t('step6.transcripts.businessCase'), has: hasBusinessCase },
    { id: 'cost_estimation', label: t('step6.transcripts.costEstimation'), has: hasCostEstimation },
  ].filter(opt => opt.has);

  const currentMessages = transcripts?.[activeTranscript] || [];

  return (
    <div className="space-y-4">
      {/* Transcript selector */}
      <div className="flex gap-2 border-b border-gray-200 pb-3">
        {transcriptOptions.map(opt => (
          <button
            key={opt.id}
            onClick={() => setActiveTranscript(opt.id)}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
              activeTranscript === opt.id
                ? 'bg-gray-800 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div className="space-y-3 max-h-[600px] overflow-y-auto">
        {currentMessages.map((msg, index) => (
          <div
            key={index}
            className={`p-3 rounded-lg ${
              msg.role === 'user'
                ? 'bg-blue-50 ml-8'
                : msg.role === 'assistant'
                ? 'bg-gray-50 mr-8'
                : 'bg-yellow-50'
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-xs font-medium ${
                msg.role === 'user' ? 'text-blue-600' : 'text-gray-600'
              }`}>
                {msg.role === 'user' ? t('step6.transcripts.user') : t('step6.transcripts.assistant')}
              </span>
              {msg.created_at && (
                <span className="text-xs text-gray-400">
                  {new Date(msg.created_at).toLocaleString()}
                </span>
              )}
            </div>
            <p className="text-sm text-gray-700 whitespace-pre-wrap">{msg.content}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

const ExportTab = ({ t, onExportPDF, exporting, hasAllFindings }) => {
  const completedCount = Object.values(hasAllFindings).filter(Boolean).length;
  const totalCount = Object.keys(hasAllFindings).length;

  return (
    <div className="space-y-6">
      <div className="bg-emerald-50 rounded-lg p-4 mb-6">
        <h4 className="font-medium text-emerald-800 mb-2">{t('step6.export.readiness')}</h4>
        <p className="text-emerald-700">
          {completedCount}/{totalCount} {t('step6.export.sectionsComplete')}
        </p>
        <div className="mt-2 bg-emerald-200 rounded-full h-2">
          <div
            className="bg-emerald-600 h-2 rounded-full transition-all"
            style={{ width: `${(completedCount / totalCount) * 100}%` }}
          />
        </div>
      </div>

      <button
        onClick={onExportPDF}
        disabled={exporting}
        className="w-full flex items-center justify-center gap-3 bg-emerald-600 text-white px-6 py-4 rounded-md hover:bg-emerald-700 disabled:bg-gray-300 transition-colors font-medium"
      >
        {exporting ? (
          <>
            <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {t('step6.export.generating')}
          </>
        ) : (
          <>
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            {t('step6.export.downloadPDF')}
          </>
        )}
      </button>

      <p className="text-sm text-gray-500 text-center">
        {t('step6.export.pdfNote')}
      </p>
    </div>
  );
};

// Helper Components

const EmptyState = ({ message }) => (
  <div className="text-center py-8">
    <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
    <p className="text-gray-500 italic">{message}</p>
  </div>
);

const GenerateButton = ({ onClick, loading, colorClass, children }) => (
  <button
    onClick={onClick}
    disabled={loading}
    className={`${colorClass} text-white px-6 py-3 rounded-md disabled:bg-gray-300 transition-colors font-medium flex items-center gap-2 mx-auto`}
  >
    {loading && (
      <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
    )}
    {children}
  </button>
);

export default Step6Page;
