import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { reflectionAPI } from '../../services/api';

/**
 * ReflectionModal — shown between major steps (P6 / DP8).
 * Prompts the user to reflect on what they learned.
 *
 * Props:
 *   sessionUuid  — current session UUID
 *   stepKey      — e.g. "step3", "step4"
 *   open         — boolean controlling visibility
 *   onClose      — called when the user dismisses the modal
 */
const ReflectionModal = ({ sessionUuid, stepKey, open, onClose }) => {
  const { t } = useTranslation();
  const [surprised, setSurprised] = useState('');
  const [confidence, setConfidence] = useState(3);
  const [explore, setExplore] = useState('');
  const [saving, setSaving] = useState(false);

  // Load existing reflection if any
  useEffect(() => {
    if (!open || !sessionUuid || !stepKey) return;
    reflectionAPI.getAll(sessionUuid).then((res) => {
      const data = res.data?.[stepKey];
      if (data) {
        setSurprised(data.surprised || '');
        setConfidence(data.confidence ?? 3);
        setExplore(data.explore || '');
      }
    }).catch(() => {});
  }, [open, sessionUuid, stepKey]);

  if (!open) return null;

  const handleSave = async () => {
    setSaving(true);
    try {
      await reflectionAPI.save(sessionUuid, stepKey, {
        surprised,
        confidence,
        explore,
      });
    } catch {
      // non-critical — don't block the user
    } finally {
      setSaving(false);
      onClose();
    }
  };

  const handleSkip = () => {
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full mx-4 p-6 space-y-5 animate-in fade-in">
        {/* Header */}
        <div className="text-center">
          <span className="inline-block text-3xl mb-2">💡</span>
          <h2 className="text-xl font-bold text-gray-900">{t('reflection.title')}</h2>
          <p className="text-sm text-gray-500 mt-1">{t('reflection.subtitle')}</p>
        </div>

        {/* Q1: What surprised you? */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('reflection.surprisedLabel')}
          </label>
          <textarea
            value={surprised}
            onChange={(e) => setSurprised(e.target.value)}
            rows={2}
            className="w-full border border-gray-300 rounded-lg p-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder={t('reflection.surprisedPlaceholder')}
          />
        </div>

        {/* Q2: Confidence slider */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('reflection.confidenceLabel')}
          </label>
          <input
            type="range"
            min={1}
            max={5}
            value={confidence}
            onChange={(e) => setConfidence(Number(e.target.value))}
            className="w-full accent-blue-600"
          />
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>{t('reflection.confidenceLow')}</span>
            <span className="font-medium text-blue-600">{confidence}/5</span>
            <span>{t('reflection.confidenceHigh')}</span>
          </div>
        </div>

        {/* Q3: What to explore further? */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('reflection.exploreLabel')}
          </label>
          <textarea
            value={explore}
            onChange={(e) => setExplore(e.target.value)}
            rows={2}
            className="w-full border border-gray-300 rounded-lg p-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder={t('reflection.explorePlaceholder')}
          />
        </div>

        {/* Buttons */}
        <div className="flex gap-3 pt-2">
          <button
            onClick={handleSkip}
            className="flex-1 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            {t('reflection.skip')}
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:bg-gray-300"
          >
            {saving ? t('common.saving') : t('reflection.save')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ReflectionModal;
