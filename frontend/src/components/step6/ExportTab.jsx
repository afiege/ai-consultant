import React from 'react';

const ExportTab = ({ t, onExportPDF, exporting, hasAllFindings }) => {
  const completedCount = Object.values(hasAllFindings).filter(Boolean).length;
  const totalCount = Object.keys(hasAllFindings).length;

  return (
    <div className="space-y-6">
      <div className="bg-emerald-50 rounded-lg p-4 mb-6">
        <h4 className="font-medium text-emerald-800 mb-2">{t('step6.export.readiness')}</h4>
        <p className="text-emerald-700">
          {completedCount}/{totalCount} {t('step6.export.sectionsComplete')}
        </p>
        <div className="mt-2 bg-emerald-200 rounded-full h-2">
          <div
            className="bg-emerald-600 h-2 rounded-full transition-all"
            style={{ width: `${(completedCount / totalCount) * 100}%` }}
          />
        </div>
      </div>

      <button
        onClick={onExportPDF}
        disabled={exporting}
        className="w-full flex items-center justify-center gap-3 bg-emerald-600 text-white px-6 py-4 rounded-md hover:bg-emerald-700 disabled:bg-gray-300 transition-colors font-medium"
      >
        {exporting ? (
          <>
            <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {t('step6.export.generating')}
          </>
        ) : (
          <>
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            {t('step6.export.downloadPDF')}
          </>
        )}
      </button>

      <p className="text-sm text-gray-500 text-center">
        {t('step6.export.pdfNote')}
      </p>
    </div>
  );
};

export default ExportTab;
