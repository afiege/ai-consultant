import { useRef, useEffect, useCallback } from 'react';

/**
 * Custom hook for managing SSE stream connections with automatic cleanup.
 * Creates an AbortController that cancels streams when component unmounts.
 *
 * Usage:
 *   const { getSignal, abort } = useStreamController();
 *
 *   // In your streaming call:
 *   await consultationAPI.startStream(sessionUuid, onChunk, onDone, onError, apiKey, getSignal());
 *
 *   // To manually abort:
 *   abort();
 */
export const useStreamController = () => {
  const controllerRef = useRef(null);

  // Create a new AbortController and return its signal
  const getSignal = useCallback(() => {
    // Abort any existing controller
    if (controllerRef.current) {
      controllerRef.current.abort();
    }
    // Create new controller
    controllerRef.current = new AbortController();
    return controllerRef.current.signal;
  }, []);

  // Manually abort the current stream
  const abort = useCallback(() => {
    if (controllerRef.current) {
      controllerRef.current.abort();
      controllerRef.current = null;
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (controllerRef.current) {
        controllerRef.current.abort();
      }
    };
  }, []);

  return { getSignal, abort };
};

export default useStreamController;
