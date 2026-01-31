import React from 'react';
import { useTranslation } from 'react-i18next';

const ChatInput = ({
  value,
  onChange,
  onSubmit,
  onSummarize,
  onRequestAiResponse,
  disabled,
  summarizing,
  collaborativeMode,
  messageCount,
}) => {
  const { t } = useTranslation();

  const handleSubmit = (e) => {
    e.preventDefault();
    if (value.trim() && !disabled) {
      onSubmit(e);
    }
  };

  return (
    <div className="border-t p-4">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={
            collaborativeMode
              ? t('step4.chat.collaborativePlaceholder')
              : t('step4.chat.messagePlaceholder')
          }
          disabled={disabled}
          className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-300 transition-colors"
        >
          {t('common.send')}
        </button>
      </form>
      <div className="mt-2 flex justify-between items-center">
        {/* Request AI Response button for collaborative mode */}
        {collaborativeMode && onRequestAiResponse && (
          <button
            onClick={onRequestAiResponse}
            disabled={disabled || messageCount < 2}
            className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-300 transition-colors text-sm font-medium"
          >
            {disabled
              ? t('step4.chat.thinking')
              : t('step4.chat.requestAiResponse')}
          </button>
        )}
        <div className={collaborativeMode ? '' : 'ml-auto'}>
          <button
            onClick={onSummarize}
            disabled={summarizing || messageCount < 4}
            className="text-sm text-blue-600 hover:text-blue-800 disabled:text-gray-400"
          >
            {summarizing
              ? t('step4.chat.generatingSummary')
              : t('step4.chat.generateSummary')}
          </button>
        </div>
      </div>
      {collaborativeMode && (
        <p className="mt-2 text-xs text-gray-500">
          {t('step4.chat.collaborativeHint')}
        </p>
      )}
    </div>
  );
};

export default ChatInput;
