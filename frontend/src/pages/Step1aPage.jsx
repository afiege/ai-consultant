import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { companyInfoAPI } from '../services/api';
import CompanyInfoForm from '../components/step1/CompanyInfoForm';
import FileUploader from '../components/step1/FileUploader';
import WebCrawlerForm from '../components/step1/WebCrawlerForm';
import CompanyInfoDisplay from '../components/step1/CompanyInfoDisplay';
import { PageHeader, ExplanationBox } from '../components/common';

const Step1aPage = () => {
  const { t } = useTranslation();
  const { sessionUuid } = useParams();
  const navigate = useNavigate();
  const [companyInfoList, setCompanyInfoList] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadingType, setLoadingType] = useState(null);
  const [error, setError] = useState(null);

  // Load existing company info
  useEffect(() => {
    loadCompanyInfo();
  }, [sessionUuid]);

  const loadCompanyInfo = async () => {
    try {
      const response = await companyInfoAPI.getAll(sessionUuid);
      setCompanyInfoList(response.data);
    } catch (err) {
      console.error('Error loading company info:', err);
      setError(t('errors.failedToLoad'));
    }
  };

  const handleTextSubmit = async (content) => {
    setLoading(true);
    setLoadingType('text');
    setError(null);

    try {
      await companyInfoAPI.submitText(sessionUuid, { content });
      await loadCompanyInfo();
    } catch (err) {
      console.error('Error submitting text:', err);
      setError(t('errors.failedToSave'));
    } finally {
      setLoading(false);
      setLoadingType(null);
    }
  };

  const handleFileUpload = async (file) => {
    setLoading(true);
    setLoadingType('file');
    setError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      await companyInfoAPI.uploadFile(sessionUuid, formData);
      await loadCompanyInfo();
    } catch (err) {
      console.error('Error uploading file:', err);
      setError(err.response?.data?.detail || t('errors.failedToSubmit'));
      throw err;
    } finally {
      setLoading(false);
      setLoadingType(null);
    }
  };

  const handleWebCrawl = async (url) => {
    setLoading(true);
    setLoadingType('crawl');
    setError(null);

    try {
      await companyInfoAPI.crawlWeb(sessionUuid, { url });
      await loadCompanyInfo();
    } catch (err) {
      console.error('Error crawling website:', err);
      setError(err.response?.data?.detail || t('errors.failedToSubmit'));
    } finally {
      setLoading(false);
      setLoadingType(null);
    }
  };

  const handleDelete = async (infoId) => {
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

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <PageHeader
        title={t('step1a.title')}
        subtitle={t('step1a.subtitle')}
        sessionUuid={sessionUuid}
      />

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

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
            loading={loading && loadingType === 'text'}
          />
          <FileUploader
            onUpload={handleFileUpload}
            loading={loading && loadingType === 'file'}
          />
          <WebCrawlerForm
            onCrawl={handleWebCrawl}
            loading={loading && loadingType === 'crawl'}
          />
        </div>

        {/* Collected Information Display */}
        <div className="bg-gray-100 rounded-lg p-6">
          <CompanyInfoDisplay
            companyInfoList={companyInfoList}
            onDelete={handleDelete}
          />
        </div>

      </div>
    </div>
  );
};

export default Step1aPage;
