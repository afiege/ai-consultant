import React from 'react';

export const EmptyState = ({ message }) => (
  <div className="text-center py-8">
    <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
    <p className="text-gray-500 italic">{message}</p>
  </div>
);

export const GenerateButton = ({ onClick, loading, colorClass, children }) => (
  <button
    onClick={onClick}
    disabled={loading}
    className={`${colorClass} text-white px-6 py-3 rounded-md disabled:bg-gray-300 transition-colors font-medium flex items-center gap-2 mx-auto`}
  >
    {loading && (
      <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
    )}
    {children}
  </button>
);

export const DimensionScore = ({ label, score }) => (
  <div className="bg-white/50 rounded-lg p-3">
    <p className="text-sm text-gray-600 mb-1">{label}</p>
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-200 rounded-full h-2">
        <div
          className="bg-purple-500 h-2 rounded-full"
          style={{ width: `${(score / 6) * 100}%` }}
        />
      </div>
      <span className="font-medium text-gray-700">{score?.toFixed(1)}</span>
    </div>
  </div>
);
