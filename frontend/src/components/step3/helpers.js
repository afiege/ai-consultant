/**
 * Shared helper functions for Step 3 prioritization components.
 */

/** Convert low/medium/high to numeric values for scatter plots. */
export const levelToNumber = (level) => {
  const mapping = { low: 1, medium: 2, high: 3 };
  return mapping[level] || 2;
};

/** Get maturity style config (fill color, icon, label) for scatter plot dots. */
export const getMaturityStyle = (level) => {
  const styles = {
    high: {
      fill: '#16a34a',
      fillHover: '#15803d',
      icon: '✓',
      label: 'Well-suited',
    },
    medium: {
      fill: '#ca8a04',
      fillHover: '#a16207',
      icon: '◐',
      label: 'Moderate',
    },
    low: {
      fill: '#dc2626',
      fillHover: '#b91c1c',
      icon: '!',
      label: 'Ambitious',
    },
  };
  return styles[level] || styles.medium;
};

/** Get card border/bg color classes based on vote count. */
export const getCardColorClasses = (votes, baseColor = 'blue') => {
  if (baseColor === 'blue') {
    if (votes === 0) return 'border-transparent bg-white hover:border-gray-200';
    if (votes === 1) return 'border-blue-300 bg-blue-50';
    return 'border-blue-500 bg-blue-100';
  } else {
    if (votes === 0) return 'border-transparent bg-white hover:border-gray-200';
    if (votes === 1) return 'border-purple-300 bg-purple-50';
    return 'border-purple-500 bg-purple-100';
  }
};
