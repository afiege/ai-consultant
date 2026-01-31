import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { QRCodeSVG } from 'qrcode.react';

const CollaborativeModePanel = ({
  sessionUuid,
  collaborativeMode,
  isOwner,
  participants,
  consultationStarted,
  onToggleMode,
}) => {
  const { t } = useTranslation();
  const [showSharePanel, setShowSharePanel] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);

  const shareUrl = `${window.location.origin}/session/${sessionUuid}/step4`;

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    } catch (err) {
      // Fallback for older browsers
      const textArea = document.createElement('textarea');
      textArea.value = shareUrl;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    }
  };

  return (
    <div className="mb-6 bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <h3 className="font-semibold text-gray-900">
            {t('step4.collaborative.title')}
          </h3>
          {isOwner && (
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={collaborativeMode}
                onChange={onToggleMode}
                className="sr-only peer"
                disabled={consultationStarted}
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          )}
          {!isOwner && collaborativeMode && (
            <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
              {t('step4.collaborative.active')}
            </span>
          )}
        </div>
        {collaborativeMode && (
          <button
            onClick={() => setShowSharePanel(!showSharePanel)}
            className="text-blue-600 hover:text-blue-800 text-sm font-medium"
          >
            {showSharePanel
              ? t('step4.collaborative.hideShare')
              : t('step4.collaborative.showShare')}
          </button>
        )}
      </div>

      {collaborativeMode && (
        <p className="text-sm text-gray-600 mt-2">
          {t('step4.collaborative.description')}
        </p>
      )}

      {/* Participants List */}
      {collaborativeMode && participants.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {participants.map((p) => (
            <span
              key={p.uuid}
              className={`px-3 py-1 rounded-full text-xs font-medium ${
                p.is_owner
                  ? 'bg-yellow-100 text-yellow-800'
                  : 'bg-blue-100 text-blue-800'
              }`}
            >
              {p.name} {p.is_owner && '(Owner)'}
            </span>
          ))}
        </div>
      )}

      {/* Share Panel with QR Code */}
      {collaborativeMode && showSharePanel && (
        <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
          <div className="flex flex-col md:flex-row items-center gap-4">
            <div className="bg-white p-3 rounded-lg border border-gray-200">
              <QRCodeSVG
                value={shareUrl}
                size={120}
                level="M"
                includeMargin={true}
              />
            </div>
            <div className="flex-1 space-y-3">
              <p className="text-sm text-gray-600">
                {t('step4.collaborative.shareInstructions')}
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  readOnly
                  value={shareUrl}
                  className="flex-1 px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-600 truncate"
                />
                <button
                  onClick={handleCopyLink}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    linkCopied
                      ? 'bg-green-600 text-white'
                      : 'bg-blue-600 text-white hover:bg-blue-700'
                  }`}
                >
                  {linkCopied ? t('common.copied') : t('common.copy')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CollaborativeModePanel;
