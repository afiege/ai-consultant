import React, { useState } from 'react';

const InfoIcon = ({ className }) => (
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
      d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
    />
  </svg>
);

const ChevronIcon = ({ className, isOpen }) => (
  <svg
    className={`${className} transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M19 9l-7 7-7-7"
    />
  </svg>
);

/**
 * ExplanationBox - A collapsible component for providing contextual help
 *
 * @param {string} title - The title/header for the explanation section
 * @param {string} description - Main explanatory text
 * @param {Array<string>} bullets - Optional list of bullet points
 * @param {string} tip - Optional tip shown at the bottom
 * @param {boolean} defaultOpen - Whether the box is expanded by default (default: true)
 * @param {string} variant - Color variant: 'blue' (default), 'green', 'yellow'
 */
const ExplanationBox = ({
  title,
  description,
  bullets = [],
  tip,
  defaultOpen = true,
  variant = 'blue',
}) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  const variantStyles = {
    blue: {
      container: 'bg-blue-50 border-blue-200',
      icon: 'text-blue-500',
      title: 'text-blue-900',
      text: 'text-blue-800',
      bullet: 'text-blue-400',
      tip: 'bg-blue-100 text-blue-700',
    },
    green: {
      container: 'bg-green-50 border-green-200',
      icon: 'text-green-500',
      title: 'text-green-900',
      text: 'text-green-800',
      bullet: 'text-green-400',
      tip: 'bg-green-100 text-green-700',
    },
    yellow: {
      container: 'bg-yellow-50 border-yellow-200',
      icon: 'text-yellow-600',
      title: 'text-yellow-900',
      text: 'text-yellow-800',
      bullet: 'text-yellow-500',
      tip: 'bg-yellow-100 text-yellow-700',
    },
  };

  const styles = variantStyles[variant] || variantStyles.blue;

  return (
    <div className={`rounded-lg border ${styles.container} mb-6`}>
      {/* Header - always visible */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 text-left focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 rounded-lg"
      >
        <div className="flex items-center">
          <InfoIcon className={`w-5 h-5 ${styles.icon} mr-3 flex-shrink-0`} />
          <span className={`font-medium ${styles.title}`}>{title}</span>
        </div>
        <ChevronIcon className={`w-5 h-5 ${styles.icon}`} isOpen={isOpen} />
      </button>

      {/* Expandable content */}
      {isOpen && (
        <div className="px-4 pb-4 pt-0">
          <div className="pl-8">
            {/* Main description */}
            {description && (
              <p className={`${styles.text} text-sm mb-3`}>{description}</p>
            )}

            {/* Bullet points */}
            {bullets.length > 0 && (
              <ul className="space-y-2 mb-3">
                {bullets.map((bullet, index) => (
                  <li key={index} className="flex items-start">
                    <span className={`${styles.bullet} mr-2 mt-1`}>•</span>
                    <span className={`${styles.text} text-sm`}>{bullet}</span>
                  </li>
                ))}
              </ul>
            )}

            {/* Tip */}
            {tip && (
              <div className={`${styles.tip} rounded-md p-3 text-sm mt-3`}>
                <strong>Tip:</strong> {tip}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default ExplanationBox;
