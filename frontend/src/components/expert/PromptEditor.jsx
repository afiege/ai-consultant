import React, { useState, useEffect } from 'react';

const PromptEditor = ({
  promptKey,
  label,
  description,
  variables,
  customValue,
  defaultValue,
  onChange,
  onReset,
  disabled = false,
}) => {
  const [localValue, setLocalValue] = useState('');
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    // Use custom value if set, otherwise show default
    setLocalValue(customValue || defaultValue || '');
  }, [customValue, defaultValue]);

  const handleChange = (e) => {
    setLocalValue(e.target.value);
  };

  const handleBlur = () => {
    // Only call onChange if value differs from default
    if (localValue !== defaultValue) {
      onChange(promptKey, localValue);
    } else {
      onChange(promptKey, null); // Reset to default
    }
  };

  const handleReset = () => {
    setLocalValue(defaultValue || '');
    onChange(promptKey, null);
    if (onReset) {
      onReset(promptKey);
    }
  };

  const isCustomized = customValue && customValue !== defaultValue;

  return (
    <div className="border rounded-lg p-4 bg-white">
      <div className="flex justify-between items-start mb-2">
        <div>
          <h4 className="font-medium text-gray-900">{label}</h4>
          <p className="text-sm text-gray-500">{description}</p>
        </div>
        <div className="flex items-center gap-2">
          {isCustomized && (
            <span className="px-2 py-1 text-xs font-medium bg-yellow-100 text-yellow-800 rounded">
              Customized
            </span>
          )}
          {isCustomized && (
            <button
              type="button"
              onClick={handleReset}
              disabled={disabled}
              className="text-sm text-blue-600 hover:text-blue-800 disabled:opacity-50"
            >
              Reset to Default
            </button>
          )}
        </div>
      </div>

      {variables && variables.length > 0 && (
        <div className="mb-2 text-xs text-gray-500">
          <span className="font-medium">Available variables: </span>
          {variables.map((v, i) => (
            <code key={v} className="bg-gray-100 px-1 rounded">
              {'{' + v + '}'}
              {i < variables.length - 1 && ', '}
            </code>
          ))}
        </div>
      )}

      <textarea
        value={localValue}
        onChange={handleChange}
        onBlur={handleBlur}
        disabled={disabled}
        placeholder="Enter custom prompt..."
        className={`w-full h-48 p-3 border rounded-md font-mono text-sm resize-y ${
          disabled
            ? 'bg-gray-100 cursor-not-allowed'
            : 'bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
        } ${isCustomized ? 'border-yellow-400' : 'border-gray-300'}`}
      />

      <div className="mt-2 flex justify-between items-center text-xs text-gray-500">
        <span>
          {localValue.length} characters
        </span>
        {!isEditing && !isCustomized && (
          <span className="text-gray-400">
            Showing default prompt (edit to customize)
          </span>
        )}
      </div>
    </div>
  );
};

export default PromptEditor;
