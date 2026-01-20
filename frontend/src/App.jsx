import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { SessionProvider } from './context/SessionContext';
import { exportAPI } from './services/api';
import HomePage from './pages/HomePage';
import Step1Page from './pages/Step1Page';
import Step2Page from './pages/Step2Page';
import Step3Page from './pages/Step3Page';
import Step4Page from './pages/Step4Page';
import Step5Page from './pages/Step5Page';

const ExportPage = () => {
  const { sessionUuid } = useParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [generating, setGenerating] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [downloadUrl, setDownloadUrl] = React.useState(null);

  const handleGeneratePDF = async () => {
    setGenerating(true);
    setError(null);

    try {
      const response = await exportAPI.generatePDF(sessionUuid);
      // Create download URL from blob
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      setDownloadUrl(url);

      // Auto-download
      const link = document.createElement('a');
      link.href = url;
      link.download = `consultation-report-${sessionUuid}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err) {
      setError(err.response?.data?.detail || t('errors.failedToGeneratePDF'));
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <h1 className="text-2xl font-bold text-gray-900">{t('export.title')}</h1>
          <p className="mt-1 text-sm text-gray-600">
            {t('export.subtitle')}
          </p>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        <div className="bg-white rounded-lg shadow p-8 text-center">
          <div className="mb-6">
            <svg className="w-16 h-16 mx-auto text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>

          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            {t('export.reportTitle')}
          </h2>
          <p className="text-gray-600 mb-6">
            {t('export.reportIncludes')}
          </p>

          <ul className="text-left max-w-md mx-auto mb-8 space-y-2">
            <li className="flex items-center text-gray-700">
              <span className="w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mr-3 text-sm font-bold">1</span>
              {t('export.executiveSummary')}
            </li>
            <li className="flex items-center text-gray-700">
              <span className="w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mr-3 text-sm font-bold">2</span>
              {t('export.businessCaseSection')}
            </li>
            <li className="flex items-center text-gray-700">
              <span className="w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mr-3 text-sm font-bold">3</span>
              {t('export.implementationRoadmap')}
            </li>
            <li className="flex items-center text-gray-500 text-sm mt-4 pt-2 border-t">
              <span className="w-5 h-5 bg-gray-100 text-gray-500 rounded-full flex items-center justify-center mr-3 text-xs">A</span>
              {t('export.appendixCompany')}
            </li>
            <li className="flex items-center text-gray-500 text-sm">
              <span className="w-5 h-5 bg-gray-100 text-gray-500 rounded-full flex items-center justify-center mr-3 text-xs">B</span>
              {t('export.appendixIdeas')}
            </li>
            <li className="flex items-center text-gray-500 text-sm">
              <span className="w-5 h-5 bg-gray-100 text-gray-500 rounded-full flex items-center justify-center mr-3 text-xs">C</span>
              {t('export.appendixPrioritization')}
            </li>
            <li className="flex items-center text-gray-500 text-sm">
              <span className="w-5 h-5 bg-gray-100 text-gray-500 rounded-full flex items-center justify-center mr-3 text-xs">D</span>
              {t('export.appendixTranscript')}
            </li>
            <li className="flex items-center text-gray-500 text-sm">
              <span className="w-5 h-5 bg-gray-100 text-gray-500 rounded-full flex items-center justify-center mr-3 text-xs">E</span>
              {t('export.appendixBusinessCase')}
            </li>
          </ul>

          <button
            onClick={handleGeneratePDF}
            disabled={generating}
            className="bg-blue-600 text-white py-3 px-8 rounded-md hover:bg-blue-700 disabled:bg-gray-300 transition-colors font-medium"
          >
            {generating ? t('export.generating') : t('export.generateButton')}
          </button>

          {downloadUrl && (
            <p className="mt-4 text-green-600 text-sm">
              {t('export.success')}
            </p>
          )}
        </div>

        <div className="mt-8 flex justify-between">
          <button
            onClick={() => navigate(`/session/${sessionUuid}/step5`)}
            className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
          >
            {t('export.backToBusinessCase')}
          </button>
          <button
            onClick={() => navigate('/')}
            className="px-6 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
          >
            {t('export.startNew')}
          </button>
        </div>
      </div>
    </div>
  );
};

function App() {
  return (
    <SessionProvider>
      <Router>
        <div className="min-h-screen bg-gray-50">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/session/:sessionUuid/step1" element={<Step1Page />} />
            <Route path="/session/:sessionUuid/step2" element={<Step2Page />} />
            <Route path="/session/:sessionUuid/step3" element={<Step3Page />} />
            <Route path="/session/:sessionUuid/step4" element={<Step4Page />} />
            <Route path="/session/:sessionUuid/step5" element={<Step5Page />} />
            <Route path="/session/:sessionUuid/export" element={<ExportPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </Router>
    </SessionProvider>
  );
}

export default App;
