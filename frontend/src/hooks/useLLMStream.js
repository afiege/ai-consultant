import { useState, useRef, useCallback, useEffect } from 'react';

/**
 * Reusable hook for LLM streaming chat interactions.
 *
 * Encapsulates the common pattern of:
 *  - Managing a messages array (user + assistant)
 *  - Creating placeholder assistant messages for streaming
 *  - Accumulating SSE chunks into the placeholder
 *  - Handling start/send/error/abort uniformly
 *
 * @param {Object} options
 * @param {Function} options.startStreamFn  - (sessionUuid, onChunk, onDone, onError, apiKey, signal) => Promise
 * @param {Function} options.sendStreamFn   - (sessionUuid, onChunk, onDone, onError, apiKey, signal) => Promise
 * @param {Function} options.saveMessageFn  - (sessionUuid, content) => Promise
 * @param {Function} options.getMessagesFn  - (sessionUuid) => Promise  (to load history)
 * @returns hook API
 */
export function useLLMStream({
  startStreamFn,
  sendStreamFn,
  saveMessageFn,
  getMessagesFn,
} = {}) {
  const [messages, setMessages] = useState([]);
  const [sending, setSending] = useState(false);
  const [started, setStarted] = useState(false);
  const [error, setError] = useState(null);
  const controllerRef = useRef(null);

  // Abort any in-flight stream on unmount
  useEffect(() => {
    return () => {
      if (controllerRef.current) {
        controllerRef.current.abort();
      }
    };
  }, []);

  const getSignal = useCallback(() => {
    if (controllerRef.current) {
      controllerRef.current.abort();
    }
    controllerRef.current = new AbortController();
    return controllerRef.current.signal;
  }, []);

  const abort = useCallback(() => {
    if (controllerRef.current) {
      controllerRef.current.abort();
      controllerRef.current = null;
    }
    setSending(false);
  }, []);

  /** Load existing message history from the server. */
  const loadMessages = useCallback(async (sessionUuid) => {
    if (!getMessagesFn) return;
    try {
      const res = await getMessagesFn(sessionUuid);
      const msgs = res.data || [];
      setMessages(msgs);
      if (msgs.length > 0) setStarted(true);
    } catch {
      // ignore — history may not exist yet
    }
  }, [getMessagesFn]);

  /**
   * Internal helper — streams into a placeholder assistant message.
   * @param {string} sessionUuid
   * @param {Function} streamFn - the API streaming function to call
   * @param {Object}  [extra]  - extra args to spread to the stream function
   */
  const _streamResponse = useCallback(async (sessionUuid, streamFn, placeholderId) => {
    const signal = getSignal();

    await streamFn(
      sessionUuid,
      // onChunk
      (chunk) => {
        setMessages(prev => {
          const updated = [...prev];
          const idx = updated.findIndex(m => m.id === placeholderId);
          if (idx >= 0) {
            updated[idx] = {
              ...updated[idx],
              content: updated[idx].content + chunk,
            };
          }
          return updated;
        });
      },
      // onDone
      () => setSending(false),
      // onError
      (errorMsg) => {
        setError(errorMsg || 'Stream error');
        setSending(false);
        // Remove empty placeholder on error
        setMessages(prev => prev.filter(m => m.id !== placeholderId || m.content));
      },
      undefined, // apiKey (handled by API layer)
      signal,
    );
  }, [getSignal]);

  /** Start a new consultation — creates the first assistant placeholder and streams. */
  const startStream = useCallback(async (sessionUuid) => {
    if (!startStreamFn) return;
    setError(null);
    setSending(true);
    setStarted(true);

    const placeholderId = Date.now();
    setMessages([{
      id: placeholderId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
    }]);

    try {
      await _streamResponse(sessionUuid, startStreamFn, placeholderId);
    } catch (err) {
      setError(err?.message || 'Failed to start stream');
      setSending(false);
    }
  }, [startStreamFn, _streamResponse]);

  /** Send a user message and stream the AI reply. */
  const sendMessage = useCallback(async (sessionUuid, content) => {
    if (!content?.trim() || sending) return;

    const userMessage = content.trim();
    setSending(true);
    setError(null);

    // Append user message to UI
    const userMsgId = Date.now();
    setMessages(prev => [...prev, {
      id: userMsgId,
      role: 'user',
      content: userMessage,
      created_at: new Date().toISOString(),
    }]);

    try {
      // Persist on server
      if (saveMessageFn) {
        await saveMessageFn(sessionUuid, userMessage);
      }

      // Create assistant placeholder
      const aiMsgId = Date.now() + 1;
      setMessages(prev => [...prev, {
        id: aiMsgId,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
      }]);

      const fn = sendStreamFn || startStreamFn;
      await _streamResponse(sessionUuid, fn, aiMsgId);
    } catch (err) {
      setError(err?.message || 'Failed to send message');
      setSending(false);
    }
  }, [sending, saveMessageFn, sendStreamFn, startStreamFn, _streamResponse]);

  /** Request an AI response without sending a new user message (e.g. continue). */
  const requestResponse = useCallback(async (sessionUuid, onComplete) => {
    if (sending) return;
    setSending(true);
    setError(null);

    const aiMsgId = Date.now() + 1;
    setMessages(prev => [...prev, {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
    }]);

    const fn = sendStreamFn || startStreamFn;
    const signal = getSignal();

    try {
      await fn(
        sessionUuid,
        // onChunk
        (chunk) => {
          setMessages(prev => {
            const updated = [...prev];
            const idx = updated.findIndex(m => m.id === aiMsgId);
            if (idx >= 0) {
              updated[idx] = { ...updated[idx], content: updated[idx].content + chunk };
            }
            return updated;
          });
        },
        // onDone
        () => {
          setSending(false);
          if (onComplete) onComplete();
        },
        // onError
        (errorMsg) => {
          setError(errorMsg || 'Stream error');
          setSending(false);
          setMessages(prev => prev.filter(m => m.id !== aiMsgId || m.content));
        },
        undefined,
        signal,
      );
    } catch (err) {
      setError(err?.message || 'Failed to get AI response');
      setSending(false);
    }
  }, [sending, sendStreamFn, startStreamFn, getSignal]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setStarted(false);
    setError(null);
  }, []);

  return {
    messages,
    setMessages,
    sending,
    started,
    setStarted,
    error,
    setError,
    startStream,
    sendMessage,
    requestResponse,
    loadMessages,
    clearMessages,
    abort,
  };
}

export default useLLMStream;
