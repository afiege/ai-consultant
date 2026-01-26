import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import {
  sessionAPI,
  companyInfoAPI,
  maturityAPI,
  consultationAPI,
  businessCaseAPI,
  costEstimationAPI,
  exportAPI,
  apiKeyManager
} from '../services/api';
import { PageHeader, ExplanationBox } from '../components/common';
import ApiKeyPrompt from '../components/common/ApiKeyPrompt';

const Step6Page = () => {
  const { t } = useTranslation();
  const { sessionUuid } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [session, setSession] = useState(null);

  // Summary data from previous steps
  const [companyInfo, setCompanyInfo] = useState([]);
  const [maturity, setMaturity] = useState(null);
  const [crispDmFindings, setCrispDmFindings] = useState(null);
  const [businessCaseFindings, setBusinessCaseFindings] = useState(null);
  const [costFindings, setCostFindings] = useState(null);

  // SWOT analysis state
  const [swot, setSwot] = useState(null);
  const [swotLoading, setSwotLoading] = useState(false);
  const [swotError, setSwotError] = useState(null);

  // Transition briefing state
  const [briefing, setBriefing] = useState(null);
  const [briefingLoading, setBriefingLoading] = useState(false);
  const [briefingError, setBriefingError] = useState(null);

  // PDF export state
  const [exporting, setExporting] = useState(false);

  // API key prompt
  const [showApiKeyPrompt, setShowApiKeyPrompt] = useState(false);
  const [pendingAction, setPendingAction] = useState(null);

  // Collapsed sections state
  const [expandedSections, setExpandedSections] = useState({
    company: false,
    maturity: false,
    crispDm: true,
    businessCase: false,
    costs: false,
    swot: true,
    briefing: true,
  });

  useEffect(() => {
    loadAllData();
  }, [sessionUuid]);

  const loadAllData = async () => {
    setLoading(true);
    try {
      // Load session
      const sessionRes = await sessionAPI.get(sessionUuid);
      setSession(sessionRes.data);

      // Load company info
      try {
        const companyRes = await companyInfoAPI.getAll(sessionUuid);
        setCompanyInfo(companyRes.data || []);
      } catch (e) {
        console.log('No company info');
      }

      // Load maturity assessment
      try {
        const maturityRes = await maturityAPI.get(sessionUuid);
        setMaturity(maturityRes.data);
      } catch (e) {
        console.log('No maturity assessment');
      }

      // Load CRISP-DM findings (Step 4)
      try {
        const findingsRes = await consultationAPI.getFindings(sessionUuid);
        if (findingsRes.data.business_objectives || findingsRes.data.ai_goals) {
          setCrispDmFindings(findingsRes.data);
        }
      } catch (e) {
        console.log('No CRISP-DM findings');
      }

      // Load business case findings (Step 5a)
      try {
        const bcRes = await businessCaseAPI.getFindings(sessionUuid);
        if (bcRes.data.classification || bcRes.data.calculation) {
          setBusinessCaseFindings(bcRes.data);
        }
      } catch (e) {
        console.log('No business case findings');
      }

      // Load cost findings (Step 5b)
      try {
        const costRes = await costEstimationAPI.getFindings(sessionUuid);
        if (costRes.data.complexity || costRes.data.tco) {
          setCostFindings(costRes.data);
        }
      } catch (e) {
        console.log('No cost findings');
      }

      // Load existing SWOT analysis
      try {
        const swotRes = await exportAPI.getSwotAnalysis(sessionUuid);
        if (swotRes.data.exists) {
          setSwot(swotRes.data.swot);
        }
      } catch (e) {
        console.log('No SWOT analysis');
      }

      // Load existing transition briefing
      try {
        const briefingRes = await exportAPI.getTransitionBriefing(sessionUuid);
        if (briefingRes.data.exists) {
          setBriefing(briefingRes.data.briefing);
        }
      } catch (e) {
        console.log('No transition briefing');
      }

    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateBriefing = async () => {
    if (!apiKeyManager.isSet()) {
      setPendingAction('generate_briefing');
      setShowApiKeyPrompt(true);
      return;
    }

    setBriefingLoading(true);
    setBriefingError(null);

    try {
      const response = await exportAPI.generateTransitionBriefing(sessionUuid, {
        language: t('common.languageCode') || 'en',
      });
      setBriefing(response.data.briefing);
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
      const response = await exportAPI.generateSwotAnalysis(sessionUuid, {
        language: t('common.languageCode') || 'en',
      });
      setSwot(response.data.swot);
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

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  // Check completeness for status indicators
  const hasCompanyInfo = companyInfo.length > 0;
  const hasMaturity = !!maturity;
  const hasCrispDm = !!crispDmFindings;
  const hasBusinessCase = !!businessCaseFindings;
  const hasCosts = !!costFindings;
  const hasSwot = !!swot;
  const hasBriefing = !!briefing;

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">{t('common.loading')}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <PageHeader
        title={t('step6.title')}
        subtitle={t('step6.subtitle')}
        sessionUuid={sessionUuid}
      />

      {/* Main Content */}
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* Explanation */}
        <ExplanationBox
          title={t('step6.explanation.title')}
          description={t('step6.explanation.description')}
          bullets={[
            t('step6.explanation.bullet1'),
            t('step6.explanation.bullet2'),
            t('step6.explanation.bullet3'),
            t('step6.explanation.bullet4'),
          ]}
          tip={t('step6.explanation.tip')}
          variant="indigo"
          defaultOpen={!hasBriefing}
        />

        {/* Status Overview */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">{t('step6.status.title')}</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <StatusItem
              label={t('step6.status.companyInfo')}
              complete={hasCompanyInfo}
              t={t}
            />
            <StatusItem
              label={t('step6.status.maturity')}
              complete={hasMaturity}
              t={t}
            />
            <StatusItem
              label={t('step6.status.crispDm')}
              complete={hasCrispDm}
              t={t}
            />
            <StatusItem
              label={t('step6.status.businessCase')}
              complete={hasBusinessCase}
              t={t}
            />
            <StatusItem
              label={t('step6.status.costs')}
              complete={hasCosts}
              t={t}
            />
            <StatusItem
              label={t('step6.status.swot')}
              complete={hasSwot}
              t={t}
            />
            <StatusItem
              label={t('step6.status.briefing')}
              complete={hasBriefing}
              t={t}
            />
          </div>
        </div>

        {/* Summary Sections */}
        <div className="space-y-4 mb-8">
          {/* Company Profile Summary */}
          <CollapsibleSection
            title={t('step6.sections.companyProfile')}
            expanded={expandedSections.company}
            onToggle={() => toggleSection('company')}
            complete={hasCompanyInfo}
          >
            {hasCompanyInfo ? (
              <div className="text-sm text-gray-700">
                <p className="font-medium">{session?.company_name || t('step6.unknownCompany')}</p>
                {companyInfo[0]?.content && (
                  <p className="mt-2 text-gray-600">{companyInfo[0].content.slice(0, 300)}...</p>
                )}
              </div>
            ) : (
              <p className="text-sm text-gray-500 italic">{t('step6.incomplete.companyInfo')}</p>
            )}
          </CollapsibleSection>

          {/* Maturity Assessment Summary */}
          <CollapsibleSection
            title={t('step6.sections.maturity')}
            expanded={expandedSections.maturity}
            onToggle={() => toggleSection('maturity')}
            complete={hasMaturity}
          >
            {hasMaturity ? (
              <div className="text-sm">
                <div className="flex items-center gap-3 mb-2">
                  <span className={`px-3 py-1 rounded-full text-white font-bold ${
                    maturity.overall_score < 2 ? 'bg-red-500' :
                    maturity.overall_score < 3 ? 'bg-orange-500' :
                    maturity.overall_score < 4 ? 'bg-yellow-500' :
                    maturity.overall_score < 5 ? 'bg-blue-500' :
                    'bg-green-500'
                  }`}>
                    {maturity.overall_score?.toFixed(1)}/6
                  </span>
                  <span className="font-medium text-gray-700">{maturity.maturity_level}</span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-gray-600">
                  <p>{t('step6.maturity.resources')}: {maturity.resources_score?.toFixed(1)}</p>
                  <p>{t('step6.maturity.infoSystems')}: {maturity.information_systems_score?.toFixed(1)}</p>
                  <p>{t('step6.maturity.culture')}: {maturity.culture_score?.toFixed(1)}</p>
                  <p>{t('step6.maturity.orgStructure')}: {maturity.organizational_structure_score?.toFixed(1)}</p>
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-500 italic">{t('step6.incomplete.maturity')}</p>
            )}
          </CollapsibleSection>

          {/* CRISP-DM Summary */}
          <CollapsibleSection
            title={t('step6.sections.crispDm')}
            expanded={expandedSections.crispDm}
            onToggle={() => toggleSection('crispDm')}
            complete={hasCrispDm}
          >
            {hasCrispDm ? (
              <div className="text-sm text-gray-700 space-y-3">
                {crispDmFindings.business_objectives && (
                  <div>
                    <p className="font-medium">{t('step6.crispDm.objectives')}:</p>
                    <p className="text-gray-600">{crispDmFindings.business_objectives.slice(0, 200)}...</p>
                  </div>
                )}
                {crispDmFindings.ai_goals && (
                  <div>
                    <p className="font-medium">{t('step6.crispDm.aiGoals')}:</p>
                    <p className="text-gray-600">{crispDmFindings.ai_goals.slice(0, 200)}...</p>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-gray-500 italic">{t('step6.incomplete.crispDm')}</p>
            )}
          </CollapsibleSection>

          {/* Business Case Summary */}
          <CollapsibleSection
            title={t('step6.sections.businessCase')}
            expanded={expandedSections.businessCase}
            onToggle={() => toggleSection('businessCase')}
            complete={hasBusinessCase}
          >
            {hasBusinessCase ? (
              <div className="text-sm text-gray-700 space-y-2">
                {businessCaseFindings.classification && (
                  <div>
                    <p className="font-medium">{t('step6.businessCase.classification')}:</p>
                    <p className="text-gray-600">{businessCaseFindings.classification.slice(0, 150)}...</p>
                  </div>
                )}
                {businessCaseFindings.management_pitch && (
                  <div className="bg-green-50 p-3 rounded">
                    <p className="font-medium text-green-800">{t('step6.businessCase.pitch')}:</p>
                    <p className="text-green-700">{businessCaseFindings.management_pitch}</p>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-gray-500 italic">{t('step6.incomplete.businessCase')}</p>
            )}
          </CollapsibleSection>

          {/* Cost Estimation Summary */}
          <CollapsibleSection
            title={t('step6.sections.costs')}
            expanded={expandedSections.costs}
            onToggle={() => toggleSection('costs')}
            complete={hasCosts}
          >
            {hasCosts ? (
              <div className="text-sm text-gray-700 space-y-2">
                {costFindings.complexity && (
                  <div>
                    <p className="font-medium">{t('step6.costs.complexity')}:</p>
                    <p className="text-gray-600">{costFindings.complexity.slice(0, 150)}...</p>
                  </div>
                )}
                {costFindings.tco && (
                  <div className="bg-blue-50 p-3 rounded">
                    <p className="font-medium text-blue-800">{t('step6.costs.tco')}:</p>
                    <p className="text-blue-700">{costFindings.tco.slice(0, 200)}...</p>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-gray-500 italic">{t('step6.incomplete.costs')}</p>
            )}
          </CollapsibleSection>
        </div>

        {/* SWOT Analysis Section */}
        <div className="bg-white rounded-lg shadow-md overflow-hidden mb-8">
          <div className="bg-amber-600 px-6 py-4">
            <h2 className="text-lg font-semibold text-white flex items-center">
              <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              {t('step6.swot.title')}
            </h2>
            <p className="text-amber-200 text-sm mt-1">{t('step6.swot.subtitle')}</p>
          </div>

          <div className="p-6">
            {swotError && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
                <p className="text-sm text-red-700">{swotError}</p>
              </div>
            )}

            {!swot ? (
              <div className="text-center py-8">
                <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                <p className="text-gray-600 mb-4">{t('step6.swot.notGenerated')}</p>
                <button
                  onClick={handleGenerateSwot}
                  disabled={swotLoading}
                  className="bg-amber-600 text-white px-6 py-3 rounded-md hover:bg-amber-700 disabled:bg-gray-300 transition-colors font-medium"
                >
                  {swotLoading ? (
                    <span className="flex items-center">
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      {t('step6.swot.generating')}
                    </span>
                  ) : (
                    t('step6.swot.generateButton')
                  )}
                </button>
                <p className="text-xs text-gray-500 mt-3">{t('step6.swot.generateNote')}</p>
              </div>
            ) : (
              <div>
                <div className="flex justify-end mb-4">
                  <button
                    onClick={handleGenerateSwot}
                    disabled={swotLoading}
                    className="text-sm text-amber-600 hover:text-amber-800 disabled:text-gray-400"
                  >
                    {swotLoading ? t('step6.swot.regenerating') : t('step6.swot.regenerateButton')}
                  </button>
                </div>
                <div className="prose prose-sm max-w-none border border-gray-200 rounded-lg p-6 bg-gray-50">
                  <ReactMarkdown
                    components={{
                      h1: ({children}) => <h1 className="text-xl font-bold text-gray-900 mt-4 mb-2">{children}</h1>,
                      h2: ({children}) => <h2 className="text-lg font-semibold text-gray-800 mt-4 mb-2">{children}</h2>,
                      h3: ({children}) => <h3 className="text-base font-medium text-gray-700 mt-3 mb-1">{children}</h3>,
                      p: ({children}) => <p className="mb-2 text-gray-600">{children}</p>,
                      ul: ({children}) => <ul className="list-disc ml-4 mb-2 text-gray-600">{children}</ul>,
                      ol: ({children}) => <ol className="list-decimal ml-4 mb-2 text-gray-600">{children}</ol>,
                      li: ({children}) => <li className="mb-1">{children}</li>,
                      strong: ({children}) => <strong className="font-semibold text-gray-800">{children}</strong>,
                    }}
                  >
                    {swot}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Technical Transition Briefing Section */}
        <div className="bg-white rounded-lg shadow-md overflow-hidden mb-8">
          <div className="bg-indigo-600 px-6 py-4">
            <h2 className="text-lg font-semibold text-white flex items-center">
              <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              {t('step6.briefing.title')}
            </h2>
            <p className="text-indigo-200 text-sm mt-1">{t('step6.briefing.subtitle')}</p>
          </div>

          <div className="p-6">
            {briefingError && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
                <p className="text-sm text-red-700">{briefingError}</p>
              </div>
            )}

            {!briefing ? (
              <div className="text-center py-8">
                <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p className="text-gray-600 mb-4">{t('step6.briefing.notGenerated')}</p>
                <button
                  onClick={handleGenerateBriefing}
                  disabled={briefingLoading}
                  className="bg-indigo-600 text-white px-6 py-3 rounded-md hover:bg-indigo-700 disabled:bg-gray-300 transition-colors font-medium"
                >
                  {briefingLoading ? (
                    <span className="flex items-center">
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      {t('step6.briefing.generating')}
                    </span>
                  ) : (
                    t('step6.briefing.generateButton')
                  )}
                </button>
                <p className="text-xs text-gray-500 mt-3">{t('step6.briefing.generateNote')}</p>
              </div>
            ) : (
              <div>
                <div className="flex justify-end mb-4">
                  <button
                    onClick={handleGenerateBriefing}
                    disabled={briefingLoading}
                    className="text-sm text-indigo-600 hover:text-indigo-800 disabled:text-gray-400"
                  >
                    {briefingLoading ? t('step6.briefing.regenerating') : t('step6.briefing.regenerateButton')}
                  </button>
                </div>
                <div className="prose prose-sm max-w-none border border-gray-200 rounded-lg p-6 bg-gray-50">
                  <ReactMarkdown
                    components={{
                      h1: ({children}) => <h1 className="text-xl font-bold text-gray-900 mt-4 mb-2">{children}</h1>,
                      h2: ({children}) => <h2 className="text-lg font-semibold text-gray-800 mt-4 mb-2">{children}</h2>,
                      h3: ({children}) => <h3 className="text-base font-medium text-gray-700 mt-3 mb-1">{children}</h3>,
                      p: ({children}) => <p className="mb-2 text-gray-600">{children}</p>,
                      ul: ({children}) => <ul className="list-disc ml-4 mb-2 text-gray-600">{children}</ul>,
                      ol: ({children}) => <ol className="list-decimal ml-4 mb-2 text-gray-600">{children}</ol>,
                      li: ({children}) => <li className="mb-1">{children}</li>,
                      strong: ({children}) => <strong className="font-semibold text-gray-800">{children}</strong>,
                      blockquote: ({children}) => <blockquote className="border-l-4 border-indigo-300 pl-4 italic text-gray-600 my-2">{children}</blockquote>,
                    }}
                  >
                    {briefing}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Export Actions */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">{t('step6.export.title')}</h2>

          <div className="space-y-4">
            <button
              onClick={handleExportPDF}
              disabled={exporting}
              className="w-full flex items-center justify-center gap-3 bg-green-600 text-white px-6 py-4 rounded-md hover:bg-green-700 disabled:bg-gray-300 transition-colors font-medium"
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
        </div>

        {/* Navigation */}
        <div className="mt-8 flex justify-between">
          <button
            onClick={() => navigate(`/session/${sessionUuid}/step5`)}
            className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
          >
            {t('step6.backStep5')}
          </button>
          <button
            onClick={() => navigate('/')}
            className="px-6 py-2 bg-gray-800 text-white rounded-md hover:bg-gray-900"
          >
            {t('step6.backHome')}
          </button>
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

// Helper Components
const StatusItem = ({ label, complete, t }) => (
  <div className={`flex items-center gap-2 p-3 rounded-lg ${complete ? 'bg-green-50' : 'bg-gray-50'}`}>
    {complete ? (
      <svg className="w-5 h-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ) : (
      <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    )}
    <span className={`text-sm ${complete ? 'text-green-700' : 'text-gray-500'}`}>{label}</span>
  </div>
);

const CollapsibleSection = ({ title, expanded, onToggle, complete, children }) => (
  <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
    <button
      onClick={onToggle}
      className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-50 transition-colors"
    >
      <div className="flex items-center gap-3">
        {complete ? (
          <svg className="w-5 h-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        ) : (
          <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        )}
        <span className={`font-medium ${complete ? 'text-gray-900' : 'text-gray-500'}`}>{title}</span>
      </div>
      <svg
        className={`w-5 h-5 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
      </svg>
    </button>
    {expanded && (
      <div className="px-4 pb-4 border-t border-gray-100">
        <div className="pt-3">{children}</div>
      </div>
    )}
  </div>
);

export default Step6Page;
