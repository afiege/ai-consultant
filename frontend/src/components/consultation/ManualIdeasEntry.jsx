import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

const ManualIdeasEntry = ({ onSubmit, submitting }) => {
  const { t } = useTranslation();
  const [manualIdeas, setManualIdeas] = useState(['', '', '']);

  const handleIdeaChange = (index, value) => {
    const newIdeas = [...manualIdeas];
    newIdeas[index] = value;
    setManualIdeas(newIdeas);
  };

  const handleSubmit = async () => {
    const filledIdeas = manualIdeas.filter((idea) => idea.trim() !== '');
    if (filledIdeas.length === 0) {
      return;
    }

    const success = await onSubmit(filledIdeas);
    if (success) {
      setManualIdeas(['', '', '']);
    }
  };

  const hasIdeas = manualIdeas.some((idea) => idea.trim() !== '');

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-6">
      <h2 className="text-lg font-semibold text-blue-800 mb-3">
        {t('step4.manualEntry.title')}
      </h2>
      <p className="text-blue-700 mb-4">{t('step4.manualEntry.message')}</p>
      <div className="space-y-3">
        {manualIdeas.map((idea, index) => (
          <div key={index}>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('step4.manualEntry.ideaLabel', { number: index + 1 })}{' '}
              {index === 0 && <span className="text-red-500">*</span>}
            </label>
            <textarea
              value={idea}
              onChange={(e) => handleIdeaChange(index, e.target.value)}
              placeholder={t('step4.manualEntry.ideaPlaceholder')}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows="2"
            />
          </div>
        ))}
      </div>
      <button
        onClick={handleSubmit}
        disabled={submitting || !hasIdeas}
        className="mt-4 w-full bg-blue-600 text-white py-2 px-6 rounded-md hover:bg-blue-700 disabled:bg-gray-300 transition-colors font-medium"
      >
        {submitting ? t('common.submitting') : t('step4.manualEntry.submitIdeas')}
      </button>
    </div>
  );
};

export default ManualIdeasEntry;
