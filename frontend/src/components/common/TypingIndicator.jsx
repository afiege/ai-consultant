import React from 'react';

const TypingIndicator = ({ className = '' }) => {
  return (
    <div className={`flex items-center space-x-1.5 p-3 bg-gray-100 rounded-lg w-16 ${className}`}>
      <div
        className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
        style={{ animationDelay: '0ms', animationDuration: '1s' }}
      />
      <div
        className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
        style={{ animationDelay: '150ms', animationDuration: '1s' }}
      />
      <div
        className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
        style={{ animationDelay: '300ms', animationDuration: '1s' }}
      />
    </div>
  );
};

export default TypingIndicator;
