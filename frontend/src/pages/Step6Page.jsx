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
      case 'export':
        return (
          <ExportTab
            t={t}
            onExportPDF={handleExportPDF}
            exporting={exporting}
            hasAllFindings={{
              hasCompanyProfile, hasCrispDm,
              hasBusinessCase, hasCosts, hasSwot, hasBriefing
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
