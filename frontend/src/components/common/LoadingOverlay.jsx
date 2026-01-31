import React from 'react';
import { useTranslation } from 'react-i18next';

const LoadingOverlay = ({
  isVisible,
  title,
  description,
  showProgress = false,
  progress = 0
}) => {
  const { t } = useTranslation();

  if (!isVisible) return null;

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="loading-title"
      aria-describedby="loading-description"
    >
      <div className="bg-white rounded-lg p-8 max-w-md w-full mx-4 shadow-2xl">
        <div className="flex items-center space-x-4">
          <svg
            className="animate-spin h-10 w-10 text-blue-600 flex-shrink-0"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          <div>
            <h3 id="loading-title" className="font-semibold text-gray-900 text-lg">
              {title || t('common.loading', 'Loading...')}
            </h3>
            {description && (
              <p id="loading-description" className="text-sm text-gray-600 mt-1">
                {description}
              </p>
            )}
          </div>
        </div>

        {showProgress && (
          <div className="mt-6">
            <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
              <div
                className="bg-blue-600 h-2.5 rounded-full transition-all duration-300 ease-out"
                style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
                role="progressbar"
                aria-valuenow={progress}
                aria-valuemin="0"
                aria-valuemax="100"
              />
            </div>
            <p className="text-xs text-gray-500 mt-2 text-center">
              {Math.round(progress)}%
            </p>
          </div>
        )}

        {!showProgress && (
          <div className="mt-4 flex justify-center">
            <div className="flex space-x-1">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="w-2 h-2 bg-blue-600 rounded-full animate-pulse"
                  style={{ animationDelay: `${i * 200}ms` }}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default LoadingOverlay;
