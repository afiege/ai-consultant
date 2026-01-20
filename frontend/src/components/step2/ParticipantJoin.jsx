import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

const ParticipantJoin = ({ onJoin, participants, sessionStarted }) => {
  const { t } = useTranslation();
  const [name, setName] = useState('');
  const [joining, setJoining] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;

    setJoining(true);
    try {
      await onJoin(name);
    } catch (error) {
      alert(error.message || 'Failed to join session');
    } finally {
      setJoining(false);
    }
  };

  const humanCount = participants.filter(p => !p.is_ai).length;
  const aiCount = participants.filter(p => p.is_ai).length;

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-white rounded-lg shadow-lg p-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">
          {t('step2.join.title')}
        </h2>

        {sessionStarted ? (
          <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
            <p className="text-yellow-800">
              {t('step2.join.sessionStarted')}
            </p>
          </div>
        ) : (
          <>
            <p className="text-gray-600 mb-6">
              {t('step2.join.description')}
            </p>

            {/* Current Participants */}
            {participants.length > 0 && (
              <div className="mb-6 p-4 bg-blue-50 rounded-md">
                <h3 className="font-semibold text-gray-900 mb-2">
                  {t('step2.join.participants')} ({participants.length}/6)
                </h3>
                <div className="space-y-1">
                  {participants.map((p) => (
                    <div key={p.uuid} className="flex items-center text-sm">
                      {p.is_ai ? (
                        <span className="text-blue-600">🤖 {p.name}</span>
                      ) : (
                        <span className="text-gray-700">👤 {p.name}</span>
                      )}
                    </div>
                  ))}
                </div>
                <p className="text-xs text-gray-600 mt-2">
                  {t('step2.join.humanCount', { count: humanCount })}
                  {aiCount > 0 && `, ${t('step2.join.aiCount', { count: aiCount })}`}
                </p>
              </div>
            )}

            {/* Join Form */}
            <form onSubmit={handleSubmit}>
              <div className="mb-4">
                <label htmlFor="participant-name" className="block text-sm font-medium text-gray-700 mb-2">
                  {t('step2.join.nameLabel')}
                </label>
                <input
                  type="text"
                  id="participant-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={t('step2.join.namePlaceholder')}
                  className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={joining || participants.length >= 6}
                  required
                />
              </div>

              <button
                type="submit"
                disabled={!name.trim() || joining || participants.length >= 6}
                className="w-full bg-blue-600 text-white py-3 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium"
              >
                {joining ? t('step2.join.joining') : participants.length >= 6 ? t('step2.join.sessionFull') : t('step2.join.joinButton')}
              </button>
            </form>

            <div className="mt-6 p-4 bg-gray-50 rounded-md">
              <p className="text-sm text-gray-700">
                <span className="font-semibold">{t('step2.join.howItWorks')}</span>
              </p>
              <ul className="text-sm text-gray-600 mt-2 space-y-1 list-disc list-inside">
                <li>{t('step2.join.rule1')}</li>
                <li>{t('step2.join.rule2')}</li>
                <li>{t('step2.join.rule3')}</li>
                <li>{t('step2.join.rule4')}</li>
                <li>{t('step2.join.rule5')}</li>
              </ul>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default ParticipantJoin;
