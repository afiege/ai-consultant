import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { companyInfoAPI, maturityAPI } from '../services/api';
import CompanyInfoForm from '../components/step1/CompanyInfoForm';
import FileUploader from '../components/step1/FileUploader';
import WebCrawlerForm from '../components/step1/WebCrawlerForm';
import CompanyInfoDisplay from '../components/step1/CompanyInfoDisplay';
import CompanyProfileEditor from '../components/step1/CompanyProfileEditor';
import { PageHeader, ExplanationBox } from '../components/common';
import TestModeStep1Panel from '../components/common/TestModeStep1Panel';
import { useTestMode } from '../hooks/useTestMode';

// Maturity level names for reference
const MATURITY_LEVELS = [
  { level: 1, key: 'computerization' },
  { level: 2, key: 'connectivity' },
  { level: 3, key: 'visibility' },
  { level: 4, key: 'transparency' },
  { level: 5, key: 'predictiveCapacity' },
  { level: 6, key: 'adaptability' },
];

// Question configuration for each dimension
const DIMENSION_QUESTIONS = {
  resources: ['q1', 'q2', 'q3', 'q4'],
  informationSystems: ['q1', 'q2', 'q3', 'q4'],
  culture: ['q1', 'q2', 'q3', 'q4'],
  organizationalStructure: ['q1', 'q2', 'q3', 'q4'],
};

const DIMENSIONS = ['resources', 'informationSystems', 'culture', 'organizationalStructure'];

// Slider component for individual questions with +/- buttons for accessibility
const MaturitySlider = ({ value, onChange, questionKey, dimensionKey, t }) => {
  const levelKey = MATURITY_LEVELS.find(l => l.level === value)?.key || 'computerization';
  const labelId = `slider-label-${dimensionKey}-${questionKey}`;
  const sliderId = `slider-${dimensionKey}-${questionKey}`;

  const handleDecrement = () => {
    if (value > 1) onChange(value - 1);
  };

  const handleIncrement = () => {
    if (value < 6) onChange(value + 1);
  };

  return (
    <div className="bg-gray-50 rounded-lg p-4 mb-4">
      <label id={labelId} className="block text-sm font-medium text-gray-700 mb-3">
        {t(`step1b.dimensions.${dimensionKey}.${questionKey}`)}
      </label>
      <div className="flex items-center gap-2">
        {/* Decrement button for better accessibility */}
        <button
          type="button"
          onClick={handleDecrement}
          disabled={value <= 1}
          aria-label={t('common.decrease', 'Decrease')}
          className="w-8 h-8 rounded-full bg-gray-200 hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center text-gray-700 font-bold transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          −
        </button>
        <div className="flex-1 px-2">
          <input
            id={sliderId}
            type="range"
            min="1"
            max="6"
            step="1"
            value={value}
            onChange={(e) => onChange(parseInt(e.target.value))}
            aria-labelledby={labelId}
            aria-valuemin={1}
            aria-valuemax={6}
            aria-valuenow={value}
            aria-valuetext={`${value} - ${t(`step1b.maturityLevels.${levelKey}`)}`}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        {/* Increment button for better accessibility */}
        <button
          type="button"
          onClick={handleIncrement}
          disabled={value >= 6}
          aria-label={t('common.increase', 'Increase')}
          className="w-8 h-8 rounded-full bg-gray-200 hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center text-gray-700 font-bold transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          +
        </button>
        <div className="w-12 text-center">
          <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-blue-600 text-white font-bold text-sm">
            {value}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <div className="w-8"></div>
        <div className="flex-1 px-2">
          <div className="flex justify-between text-xs text-gray-500">
            <span>1</span>
            <span>2</span>
            <span>3</span>
            <span>4</span>
            <span>5</span>
            <span>6</span>
          </div>
        </div>
        <div className="w-8"></div>
        <div className="w-12"></div>
      </div>
    </div>
  );
};

// Dimension card component with ARIA attributes for accordion
const DimensionCard = ({ dimension, scores, onScoreChange, t, isExpanded, onToggle }) => {
  const questions = DIMENSION_QUESTIONS[dimension];
  const avgScore = questions.reduce((sum, q) => sum + (scores[q] || 1), 0) / questions.length;
  const levelKey = MATURITY_LEVELS.find(l => l.level === Math.round(avgScore))?.key || 'computerization';
  const contentId = `dimension-content-${dimension}`;
  const headerId = `dimension-header-${dimension}`;

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      <button
        id={headerId}
        onClick={onToggle}
        aria-expanded={isExpanded}
        aria-controls={contentId}
        className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-gray-50 transition-colors focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500"
      >
        <div className="flex items-center gap-4">
          {/* Improved color contrast: using -600/-700 instead of -500 */}
          <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-bold ${
            avgScore < 2 ? 'bg-red-600' :
            avgScore < 3 ? 'bg-orange-600' :
            avgScore < 4 ? 'bg-yellow-600' :
            avgScore < 5 ? 'bg-blue-600' :
            'bg-green-600'
          }`}>
            {avgScore.toFixed(1)}
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">
              {t(`step1b.dimensions.${dimension}.title`)}
            </h3>
            <p className="text-sm text-gray-600">
              {t(`step1b.maturityLevels.${levelKey}`)}
            </p>
          </div>
        </div>
        <svg
          className={`w-5 h-5 text-gray-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      <div
        id={contentId}
        role="region"
        aria-labelledby={headerId}
        hidden={!isExpanded}
      >
        {isExpanded && (
          <div className="px-6 pb-6 border-t border-gray-100">
            <p className="text-sm text-gray-600 my-4">
              {t(`step1b.dimensions.${dimension}.description`)}
            </p>
            {questions.map((q) => (
              <MaturitySlider
                key={q}
                value={scores[q] || 1}
                onChange={(val) => onScoreChange(q, val)}
                questionKey={q}
                dimensionKey={dimension}
                t={t}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

// Overall results display with improved color contrast
const MaturityResults = ({ scores, t }) => {
  // Calculate dimension averages
  const dimensionScores = DIMENSIONS.map(dim => {
    const questions = DIMENSION_QUESTIONS[dim];
    const dimScores = scores[dim] || {};
    return questions.reduce((sum, q) => sum + (dimScores[q] || 1), 0) / questions.length;
  });

  const overallScore = dimensionScores.reduce((sum, s) => sum + s, 0) / dimensionScores.length;
  const levelKey = MATURITY_LEVELS.find(l => l.level === Math.round(overallScore))?.key || 'computerization';

  return (
    <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg p-6 mb-6" role="region" aria-label={t('step1b.results.title')}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">
          {t('step1b.results.title')}
        </h3>
        <div className="flex items-center gap-3">
          {/* Improved color contrast: using -600 instead of -500 */}
          <div
            className={`w-16 h-16 rounded-full flex items-center justify-center text-white font-bold text-xl ${
              overallScore < 2 ? 'bg-red-600' :
              overallScore < 3 ? 'bg-orange-600' :
              overallScore < 4 ? 'bg-yellow-600' :
              overallScore < 5 ? 'bg-blue-600' :
              'bg-green-600'
            }`}
            role="img"
            aria-label={`${t('step1b.results.maturityLevel')}: ${overallScore.toFixed(1)} - ${t(`step1b.maturityLevels.${levelKey}`)}`}
          >
            {overallScore.toFixed(1)}
          </div>
          <div>
            <p className="text-sm text-gray-600">{t('step1b.results.maturityLevel')}</p>
            <p className="font-semibold text-gray-900">{t(`step1b.maturityLevels.${levelKey}`)}</p>
          </div>
        </div>
      </div>

      {/* Dimension bars with ARIA */}
      <div className="space-y-3" role="list" aria-label={t('step1b.results.dimensionScores', 'Dimension Scores')}>
        {DIMENSIONS.map((dim, idx) => {
          const score = dimensionScores[idx];
          return (
            <div key={dim} className="flex items-center gap-3" role="listitem">
              <span className="text-sm text-gray-700 w-40 truncate">
                {t(`step1b.dimensions.${dim}.title`)}
              </span>
              <div className="flex-1 h-3 bg-gray-200 rounded-full overflow-hidden">
                {/* Improved color contrast: using -600 instead of -500 */}
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    score < 2 ? 'bg-red-600' :
                    score < 3 ? 'bg-orange-600' :
                    score < 4 ? 'bg-yellow-600' :
                    score < 5 ? 'bg-blue-600' :
                    'bg-green-600'
                  }`}
                  style={{ width: `${(score / 6) * 100}%` }}
                  role="progressbar"
                  aria-valuenow={score}
                  aria-valuemin={1}
                  aria-valuemax={6}
                  aria-label={`${t(`step1b.dimensions.${dim}.title`)}: ${score.toFixed(1)}`}
                />
              </div>
              <span className="text-sm font-medium text-gray-700 w-8" aria-hidden="true">
                {score.toFixed(1)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const Step1Page = () => {
  const { t } = useTranslation();
  const { sessionUuid } = useParams();
  const navigate = useNavigate();

  // Tab state: 'profile' (1a) or 'maturity' (1b)
  const [activeTab, setActiveTab] = useState('profile');

  // === Step 1a (Company Profile) state ===
  const [companyInfoList, setCompanyInfoList] = useState([]);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileLoadingType, setProfileLoadingType] = useState(null);
  const [profileError, setProfileError] = useState(null);

  // === Step 1b (Maturity Assessment) state ===
  const [scores, setScores] = useState({
    resources: { q1: 1, q2: 1, q3: 1, q4: 1 },
    informationSystems: { q1: 1, q2: 1, q3: 1, q4: 1 },
    culture: { q1: 1, q2: 1, q3: 1, q4: 1 },
    organizationalStructure: { q1: 1, q2: 1, q3: 1, q4: 1 },
  });
  const [expandedDimensions, setExpandedDimensions] = useState(['resources']);
  const [maturityLoading, setMaturityLoading] = useState(true);
  const [maturitySaving, setMaturitySaving] = useState(false);
  const [maturityError, setMaturityError] = useState(null);
  const [maturitySaved, setMaturitySaved] = useState(false);

  // Test mode state (from localStorage, synced across tabs)
  const testModeEnabled = useTestMode();

  // Load data on mount
  useEffect(() => {
    loadCompanyInfo();
    loadMaturityAssessment();
  }, [sessionUuid]);

  // === Step 1a (Company Profile) functions ===
  const loadCompanyInfo = async () => {
    try {
      const response = await companyInfoAPI.getAll(sessionUuid);
      setCompanyInfoList(response.data);
    } catch (err) {
      console.error('Error loading company info:', err);
      setProfileError(t('errors.failedToLoad'));
    }
  };

  const handleTextSubmit = async (content) => {
    setProfileLoading(true);
    setProfileLoadingType('text');
    setProfileError(null);

    try {
      await companyInfoAPI.submitText(sessionUuid, { content });
      await loadCompanyInfo();
    } catch (err) {
      console.error('Error submitting text:', err);
      setProfileError(t('errors.failedToSave'));
    } finally {
      setProfileLoading(false);
      setProfileLoadingType(null);
    }
  };

  const handleFileUpload = async (file) => {
    setProfileLoading(true);
    setProfileLoadingType('file');
    setProfileError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      await companyInfoAPI.uploadFile(sessionUuid, formData);
      await loadCompanyInfo();
    } catch (err) {
      console.error('Error uploading file:', err);
      setProfileError(err.response?.data?.detail || t('errors.failedToSubmit'));
      throw err;
    } finally {
      setProfileLoading(false);
      setProfileLoadingType(null);
    }
  };

  const handleWebCrawl = async (url) => {
    setProfileLoading(true);
    setProfileLoadingType('crawl');
    setProfileError(null);

    try {
      await companyInfoAPI.crawlWeb(sessionUuid, { url });
      await loadCompanyInfo();
    } catch (err) {
      console.error('Error crawling website:', err);
      setProfileError(err.response?.data?.detail || t('errors.failedToSubmit'));
    } finally {
      setProfileLoading(false);
      setProfileLoadingType(null);
    }
  };

  const handleDeleteCompanyInfo = async (infoId) => {
    if (!window.confirm(t('common.delete') + '?')) {
      return;
    }

    try {
      await companyInfoAPI.delete(sessionUuid, infoId);
      await loadCompanyInfo();
    } catch (err) {
      console.error('Error deleting company info:', err);
      alert(t('errors.failedToSave'));
    }
  };

  // === Step 1b (Maturity Assessment) functions ===
  const loadMaturityAssessment = async () => {
    try {
      const response = await maturityAPI.get(sessionUuid);
      if (response.data) {
        // Reconstruct scores from saved data
        const loadedScores = {
          resources: response.data.resources_details || { q1: response.data.resources_score || 1, q2: response.data.resources_score || 1, q3: response.data.resources_score || 1, q4: response.data.resources_score || 1 },
          informationSystems: response.data.information_systems_details || { q1: response.data.information_systems_score || 1, q2: response.data.information_systems_score || 1, q3: response.data.information_systems_score || 1, q4: response.data.information_systems_score || 1 },
          culture: response.data.culture_details || { q1: response.data.culture_score || 1, q2: response.data.culture_score || 1, q3: response.data.culture_score || 1, q4: response.data.culture_score || 1 },
          organizationalStructure: response.data.organizational_structure_details || { q1: response.data.organizational_structure_score || 1, q2: response.data.organizational_structure_score || 1, q3: response.data.organizational_structure_score || 1, q4: response.data.organizational_structure_score || 1 },
        };
        setScores(loadedScores);
        setMaturitySaved(true);
      }
    } catch (err) {
      // No assessment yet, that's fine
      console.log('No existing assessment found');
    } finally {
      setMaturityLoading(false);
    }
  };

  const handleScoreChange = (dimension, question, value) => {
    setScores(prev => ({
      ...prev,
      [dimension]: {
        ...prev[dimension],
        [question]: value,
      },
    }));
    setMaturitySaved(false);
  };

  const toggleDimension = (dimension) => {
    setExpandedDimensions(prev =>
      prev.includes(dimension)
        ? prev.filter(d => d !== dimension)
        : [...prev, dimension]
    );
  };

  const calculateDimensionScore = (dimension) => {
    const dimScores = scores[dimension] || {};
    const questions = DIMENSION_QUESTIONS[dimension];
    return questions.reduce((sum, q) => sum + (dimScores[q] || 1), 0) / questions.length;
  };

  const handleSaveMaturity = async () => {
    setMaturitySaving(true);
    setMaturityError(null);

    try {
      const assessmentData = {
        resources_score: calculateDimensionScore('resources'),
        resources_details: scores.resources,
        information_systems_score: calculateDimensionScore('informationSystems'),
        information_systems_details: scores.informationSystems,
        culture_score: calculateDimensionScore('culture'),
        culture_details: scores.culture,
        organizational_structure_score: calculateDimensionScore('organizationalStructure'),
        organizational_structure_details: scores.organizationalStructure,
      };

      await maturityAPI.save(sessionUuid, assessmentData);
      setMaturitySaved(true);
    } catch (err) {
      console.error('Error saving assessment:', err);
      setMaturityError(t('errors.failedToSave'));
    } finally {
      setMaturitySaving(false);
    }
  };

  // === Test Mode Handlers ===
  const handleTestModeFillProfile = async (profileText) => {
    // Submit the profile text as company info
    await handleTextSubmit(profileText);
  };

  const handleTestModeFillMaturity = (maturityScores) => {
    // Set the maturity scores from the persona
    setScores(maturityScores);
    setMaturitySaved(false);
    // Expand all dimensions to show the filled values
    setExpandedDimensions(DIMENSIONS);
  };

  const currentError = activeTab === 'profile' ? profileError : maturityError;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <PageHeader
        title={t('step1.title')}
        subtitle={t('step1.subtitle')}
        sessionUuid={sessionUuid}
      />

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {currentError && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-700">{currentError}</p>
          </div>
        )}

        {/* Tab Navigation with keyboard support */}
        <div className="mb-6 border-b border-gray-200">
          <nav
            className="-mb-px flex space-x-8"
            role="tablist"
            aria-label={t('step1.tabNavigation', 'Step 1 navigation')}
            onKeyDown={(e) => {
              const tabs = ['profile', 'maturity'];
              const currentIndex = tabs.indexOf(activeTab);
              if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
                e.preventDefault();
                const nextIndex = (currentIndex + 1) % tabs.length;
                setActiveTab(tabs[nextIndex]);
              } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
                e.preventDefault();
                const prevIndex = (currentIndex - 1 + tabs.length) % tabs.length;
                setActiveTab(tabs[prevIndex]);
              } else if (e.key === 'Home') {
                e.preventDefault();
                setActiveTab(tabs[0]);
              } else if (e.key === 'End') {
                e.preventDefault();
                setActiveTab(tabs[tabs.length - 1]);
              }
            }}
          >
            <button
              id="tab-profile"
              role="tab"
              aria-selected={activeTab === 'profile'}
              aria-controls="tabpanel-profile"
              tabIndex={activeTab === 'profile' ? 0 : -1}
              onClick={() => setActiveTab('profile')}
              className={`py-4 px-1 border-b-2 font-medium text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                activeTab === 'profile'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <span className="flex items-center">
                <span className="bg-blue-100 text-blue-800 text-xs font-medium mr-2 px-2 py-0.5 rounded" aria-hidden="true">1a</span>
                {t('step1.tabs.profile')}
                {companyInfoList.length > 0 && (
                  <span className="ml-2 w-2 h-2 bg-green-500 rounded-full" aria-label={t('common.completed', 'Completed')}></span>
                )}
              </span>
            </button>
            <button
              id="tab-maturity"
              role="tab"
              aria-selected={activeTab === 'maturity'}
              aria-controls="tabpanel-maturity"
              tabIndex={activeTab === 'maturity' ? 0 : -1}
              onClick={() => setActiveTab('maturity')}
              className={`py-4 px-1 border-b-2 font-medium text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 ${
                activeTab === 'maturity'
                  ? 'border-purple-500 text-purple-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <span className="flex items-center">
                <span className="bg-purple-100 text-purple-800 text-xs font-medium mr-2 px-2 py-0.5 rounded" aria-hidden="true">1b</span>
                {t('step1.tabs.maturity')}
                {maturitySaved && (
                  <span className="ml-2 w-2 h-2 bg-green-500 rounded-full" aria-label={t('common.completed', 'Completed')}></span>
                )}
              </span>
            </button>
          </nav>
        </div>

        {/* Tab Content */}
        {activeTab === 'profile' ? (
          // === Step 1a: Company Profile ===
          <div
            id="tabpanel-profile"
            role="tabpanel"
            aria-labelledby="tab-profile"
            tabIndex={0}
          >
            {/* Explanation */}
            <ExplanationBox
              title={t('step1a.explanation.title')}
              description={t('step1a.explanation.description')}
              bullets={[
                t('step1a.explanation.bullet1'),
                t('step1a.explanation.bullet2'),
                t('step1a.explanation.bullet3'),
                t('step1a.explanation.bullet4'),
              ]}
              tip={t('step1a.explanation.tip')}
              defaultOpen={companyInfoList.length === 0}
            />

            {/* Input Forms */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
              <CompanyInfoForm
                onSubmit={handleTextSubmit}
                loading={profileLoading && profileLoadingType === 'text'}
              />
              <FileUploader
                onUpload={handleFileUpload}
                loading={profileLoading && profileLoadingType === 'file'}
              />
              <WebCrawlerForm
                onCrawl={handleWebCrawl}
                loading={profileLoading && profileLoadingType === 'crawl'}
              />
            </div>

            {/* Collected Information Display */}
            <div className="bg-gray-100 rounded-lg p-6 mb-6">
              <CompanyInfoDisplay
                companyInfoList={companyInfoList}
                onDelete={handleDeleteCompanyInfo}
              />
            </div>

            {/* Structured Company Profile */}
            <CompanyProfileEditor
              sessionUuid={sessionUuid}
              hasCompanyInfo={companyInfoList.length > 0}
            />
          </div>
        ) : (
          // === Step 1b: Maturity Assessment ===
          <div
            id="tabpanel-maturity"
            role="tabpanel"
            aria-labelledby="tab-maturity"
            tabIndex={0}
            className="max-w-4xl mx-auto"
          >
            {maturityLoading ? (
              <div className="flex items-center justify-center py-12">
                <p className="text-gray-600">{t('common.loading')}</p>
              </div>
            ) : (
              <>
                {/* Explanation */}
                <ExplanationBox
                  title={t('step1b.explanation.title')}
                  description={t('step1b.explanation.description')}
                  bullets={[
                    t('step1b.explanation.bullet1'),
                    t('step1b.explanation.bullet2'),
                    t('step1b.explanation.bullet3'),
                    t('step1b.explanation.bullet4'),
                  ]}
                  tip={t('step1b.explanation.tip')}
                  variant="purple"
                  defaultOpen={!maturitySaved}
                />

                {/* Results Overview */}
                <MaturityResults scores={scores} t={t} />

                {/* Maturity Level Reference - improved color contrast */}
                <div className="bg-white rounded-lg shadow p-4 mb-6">
                  <h4 className="font-medium text-gray-900 mb-3">{t('step1b.levelReference.title')}</h4>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm" role="list">
                    {MATURITY_LEVELS.map(level => (
                      <div key={level.level} className="flex items-center gap-2" role="listitem">
                        <span
                          className={`w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold ${
                            level.level === 1 ? 'bg-red-600' :
                            level.level === 2 ? 'bg-orange-600' :
                            level.level === 3 ? 'bg-yellow-600' :
                            level.level === 4 ? 'bg-blue-500' :
                            level.level === 5 ? 'bg-blue-700' :
                            'bg-green-600'
                          }`}
                          aria-hidden="true"
                        >
                          {level.level}
                        </span>
                        <span className="text-gray-700">{t(`step1b.maturityLevels.${level.key}`)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Dimension Cards */}
                <div className="space-y-4 mb-8">
                  {DIMENSIONS.map(dimension => (
                    <DimensionCard
                      key={dimension}
                      dimension={dimension}
                      scores={scores[dimension] || {}}
                      onScoreChange={(q, v) => handleScoreChange(dimension, q, v)}
                      t={t}
                      isExpanded={expandedDimensions.includes(dimension)}
                      onToggle={() => toggleDimension(dimension)}
                    />
                  ))}
                </div>

                {/* Save Button */}
                <div className="flex justify-center mb-8">
                  <button
                    onClick={handleSaveMaturity}
                    disabled={maturitySaving}
                    className={`px-8 py-3 rounded-md font-medium transition-colors ${
                      maturitySaved
                        ? 'bg-green-600 text-white hover:bg-green-700'
                        : 'bg-blue-600 text-white hover:bg-blue-700'
                    } disabled:bg-gray-300 disabled:cursor-not-allowed`}
                  >
                    {maturitySaving ? t('common.saving') : maturitySaved ? t('step1b.saved') : t('step1b.saveAssessment')}
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Test Mode Panel - only shown when enabled in expert settings */}
      {testModeEnabled && (
        <TestModeStep1Panel
          activeTab={activeTab}
          onFillCompanyProfile={handleTestModeFillProfile}
          onFillMaturityScores={handleTestModeFillMaturity}
          disabled={profileLoading || maturitySaving}
        />
      )}
    </div>
  );
};

export default Step1Page;
