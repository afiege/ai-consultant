import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { sessionAPI } from '../../services/api';

// Step configuration
const STEPS = [
  { id: 1, route: 'step1', key: 'companyProfile', label: '1' },
  { id: 2, route: 'step2', key: 'brainstorming', skippable: true, label: '2' },
  { id: 3, route: 'step3', key: 'prioritization', skippable: true, label: '3' },
  { id: 4, route: 'step4', key: 'consultation', label: '4' },
  { id: 5, route: 'step5', key: 'businessCase', label: '5' },
  { id: 6, route: 'step6', key: 'results', label: '6' },
];

// Icons
const CheckIcon = () => (
  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
  </svg>
);

const SkipIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
  </svg>
);

const ArrowIcon = () => (
  <svg className="w-5 h-5 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
  </svg>
);

const StepProgress = ({
  session: sessionProp = null,
  currentStepOverride = null,
  compact = false
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { sessionUuid } = useParams();
  const location = useLocation();
  const [session, setSession] = useState(sessionProp);

  // Load session data if not provided
  useEffect(() => {
    if (!sessionProp && sessionUuid) {
      sessionAPI.get(sessionUuid)
        .then(response => setSession(response.data))
        .catch(err => console.error('Error loading session for progress:', err));
    }
  }, [sessionUuid, sessionProp]);

  // Update session when prop changes
  useEffect(() => {
    if (sessionProp) {
      setSession(sessionProp);
    }
  }, [sessionProp]);

  // Determine current step from URL or override
  const getCurrentStep = () => {
    if (currentStepOverride) return currentStepOverride;

    const path = location.pathname;
    if (path.includes('/step6') || path.includes('/export')) return 6;
    if (path.includes('/step5')) return 5;
    if (path.includes('/step4')) return 4;
    if (path.includes('/step3')) return 3;
    if (path.includes('/step2')) return 2;
    if (path.includes('/step1')) return 1;
    return 1;
  };

  const currentStep = getCurrentStep();

  // Determine step states
  const getStepState = (stepId) => {
    // Skip check for steps 2 and 3 (brainstorming and prioritization)
    const brainstormingSkipped = session?.six_three_five_skipped;

    if (stepId === currentStep) {
      return 'current';
    }

    if (stepId < currentStep) {
      // Step 2 (brainstorming) was skipped
      if (stepId === 2 && brainstormingSkipped) {
        return 'skipped';
      }
      // Step 3 (prioritization) was skipped if brainstorming was skipped
      if (stepId === 3 && brainstormingSkipped) {
        return 'skipped';
      }
      return 'completed';
    }

    // Step 4 (Consultation) is always accessible from steps 1-3
    // This allows users to skip brainstorming and prioritization
    if (stepId === 4 && currentStep >= 1 && currentStep < 4) {
      return 'next';
    }

    // Next step (one ahead of current) is navigable
    if (stepId === currentStep + 1) {
      return 'next';
    }

    return 'upcoming';
  };

  // Navigate to step (only allow navigation to completed or current steps)
  const handleStepClick = (step) => {
    const state = getStepState(step.id);
    if (state === 'upcoming') return;

    navigate(`/session/${sessionUuid}/${step.route}`);
  };

  // Get step styles based on state
  const getStepStyles = (state) => {
    switch (state) {
      case 'current':
        return {
          circle: 'bg-blue-600 text-white border-blue-600',
          text: 'text-blue-600 font-semibold',
          clickable: true,
        };
      case 'completed':
        return {
          circle: 'bg-green-500 text-white border-green-500',
          text: 'text-green-600',
          clickable: true,
        };
      case 'skipped':
        return {
          circle: 'bg-gray-300 text-gray-500 border-gray-300',
          text: 'text-gray-400',
          clickable: true,
        };
      case 'next':
        return {
          circle: 'bg-white text-blue-600 border-blue-400 border-dashed',
          text: 'text-blue-500',
          clickable: true,
        };
      default: // upcoming
        return {
          circle: 'bg-white text-gray-400 border-gray-300',
          text: 'text-gray-400',
          clickable: false,
        };
    }
  };

  if (compact) {
    // Compact version: just show dots
    return (
      <div className="flex items-center justify-center gap-2 py-2">
        {STEPS.map((step) => {
          const state = getStepState(step.id);
          const styles = getStepStyles(state);

          return (
            <div
              key={step.id}
              className={`w-2.5 h-2.5 rounded-full transition-all ${
                state === 'current' ? 'bg-blue-600 w-4' :
                state === 'completed' ? 'bg-green-500' :
                state === 'skipped' ? 'bg-gray-300' :
                state === 'next' ? 'bg-blue-200 ring-1 ring-blue-400' :
                'bg-gray-200'
              }`}
              title={t(`stepProgress.steps.${step.key}`)}
            />
          );
        })}
      </div>
    );
  }

  return (
    <div className="bg-white border-b border-gray-100 sticky top-0 z-20 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
        <nav aria-label="Progress">
          <ol className="flex items-center justify-between">
            {STEPS.map((step, index) => {
              const state = getStepState(step.id);
              const styles = getStepStyles(state);
              const isLast = index === STEPS.length - 1;

              return (
                <li key={step.id} className="flex items-center flex-1 last:flex-none">
                  <button
                    onClick={() => handleStepClick(step)}
                    disabled={!styles.clickable}
                    className={`group flex items-center ${styles.clickable ? 'cursor-pointer' : 'cursor-not-allowed'}`}
                  >
                    {/* Step circle */}
                    <span
                      className={`
                        flex items-center justify-center w-8 h-8 rounded-full border-2
                        transition-all duration-200 text-sm font-medium
                        ${styles.circle}
                        ${styles.clickable && state !== 'current' ? 'group-hover:ring-2 group-hover:ring-offset-2 group-hover:ring-gray-200' : ''}
                      `}
                    >
                      {state === 'completed' && <CheckIcon />}
                      {state === 'skipped' && <SkipIcon />}
                      {(state === 'current' || state === 'upcoming' || state === 'next') && (step.label || step.id)}
                    </span>

                    {/* Step label - hidden on mobile */}
                    <span className={`ml-2 text-sm hidden sm:block ${styles.text}`}>
                      {t(`stepProgress.steps.${step.key}`)}
                      {state === 'skipped' && (
                        <span className="ml-1 text-xs text-gray-400">
                          ({t('stepProgress.skipped')})
                        </span>
                      )}
                    </span>
                  </button>

                  {/* Arrow connector */}
                  {!isLast && (
                    <div className="flex-1 flex items-center justify-center px-2 sm:px-4">
                      <div className={`h-0.5 w-full ${
                        getStepState(step.id + 1) === 'upcoming'
                          ? 'bg-gray-200'
                          : 'bg-green-300'
                      }`} />
                    </div>
                  )}
                </li>
              );
            })}
          </ol>
        </nav>
      </div>
    </div>
  );
};

export default StepProgress;
