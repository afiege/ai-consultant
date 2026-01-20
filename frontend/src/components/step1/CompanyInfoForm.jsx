import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

const CompanyInfoForm = ({ onSubmit, loading }) => {
  const { t } = useTranslation();
  const [content, setContent] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!content.trim()) return;

    await onSubmit(content);
    setContent(''); // Clear form after submission
  };

  return (
    <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        {t('step1.textForm.title')}
      </h3>

      <form onSubmit={handleSubmit}>
        <div className="mb-4">
          <label htmlFor="company-text" className="block text-sm font-medium text-gray-700 mb-2">
            {t('step1.textForm.label')}
          </label>
          <textarea
            id="company-text"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder={t('step1.textForm.placeholder')}
            rows={8}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={loading}
          />
          <p className="mt-2 text-sm text-gray-500">
            {t('step1.textForm.hint')}
          </p>
        </div>

        <button
          type="submit"
          disabled={!content.trim() || loading}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? t('step1.textForm.adding') : t('step1.textForm.submit')}
        </button>
      </form>
    </div>
  );
};

export default CompanyInfoForm;
