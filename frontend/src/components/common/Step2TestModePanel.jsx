import React, { useState, useEffect } from 'react';
import { testModeAPI, apiKeyManager } from '../../services/api';

/**
 * Step2TestModePanel - Test mode panel for 6-3-5 brainwriting
 * Generates ideas automatically based on selected persona
 */
const Step2TestModePanel = ({
  sessionUuid,
  onIdeasGenerated,
  previousIdeas = [],
  roundNumber = 1,
  disabled = false,
  sessionStarted = false
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [personas, setPersonas] = useState([]);
  const [selectedPersona, setSelectedPersona] = useState('');
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generatedIdeas, setGeneratedIdeas] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadPersonas();
  }, []);

  useEffect(() => {
    if (selectedPersona) {
      localStorage.setItem('test_mode_persona', selectedPersona);
    }
  }, [selectedPersona]);

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

  const handleGenerateIdeas = async () => {
    if (!selectedPersona || !apiKeyManager.isSet()) {
      setError('Please select a persona and ensure API key is set');
      return;
    }

    setGenerating(true);
    setGeneratedIdeas([]);
    setError(null);

    try {
      const response = await testModeAPI.generateIdeas(
        sessionUuid,
        selectedPersona,
        roundNumber,
        previousIdeas
      );
      setGeneratedIdeas(response.data.ideas || []);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to generate ideas');
    } finally {
      setGenerating(false);
    }
  };

  const handleUseIdeas = () => {
    if (generatedIdeas.length > 0 && onIdeasGenerated) {
      onIdeasGenerated(generatedIdeas);
      setGeneratedIdeas([]);
    }
  };

  const handleAutoGenerate = async () => {
    if (!selectedPersona || !apiKeyManager.isSet()) {
      setError('Please select a persona and ensure API key is set');
      return;
    }

    setGenerating(true);
    setError(null);

    try {
      const response = await testModeAPI.generateIdeas(
        sessionUuid,
        selectedPersona,
        roundNumber,
        previousIdeas
      );
      const ideas = response.data.ideas || [];
      if (ideas.length > 0 && onIdeasGenerated) {
        onIdeasGenerated(ideas);
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to generate ideas');
    } finally {
      setGenerating(false);
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
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          <span className="font-semibold">Test Mode - Ideas</span>
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

        {/* Persona Selector */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Select Persona
          </label>
          <select
            value={selectedPersona}
            onChange={(e) => setSelectedPersona(e.target.value)}
            disabled={loading || generating}
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

        {/* Round Info */}
        {sessionStarted && (
          <div className="bg-blue-50 p-2 rounded text-sm text-blue-800">
            Round {roundNumber} • {previousIdeas.length > 0 ? `Building on ${previousIdeas.length} previous ideas` : 'Starting fresh'}
          </div>
        )}

        {/* Action Buttons */}
        {sessionStarted && (
          <div className="space-y-2">
            <button
              onClick={handleAutoGenerate}
              disabled={disabled || generating || !selectedPersona}
              className="w-full bg-purple-600 text-white py-2 px-4 rounded-md hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {generating ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Generating...
                </span>
              ) : (
                'Auto-Generate & Submit Ideas'
              )}
            </button>

            <button
              onClick={handleGenerateIdeas}
              disabled={disabled || generating || !selectedPersona}
              className="w-full bg-gray-100 text-gray-700 py-2 px-3 rounded-md hover:bg-gray-200 disabled:bg-gray-50 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors text-sm"
            >
              Preview Ideas First
            </button>
          </div>
        )}

        {/* Generated Ideas Preview */}
        {generatedIdeas.length > 0 && (
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">
              Generated Ideas:
            </label>
            <div className="bg-gray-50 p-3 rounded-md text-sm text-gray-700 space-y-2 border">
              {generatedIdeas.map((idea, idx) => (
                <p key={idx} className="text-xs">
                  <span className="font-medium">{idx + 1}.</span> {idea}
                </p>
              ))}
            </div>
            <button
              onClick={handleUseIdeas}
              disabled={generating}
              className="w-full bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700 disabled:bg-gray-300 transition-colors text-sm"
            >
              Use These Ideas
            </button>
          </div>
        )}

        {/* Instructions */}
        {!sessionStarted && (
          <div className="bg-yellow-50 p-3 rounded-md text-sm text-yellow-800">
            <p className="font-medium">Start the session first</p>
            <p className="text-xs mt-1">The test mode will help auto-generate ideas for each round.</p>
          </div>
        )}

        <div className="text-xs text-gray-500 border-t pt-3">
          <p className="font-medium mb-1">How it works:</p>
          <ul className="list-disc list-inside space-y-1">
            <li>Select a test persona (company profile)</li>
            <li>Click "Auto-Generate" to create 3 ideas</li>
            <li>Ideas build on previous round's suggestions</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default Step2TestModePanel;
