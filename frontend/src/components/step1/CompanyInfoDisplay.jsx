import React from 'react';
import { useTranslation } from 'react-i18next';
import { format } from 'date-fns';

const CompanyInfoDisplay = ({ companyInfoList, onDelete }) => {
  const { t } = useTranslation();
  if (!companyInfoList || companyInfoList.length === 0) {
    return (
      <div className="text-center py-12" role="status" aria-live="polite">
        {/* Empty state icon */}
        <div className="mx-auto w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
          <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
          </svg>
        </div>
        <h4 className="text-lg font-medium text-gray-900 mb-2">
          {t('step1.companyInfo.empty')}
        </h4>
        <p className="text-sm text-gray-500 max-w-sm mx-auto">
          {t('step1.companyInfo.addInfo')}
        </p>
        <p className="text-xs text-gray-400 mt-4">
          {t('step1.companyInfo.emptyHint', 'Use the forms above to add company information via text, file upload, or web crawling.')}
        </p>
      </div>
    );
  }

  const getTypeIcon = (type) => {
    switch (type) {
      case 'text':
        return (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        );
      case 'file':
        return (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
          </svg>
        );
      case 'web_crawl':
        return (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
          </svg>
        );
      default:
        return null;
    }
  };

  const getTypeName = (type) => {
    switch (type) {
      case 'text':
        return t('step1.companyInfo.sourceText');
      case 'file':
        return t('step1.companyInfo.sourceFile');
      case 'web_crawl':
        return t('step1.companyInfo.sourceWeb');
      default:
        return type;
    }
  };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">
        {t('step1.companyInfo.title')} ({companyInfoList.length})
      </h3>

      <div className="space-y-3">
        {companyInfoList.map((info) => (
          <div
            key={info.id}
            className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm hover:shadow-md transition-shadow"
          >
            {/* Header */}
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center space-x-2">
                <div className="text-blue-600">
                  {getTypeIcon(info.info_type)}
                </div>
                <div>
                  <span className="font-medium text-gray-900">
                    {getTypeName(info.info_type)}
                  </span>
                  {info.file_name && (
                    <span className="text-sm text-gray-600 ml-2">
                      ({info.file_name})
                    </span>
                  )}
                  {info.source_url && (
                    <a
                      href={info.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-600 hover:underline ml-2"
                    >
                      {new URL(info.source_url).hostname}
                    </a>
                  )}
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <span className="text-xs text-gray-500">
                  {format(new Date(info.created_at), 'MMM d, HH:mm')}
                </span>
                {onDelete && (
                  <button
                    onClick={() => onDelete(info.id)}
                    className="text-red-600 hover:text-red-800 p-1 rounded focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
                    aria-label={t('step1.companyInfo.deleteItem', 'Delete this company information')}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                )}
              </div>
            </div>

            {/* Content */}
            <div className="text-sm text-gray-700">
              {info.content && info.content.length > 300 ? (
                <details className="cursor-pointer">
                  <summary className="text-gray-600 hover:text-gray-900 font-medium">
                    {info.content.substring(0, 300)}...
                    <span className="text-blue-600 ml-1">(click to expand)</span>
                  </summary>
                  <div className="mt-2 whitespace-pre-wrap">{info.content}</div>
                </details>
              ) : (
                <div className="whitespace-pre-wrap">{info.content}</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default CompanyInfoDisplay;
