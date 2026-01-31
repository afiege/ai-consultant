/**
 * Unified error handling utilities for the frontend.
 *
 * Provides consistent error parsing, user-friendly messages,
 * and error classification for better UX.
 */

// Error codes that map to specific user-friendly messages
const ERROR_MESSAGES = {
  NOT_FOUND: 'The requested resource could not be found.',
  VALIDATION_ERROR: 'Please check your input and try again.',
  LLM_ERROR: 'The AI service encountered an error. Please try again.',
  LLM_AUTH_ERROR: 'Invalid or missing API key. Please check your settings.',
  LLM_RATE_LIMIT: 'Too many AI requests. Please wait a moment and try again.',
  RATE_LIMIT_EXCEEDED: 'Too many requests. Please wait before trying again.',
  EXPORT_ERROR: 'Failed to generate the export. Please try again.',
  DATABASE_ERROR: 'A database error occurred. Please try again.',
  INTERNAL_ERROR: 'An unexpected error occurred. Please try again.',
  NETWORK_ERROR: 'Network error. Please check your connection.',
  TIMEOUT_ERROR: 'The request timed out. Please try again.',
};

// German translations for error messages
const ERROR_MESSAGES_DE = {
  NOT_FOUND: 'Die angeforderte Ressource wurde nicht gefunden.',
  VALIDATION_ERROR: 'Bitte überprüfen Sie Ihre Eingabe und versuchen Sie es erneut.',
  LLM_ERROR: 'Der KI-Dienst hat einen Fehler festgestellt. Bitte versuchen Sie es erneut.',
  LLM_AUTH_ERROR: 'Ungültiger oder fehlender API-Schlüssel. Bitte überprüfen Sie Ihre Einstellungen.',
  LLM_RATE_LIMIT: 'Zu viele KI-Anfragen. Bitte warten Sie einen Moment und versuchen Sie es erneut.',
  RATE_LIMIT_EXCEEDED: 'Zu viele Anfragen. Bitte warten Sie, bevor Sie es erneut versuchen.',
  EXPORT_ERROR: 'Der Export konnte nicht erstellt werden. Bitte versuchen Sie es erneut.',
  DATABASE_ERROR: 'Ein Datenbankfehler ist aufgetreten. Bitte versuchen Sie es erneut.',
  INTERNAL_ERROR: 'Ein unerwarteter Fehler ist aufgetreten. Bitte versuchen Sie es erneut.',
  NETWORK_ERROR: 'Netzwerkfehler. Bitte überprüfen Sie Ihre Verbindung.',
  TIMEOUT_ERROR: 'Die Anfrage hat zu lange gedauert. Bitte versuchen Sie es erneut.',
};

/**
 * Parse an error response from the API.
 *
 * @param {Error|Object|string} error - The error to parse
 * @returns {Object} Parsed error with code, message, and details
 */
export function parseError(error) {
  // Handle abort errors (user cancelled)
  if (error?.name === 'AbortError') {
    return {
      code: 'ABORTED',
      message: 'Request was cancelled',
      details: {},
      isUserCancelled: true,
    };
  }

  // Handle network errors
  if (error?.message === 'Failed to fetch' || error?.name === 'TypeError') {
    return {
      code: 'NETWORK_ERROR',
      message: ERROR_MESSAGES.NETWORK_ERROR,
      details: {},
      isNetworkError: true,
    };
  }

  // Handle timeout errors
  if (error?.name === 'TimeoutError' || error?.message?.includes('timeout')) {
    return {
      code: 'TIMEOUT_ERROR',
      message: ERROR_MESSAGES.TIMEOUT_ERROR,
      details: {},
      isTimeout: true,
    };
  }

  // Handle API error responses (standardized format)
  if (error?.error && error?.message) {
    return {
      code: error.error,
      message: error.message,
      details: error.details || {},
      isApiError: true,
    };
  }

  // Handle legacy API error responses
  if (error?.detail) {
    return {
      code: 'API_ERROR',
      message: error.detail,
      details: {},
      isApiError: true,
    };
  }

  // Handle string errors
  if (typeof error === 'string') {
    return {
      code: 'UNKNOWN_ERROR',
      message: error,
      details: {},
    };
  }

  // Handle Error instances
  if (error instanceof Error) {
    return {
      code: 'UNKNOWN_ERROR',
      message: error.message,
      details: {},
    };
  }

  // Fallback
  return {
    code: 'UNKNOWN_ERROR',
    message: 'An unexpected error occurred',
    details: {},
  };
}

/**
 * Get a user-friendly error message.
 *
 * @param {Error|Object|string} error - The error to get message for
 * @param {string} language - Language code ('en' or 'de')
 * @returns {string} User-friendly error message
 */
export function getErrorMessage(error, language = 'en') {
  const parsed = parseError(error);
  const messages = language === 'de' ? ERROR_MESSAGES_DE : ERROR_MESSAGES;

  // Return mapped message if available, otherwise the parsed message
  return messages[parsed.code] || parsed.message || messages.INTERNAL_ERROR;
}

/**
 * Check if an error is retryable (transient).
 *
 * @param {Error|Object|string} error - The error to check
 * @returns {boolean} True if the error is likely transient
 */
export function isRetryableError(error) {
  const parsed = parseError(error);
  const retryableCodes = [
    'LLM_ERROR',
    'LLM_RATE_LIMIT',
    'RATE_LIMIT_EXCEEDED',
    'DATABASE_ERROR',
    'NETWORK_ERROR',
    'TIMEOUT_ERROR',
    'INTERNAL_ERROR',
  ];
  return retryableCodes.includes(parsed.code);
}

/**
 * Check if an error requires user action (not automatically retryable).
 *
 * @param {Error|Object|string} error - The error to check
 * @returns {boolean} True if the error requires user action
 */
export function requiresUserAction(error) {
  const parsed = parseError(error);
  const userActionCodes = [
    'NOT_FOUND',
    'VALIDATION_ERROR',
    'LLM_AUTH_ERROR',
  ];
  return userActionCodes.includes(parsed.code);
}

/**
 * Log an error with appropriate context.
 *
 * @param {Error|Object|string} error - The error to log
 * @param {string} context - Context where the error occurred
 */
export function logError(error, context = '') {
  const parsed = parseError(error);
  const prefix = context ? `[${context}]` : '';

  if (parsed.isUserCancelled) {
    // Don't log cancelled requests
    return;
  }

  console.error(
    `${prefix} Error ${parsed.code}: ${parsed.message}`,
    parsed.details
  );
}

/**
 * Create an error handler function with default behavior.
 *
 * @param {Object} options - Handler options
 * @param {Function} options.onError - Callback for error handling
 * @param {string} options.context - Context for logging
 * @param {string} options.language - Language for messages
 * @returns {Function} Error handler function
 */
export function createErrorHandler({ onError, context = '', language = 'en' }) {
  return (error) => {
    const parsed = parseError(error);

    // Skip cancelled requests
    if (parsed.isUserCancelled) {
      return;
    }

    logError(error, context);

    if (onError) {
      onError({
        ...parsed,
        userMessage: getErrorMessage(error, language),
      });
    }
  };
}

export default {
  parseError,
  getErrorMessage,
  isRetryableError,
  requiresUserAction,
  logError,
  createErrorHandler,
};
