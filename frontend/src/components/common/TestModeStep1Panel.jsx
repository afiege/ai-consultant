import React, { useState, useEffect } from 'react';
import { testModeAPI } from '../../services/api';

/**
 * TestModeStep1Panel - A collapsible panel for automated testing in Step 1
 *
 * Props:
 * - activeTab: 'profile' | 'maturity' - Current tab in Step 1
 * - onFillCompanyProfile: Callback with company profile text
 * - onFillMaturityScores: Callback with maturity scores object
 * - disabled: Disable the panel
 */
const TestModeStep1Panel = ({
  activeTab = 'profile',
  onFillCompanyProfile,
  onFillMaturityScores,
  disabled = false
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [personas, setPersonas] = useState([]);
  const [selectedPersona, setSelectedPersona] = useState('');
  const [loading, setLoading] = useState(false);
  const [filling, setFilling] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Load personas on mount
  useEffect(() => {
    loadPersonas();
  }, []);

  // Store selected persona in localStorage
  useEffect(() => {
    if (selectedPersona) {
      localStorage.setItem('test_mode_persona', selectedPersona);
    }
  }, [selectedPersona]);

  // Restore selected persona from localStorage
  useEffect(() => {
    const stored = localStorage.getItem('test_mode_persona');
    if (stored && personas.some(p => p.persona_id === stored)) {
      setSelectedPersona(stored);
    }
  }, [personas]);

  const loadPersonas = async () => {
    setLoading(true);
    try {
      const response = await testModeAPI.getPersonas();
      setPersonas(response.data);
      if (response.data.length > 0 && !selectedPersona) {
        const stored = localStorage.getItem('test_mode_persona');
        if (stored && response.data.some(p => p.persona_id === stored)) {
          setSelectedPersona(stored);
        } else {
          setSelectedPersona(response.data[0].persona_id);
        }
      }
    } catch (err) {
      console.error('Failed to load personas:', err);
      setError('Failed to load test personas');
    } finally {
      setLoading(false);
    }
  };

  const handleFillCompanyProfile = async () => {
    if (!selectedPersona) {
      setError('Please select a persona');
      return;
    }

    setFilling(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await testModeAPI.getCompanyProfile(selectedPersona);
      if (onFillCompanyProfile) {
        onFillCompanyProfile(response.data.profile_text);
        setSuccess(`Filled company profile for ${response.data.company_name}`);
      }
    } catch (err) {
      console.error('Failed to get company profile:', err);
      setError('Failed to get company profile');
    } finally {
      setFilling(false);
    }
  };

  const handleFillMaturityScores = async () => {
    if (!selectedPersona) {
      setError('Please select a persona');
      return;
    }

    setFilling(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await testModeAPI.getMaturityAssessment(selectedPersona);
      if (onFillMaturityScores) {
        onFillMaturityScores(response.data.scores);
        setSuccess(`Filled maturity scores for ${response.data.company_name} (Level ${response.data.maturity_level}: ${response.data.maturity_level_name})`);
      }
    } catch (err) {
      console.error('Failed to get maturity assessment:', err);
      setError('Failed to get maturity assessment');
    } finally {
      setFilling(false);
    }
  };

  const selectedPersonaData = personas.find(p => p.persona_id === selectedPersona);

  if (!isExpanded) {
    return (
      <button
        onClick={() => setIsExpanded(true)}
        className="fixed bottom-4 right-4 bg-purple-600 text-white px-4 py-2 rounded-lg shadow-lg hover:bg-purple-700 transition-colors flex items-center gap-2 z-50"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
        Test Mode
      </button>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 w-96 bg-white rounded-lg shadow-2xl border border-purple-200 z-50">
      {/* Header */}
      <div className="bg-purple-600 text-white px-4 py-3 rounded-t-lg flex justify-between items-center">
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          <span className="font-semibold">Test Mode - Step 1</span>
        </div>
        <button
          onClick={() => setIsExpanded(false)}
          className="text-white hover:text-purple-200"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4 max-h-[500px] overflow-y-auto">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
            {error}
          </div>
        )}

        {success && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-3 py-2 rounded text-sm">
            {success}
          </div>
        )}

        {/* Persona Selector */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Select Persona
          </label>
          <select
            value={selectedPersona}
            onChange={(e) => setSelectedPersona(e.target.value)}
            disabled={loading || filling}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm"
          >
            {personas.map((persona) => (
              <option key={persona.persona_id} value={persona.persona_id}>
                {persona.company_name} ({persona.industry})
              </option>
            ))}
          </select>
        </div>

        {/* Selected Persona Info */}
        {selectedPersonaData && (
          <div className="bg-purple-50 p-3 rounded-md text-sm">
            <p className="font-medium text-purple-900">{selectedPersonaData.company_name}</p>
            <p className="text-purple-700">{selectedPersonaData.employees} employees</p>
            <p className="text-purple-600 text-xs mt-1">Focus: {selectedPersonaData.focus_idea}</p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="space-y-2">
          {activeTab === 'profile' ? (
            <button
              onClick={handleFillCompanyProfile}
              disabled={disabled || filling || !selectedPersona}
              className="w-full bg-purple-600 text-white py-2 px-4 rounded-md hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {filling ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Filling...
                </span>
              ) : (
                'Fill Company Profile'
              )}
            </button>
          ) : (
            <button
              onClick={handleFillMaturityScores}
              disabled={disabled || filling || !selectedPersona}
              className="w-full bg-purple-600 text-white py-2 px-4 rounded-md hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {filling ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Filling...
                </span>
              ) : (
                'Fill Maturity Assessment'
              )}
            </button>
          )}
        </div>

        {/* Instructions */}
        <div className="text-xs text-gray-500 border-t pt-3">
          <p className="font-medium mb-1">How it works:</p>
          <ul className="list-disc list-inside space-y-1">
            <li>Select a test persona (company profile)</li>
            {activeTab === 'profile' ? (
              <li>Click "Fill Company Profile" to add company info</li>
            ) : (
              <li>Click "Fill Maturity Assessment" to set scores</li>
            )}
            <li>The data comes from benchmark test personas</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default TestModeStep1Panel;
