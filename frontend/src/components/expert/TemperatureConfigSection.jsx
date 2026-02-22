import React from 'react';
import { useTranslation } from 'react-i18next';

const TEMPERATURE_FIELDS = [
  { key: 'brainstorming', defaultVal: '0.7' },
  { key: 'consultation', defaultVal: '0.7' },
  { key: 'business_case', defaultVal: '0.7' },
  { key: 'cost_estimation', defaultVal: '0.7' },
  { key: 'extraction', defaultVal: '0.3' },
  { key: 'export', defaultVal: '0.4' },
];

const TemperatureConfigSection = ({ config, onChange }) => {
  const { t } = useTranslation();

  const handleFieldChange = (key, value) => {
    const newConfig = { ...config };
    if (value === '' || value === null || value === undefined) {
      delete newConfig[key];
    } else {
      const numVal = parseFloat(value);
      if (!isNaN(numVal) && numVal >= 0 && numVal <= 2) {
        newConfig[key] = numVal;
      }
    }
    onChange(newConfig);
  };

  const handleResetAll = () => {
    onChange({});
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-medium text-amber-800">
          {t('expertSettings.temperature.title')}
        </h4>
        <button
          type="button"
          onClick={handleResetAll}
          className="text-xs text-amber-700 hover:text-amber-900 underline"
        >
          {t('expertSettings.temperature.resetAll')}
        </button>
      </div>
      <p className="text-xs text-amber-700 mb-3">
        {t('expertSettings.temperature.description')}
      </p>
      <div className="grid grid-cols-2 gap-3">
        {TEMPERATURE_FIELDS.map((field) => (
          <div key={field.key}>
            <label className="block text-xs font-medium text-amber-800 mb-1">
              {t(`expertSettings.temperature.${field.key}`)}
            </label>
            <input
              type="number"
              min={0}
              max={2}
              step={0.1}
              value={config[field.key] != null ? config[field.key] : ''}
              onChange={(e) => handleFieldChange(field.key, e.target.value)}
              placeholder={field.defaultVal}
              className="w-full px-3 py-1.5 text-sm border border-amber-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-500 bg-white placeholder-amber-400"
            />
          </div>
        ))}
      </div>
    </div>
  );
};

export default TemperatureConfigSection;
