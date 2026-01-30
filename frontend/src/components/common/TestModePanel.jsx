import React, { useState, useEffect } from 'react';
import { testModeAPI, apiKeyManager } from '../../services/api';

/**
 * TestModePanel - A collapsible panel for automated testing with personas
 *
 * Props:
 * - sessionUuid: Current session UUID
 * - messageType: 'consultation' | 'business_case' | 'cost_estimation'
 * - onResponseGenerated: Callback with generated response text
 * - disabled: Disable the panel (e.g., when sending a message)
 * - consultationStarted: Whether the consultation has started
 */
const TestModePanel = ({
  sessionUuid,
  messageType = 'consultation',
  onResponseGenerated,
  disabled = false,
  consultationStarted = false
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [personas, setPersonas] = useState([]);
  const [selectedPersona, setSelectedPersona] = useState('');
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generatedResponse, setGeneratedResponse] = useState('');
  const [error, setError] = useState(null);
  const [autoMode, setAutoMode] = useState(false);

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

  const handleGenerateResponse = async () => {
    if (!selectedPersona || !apiKeyManager.isSet()) {
      setError('Please select a persona and ensure API key is set');
      return;
    }

    setGenerating(true);
    setGeneratedResponse('');
    setError(null);

    try {
      await testModeAPI.generateResponseStream(
        sessionUuid,
        selectedPersona,
        messageType,
        (chunk) => {
          setGeneratedResponse(prev => prev + chunk);
        },
        () => {
          setGenerating(false);
        },
        (errorMsg) => {
          setError(errorMsg);
          setGenerating(false);
        }
      );
    } catch (err) {
      setError(err.message);
      setGenerating(false);
    }
  };

  const handleUseResponse = () => {
    if (generatedResponse && onResponseGenerated) {
      onResponseGenerated(generatedResponse);
      setGeneratedResponse('');
    }
  };

  const handleAutoRespond = async () => {
    // Generate and automatically use the response
    if (!selectedPersona || !apiKeyManager.isSet()) {
      setError('Please select a persona and ensure API key is set');
      return;
    }

    setGenerating(true);
    setError(null);
    let fullResponse = '';

    try {
      await testModeAPI.generateResponseStream(
        sessionUuid,
        selectedPersona,
        messageType,
        (chunk) => {
          fullResponse += chunk;
          setGeneratedResponse(fullResponse);
        },
        () => {
          setGenerating(false);
          if (fullResponse && onResponseGenerated) {
            onResponseGenerated(fullResponse);
            setGeneratedResponse('');
          }
        },
        (errorMsg) => {
          setError(errorMsg);
          setGenerating(false);
        }
      );
    } catch (err) {
      setError(err.message);
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
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          <span className="font-semibold">Test Mode</span>
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

        {/* Action Buttons */}
        {consultationStarted && (
          <div className="space-y-2">
            <button
              onClick={handleAutoRespond}
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
                'Auto-Respond as Persona'
              )}
            </button>

            <div className="flex gap-2">
              <button
                onClick={handleGenerateResponse}
                disabled={disabled || generating || !selectedPersona}
                className="flex-1 bg-gray-100 text-gray-700 py-2 px-3 rounded-md hover:bg-gray-200 disabled:bg-gray-50 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors text-sm"
              >
                Preview Response
              </button>
            </div>
          </div>
        )}

        {/* Generated Response Preview */}
        {generatedResponse && (
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">
              Generated Response:
            </label>
            <div className="bg-gray-50 p-3 rounded-md text-sm text-gray-700 max-h-32 overflow-y-auto border">
              {generatedResponse}
            </div>
            <button
              onClick={handleUseResponse}
              disabled={generating}
              className="w-full bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700 disabled:bg-gray-300 transition-colors text-sm"
            >
              Use This Response
            </button>
          </div>
        )}

        {/* Instructions */}
        {!consultationStarted && (
          <div className="bg-yellow-50 p-3 rounded-md text-sm text-yellow-800">
            <p className="font-medium">Start the consultation first</p>
            <p className="text-xs mt-1">The test mode will help you auto-respond to the consultant's questions.</p>
          </div>
        )}

        <div className="text-xs text-gray-500 border-t pt-3">
          <p className="font-medium mb-1">How it works:</p>
          <ul className="list-disc list-inside space-y-1">
            <li>Select a test persona (company profile)</li>
            <li>Click "Auto-Respond" to generate and send a response</li>
            <li>The AI will role-play as the selected company</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default TestModePanel;
