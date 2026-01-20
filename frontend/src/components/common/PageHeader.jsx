import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ExpertSettingsModal } from '../expert';
import { sessionBackupAPI } from '../../services/api';

const CogIcon = ({ className }) => (
  <svg
    className={className}
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
    />
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
    />
  </svg>
);

const DownloadIcon = ({ className }) => (
  <svg
    className={className}
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
    />
  </svg>
);

const PageHeader = ({
  title,
  subtitle,
  sessionUuid,
  showSettings = true,
  showSaveButton = true,
  children,
}) => {
  const { t } = useTranslation();
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleSaveSession = async () => {
    if (!sessionUuid || saving) return;

    setSaving(true);
    try {
      await sessionBackupAPI.exportBackup(sessionUuid);
    } catch (err) {
      console.error('Failed to save session:', err);
      alert(t('errors.failedToSave'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
              {subtitle && (
                <p className="mt-1 text-sm text-gray-600">{subtitle}</p>
              )}
            </div>
            <div className="flex items-center gap-3">
              {children}
              {showSaveButton && sessionUuid && (
                <button
                  onClick={handleSaveSession}
                  disabled={saving}
                  className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-full transition-colors disabled:opacity-50"
                  title={t('common.saveSession')}
                >
                  {saving ? (
                    <svg className="animate-spin w-6 h-6" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                  ) : (
                    <DownloadIcon className="w-6 h-6" />
                  )}
                </button>
              )}
              {showSettings && sessionUuid && (
                <button
                  onClick={() => setShowSettingsModal(true)}
                  className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-full transition-colors"
                  title={t('expertSettings.title')}
                >
                  <CogIcon className="w-6 h-6" />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {showSettings && sessionUuid && (
        <ExpertSettingsModal
          isOpen={showSettingsModal}
          onClose={() => setShowSettingsModal(false)}
          sessionUuid={sessionUuid}
        />
      )}
    </>
  );
};

export default PageHeader;
