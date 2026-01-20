import React from 'react';
import { useTranslation } from 'react-i18next';

const LanguageSelector = ({ value, onChange, disabled = false }) => {
  const { t } = useTranslation();

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm font-medium text-gray-700">{t('expertSettings.language.title')}:</span>
      <div className="flex rounded-md shadow-sm">
        <button
          type="button"
          onClick={() => onChange('en')}
          disabled={disabled}
          className={`px-4 py-2 text-sm font-medium rounded-l-md border ${
            value === 'en'
              ? 'bg-blue-600 text-white border-blue-600'
              : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
          } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          {t('expertSettings.language.english')}
        </button>
        <button
          type="button"
          onClick={() => onChange('de')}
          disabled={disabled}
          className={`px-4 py-2 text-sm font-medium rounded-r-md border-t border-r border-b ${
            value === 'de'
              ? 'bg-blue-600 text-white border-blue-600'
              : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
          } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          {t('expertSettings.language.german')}
        </button>
      </div>
    </div>
  );
};

export default LanguageSelector;
