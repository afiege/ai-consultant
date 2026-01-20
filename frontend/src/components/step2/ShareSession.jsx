import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { QRCodeSVG } from 'qrcode.react';

const ShareSession = ({ sessionUuid }) => {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  const shareUrl = `${window.location.origin}/session/${sessionUuid}/step2`;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      // Fallback for older browsers
      const textArea = document.createElement('textarea');
      textArea.value = shareUrl;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        {t('step2.share.title')}
      </h3>

      <div className="flex flex-col items-center space-y-4">
        {/* QR Code */}
        <div className="bg-white p-4 rounded-lg border-2 border-gray-200">
          <QRCodeSVG
            value={shareUrl}
            size={180}
            level="M"
            includeMargin={true}
          />
        </div>

        <p className="text-sm text-gray-600 text-center">
          {t('step2.share.scanQR')}
        </p>

        {/* Shareable Link */}
        <div className="w-full">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('step2.share.orCopyLink')}
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              readOnly
              value={shareUrl}
              className="flex-1 px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-sm text-gray-600 truncate"
            />
            <button
              onClick={handleCopy}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                copied
                  ? 'bg-green-600 text-white'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              }`}
            >
              {copied ? t('step2.share.copied') : t('step2.share.copy')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ShareSession;
