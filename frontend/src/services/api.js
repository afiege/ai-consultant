import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// API Key management (stored in sessionStorage - cleared when tab closes)
const API_KEY_STORAGE_KEY = 'ai_consultant_api_key';

export const apiKeyManager = {
  get: () => sessionStorage.getItem(API_KEY_STORAGE_KEY),
  set: (apiKey) => sessionStorage.setItem(API_KEY_STORAGE_KEY, apiKey),
  clear: () => sessionStorage.removeItem(API_KEY_STORAGE_KEY),
  isSet: () => !!sessionStorage.getItem(API_KEY_STORAGE_KEY),
};

// Session endpoints
export const sessionAPI = {
  create: (data) => api.post('/api/sessions/', data),
  get: (sessionUuid) => api.get(`/api/sessions/${sessionUuid}`),
  update: (sessionUuid, data) => api.put(`/api/sessions/${sessionUuid}`, data),
  delete: (sessionUuid) => api.delete(`/api/sessions/${sessionUuid}`),
  list: (skip = 0, limit = 100) => api.get('/api/sessions/', { params: { skip, limit } }),
};

// Company info endpoints
export const companyInfoAPI = {
  submitText: (sessionUuid, data) =>
    api.post(`/api/sessions/${sessionUuid}/company-info/text`, data),
  uploadFile: (sessionUuid, formData) =>
    api.post(`/api/sessions/${sessionUuid}/company-info/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  crawlWeb: (sessionUuid, data) =>
    api.post(`/api/sessions/${sessionUuid}/company-info/crawl`, data),
  getAll: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/company-info`),
  delete: (sessionUuid, infoId) =>
    api.delete(`/api/sessions/${sessionUuid}/company-info/${infoId}`),
};

// Company profile endpoints (structured extraction)
export const companyProfileAPI = {
  extract: (sessionUuid, apiKey) =>
    api.post(`/api/sessions/${sessionUuid}/company-profile/extract`, {
      api_key: apiKey || apiKeyManager.get()
    }),
  get: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/company-profile`),
  getContext: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/company-profile/context`),
  delete: (sessionUuid) =>
    api.delete(`/api/sessions/${sessionUuid}/company-profile`),
  save: (sessionUuid, profile) =>
    api.put(`/api/sessions/${sessionUuid}/company-profile`, profile),
};

// Maturity assessment endpoints (acatech Industry 4.0 Maturity Index)
export const maturityAPI = {
  get: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/maturity`),
  save: (sessionUuid, data) =>
    api.post(`/api/sessions/${sessionUuid}/maturity`, data),
  getLevels: () =>
    api.get('/api/sessions/maturity/levels'),
};

// 6-3-5 method endpoints
export const sixThreeFiveAPI = {
  start: (sessionUuid, apiKey) =>
    api.post(`/api/sessions/${sessionUuid}/six-three-five/start`, { api_key: apiKey || apiKeyManager.get() }),
  skip: (sessionUuid) =>
    api.post(`/api/sessions/${sessionUuid}/six-three-five/skip`),
  join: (sessionUuid, data) =>
    api.post(`/api/sessions/${sessionUuid}/six-three-five/join`, data),
  getStatus: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/six-three-five/status`),
  getMySheet: (sessionUuid, participantUuid) =>
    api.get(`/api/sessions/${sessionUuid}/six-three-five/my-sheet/${participantUuid}`),
  submitIdeas: (sessionUuid, participantUuid, data) =>
    api.post(`/api/sessions/${sessionUuid}/six-three-five/ideas?participant_uuid=${participantUuid}`, data),
  advanceRound: (sessionUuid, apiKey) =>
    api.post(`/api/sessions/${sessionUuid}/six-three-five/advance-round`, { api_key: apiKey || apiKeyManager.get() }),
  getIdeas: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/six-three-five/ideas`),
  submitManualIdeas: (sessionUuid, ideas) =>
    api.post(`/api/sessions/${sessionUuid}/six-three-five/manual-ideas`, ideas),
};

// Prioritization endpoints (two-phase: cluster then idea)
export const prioritizationAPI = {
  // Legacy endpoints (kept for backwards compatibility)
  submitVote: (sessionUuid, data) =>
    api.post(`/api/sessions/${sessionUuid}/prioritization/vote`, data),
  getStatus: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/prioritization/status`),
  getResults: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/prioritization/results`),

  // Phase 1: Cluster prioritization
  generateClusters: (sessionUuid, apiKey) =>
    api.post(`/api/sessions/${sessionUuid}/prioritization/cluster`, { api_key: apiKey || apiKeyManager.get() }),
  getClusters: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/prioritization/clusters`),
  submitClusterVote: (sessionUuid, data) =>
    api.post(`/api/sessions/${sessionUuid}/prioritization/cluster-vote`, data),
  getClusterResults: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/prioritization/cluster-results`),
  getClusterStatus: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/prioritization/cluster-status`),
  selectCluster: (sessionUuid, clusterId) =>
    api.post(`/api/sessions/${sessionUuid}/prioritization/select-cluster`, { cluster_id: clusterId }),

  // Phase 2: Idea prioritization (within selected cluster)
  getClusterIdeas: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/prioritization/cluster-ideas`),
  submitIdeaVote: (sessionUuid, data) =>
    api.post(`/api/sessions/${sessionUuid}/prioritization/idea-vote`, data),
  getIdeaResults: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/prioritization/idea-results`),
  getIdeaStatus: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/prioritization/idea-status`),
};

// Consultation endpoints
export const consultationAPI = {
  start: (sessionUuid, apiKey) =>
    api.post(`/api/sessions/${sessionUuid}/consultation/start`, { api_key: apiKey || apiKeyManager.get() }),
  sendMessage: (sessionUuid, content, apiKey) =>
    api.post(`/api/sessions/${sessionUuid}/consultation/message`, { content, api_key: apiKey || apiKeyManager.get() }),
  // Save user message without AI response (user answering questions)
  saveMessage: (sessionUuid, content) =>
    api.post(`/api/sessions/${sessionUuid}/consultation/message/save`, { content }),
  getMessages: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/consultation/messages`),
  getFindings: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/consultation/findings`),
  summarize: (sessionUuid, apiKey) =>
    api.post(`/api/sessions/${sessionUuid}/consultation/summarize`, { api_key: apiKey || apiKeyManager.get() }),
  extractIncremental: (sessionUuid, apiKey) =>
    api.post(`/api/sessions/${sessionUuid}/consultation/extract-incremental`, { api_key: apiKey || apiKeyManager.get() }),
  reset: (sessionUuid, fromStep = 4) =>
    api.delete(`/api/sessions/${sessionUuid}/consultation/reset?from_step=${fromStep}`),

  // Collaborative mode endpoints
  getCollaborativeStatus: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/consultation/collaborative-status`),
  setCollaborativeMode: (sessionUuid, enabled) =>
    api.post(`/api/sessions/${sessionUuid}/consultation/collaborative-mode?enabled=${enabled}`),
  saveCollaborativeMessage: (sessionUuid, content, participantUuid) =>
    api.post(`/api/sessions/${sessionUuid}/consultation/message/save-collaborative`, {
      content,
      participant_uuid: participantUuid
    }),
  getCollaborativeMessages: (sessionUuid, sinceId = null) =>
    api.get(`/api/sessions/${sessionUuid}/consultation/messages-collaborative`, {
      params: sinceId ? { since_id: sinceId } : {}
    }),

  // Streaming endpoints using fetch (SSE)
  startStream: async (sessionUuid, onChunk, onDone, onError, apiKey) => {
    const key = apiKey || apiKeyManager.get();
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/sessions/${sessionUuid}/consultation/start/stream`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ api_key: key }),
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value, { stream: true });
        const lines = text.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              onDone?.();
            } else if (data.startsWith('{')) {
              // JSON status message
              try {
                const parsed = JSON.parse(data);
                if (parsed.status === 'already_started') {
                  onError?.('Consultation already started');
                }
              } catch (e) {
                // Not JSON, treat as content
                onChunk?.(data);
              }
            } else {
              onChunk?.(data);
            }
          }
        }
      }
    } catch (error) {
      onError?.(error.message);
    }
  },

  sendMessageStream: async (sessionUuid, content, onChunk, onDone, onError, apiKey) => {
    const key = apiKey || apiKeyManager.get();
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/sessions/${sessionUuid}/consultation/message/stream`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content, api_key: key }),
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value, { stream: true });
        const lines = text.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              onDone?.();
            } else {
              onChunk?.(data);
            }
          }
        }
      }
    } catch (error) {
      onError?.(error.message);
    }
  },

  // Request AI response based on current conversation (no new user message)
  requestAiResponseStream: async (sessionUuid, onChunk, onDone, onError, apiKey) => {
    const key = apiKey || apiKeyManager.get();
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/sessions/${sessionUuid}/consultation/request-response/stream`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ api_key: key }),
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value, { stream: true });
        const lines = text.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              onDone?.();
            } else if (data.startsWith('{')) {
              // JSON status/error message
              try {
                const parsed = JSON.parse(data);
                if (parsed.error) {
                  onError?.(parsed.error);
                }
              } catch (e) {
                onChunk?.(data);
              }
            } else {
              onChunk?.(data);
            }
          }
        }
      }
    } catch (error) {
      onError?.(error.message);
    }
  },
};

// Business Case endpoints (Step 5)
export const businessCaseAPI = {
  start: (sessionUuid, apiKey) =>
    api.post(`/api/sessions/${sessionUuid}/business-case/start`, { api_key: apiKey || apiKeyManager.get() }),
  sendMessage: (sessionUuid, content, apiKey) =>
    api.post(`/api/sessions/${sessionUuid}/business-case/message`, { content, api_key: apiKey || apiKeyManager.get() }),
  saveMessage: (sessionUuid, content) =>
    api.post(`/api/sessions/${sessionUuid}/business-case/message/save`, { content }),
  getMessages: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/business-case/messages`),
  getFindings: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/business-case/findings`),
  extract: (sessionUuid, apiKey) =>
    api.post(`/api/sessions/${sessionUuid}/business-case/extract`, { api_key: apiKey || apiKeyManager.get() }),

  // Streaming endpoints using fetch (SSE)
  startStream: async (sessionUuid, onChunk, onDone, onError, apiKey) => {
    const key = apiKey || apiKeyManager.get();
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/sessions/${sessionUuid}/business-case/start/stream`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ api_key: key }),
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value, { stream: true });
        const lines = text.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              onDone?.();
            } else if (data.startsWith('{')) {
              try {
                const parsed = JSON.parse(data);
                if (parsed.status === 'already_started') {
                  onError?.('Business case already started');
                }
              } catch (e) {
                onChunk?.(data);
              }
            } else {
              onChunk?.(data);
            }
          }
        }
      }
    } catch (error) {
      onError?.(error.message);
    }
  },

  sendMessageStream: async (sessionUuid, content, onChunk, onDone, onError, apiKey) => {
    const key = apiKey || apiKeyManager.get();
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/sessions/${sessionUuid}/business-case/message/stream`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content, api_key: key }),
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value, { stream: true });
        const lines = text.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              onDone?.();
            } else {
              onChunk?.(data);
            }
          }
        }
      }
    } catch (error) {
      onError?.(error.message);
    }
  },

  requestAiResponseStream: async (sessionUuid, onChunk, onDone, onError, apiKey) => {
    const key = apiKey || apiKeyManager.get();
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/sessions/${sessionUuid}/business-case/request-response/stream`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ api_key: key }),
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value, { stream: true });
        const lines = text.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              onDone?.();
            } else if (data.startsWith('{')) {
              try {
                const parsed = JSON.parse(data);
                if (parsed.error) {
                  onError?.(parsed.error);
                }
              } catch (e) {
                onChunk?.(data);
              }
            } else {
              onChunk?.(data);
            }
          }
        }
      }
    } catch (error) {
      onError?.(error.message);
    }
  },
};

// Cost Estimation endpoints (Step 5b)
export const costEstimationAPI = {
  start: (sessionUuid, apiKey) =>
    api.post(`/api/sessions/${sessionUuid}/cost-estimation/start`, { api_key: apiKey || apiKeyManager.get() }),
  sendMessage: (sessionUuid, content, apiKey) =>
    api.post(`/api/sessions/${sessionUuid}/cost-estimation/message`, { content, api_key: apiKey || apiKeyManager.get() }),
  saveMessage: (sessionUuid, content) =>
    api.post(`/api/sessions/${sessionUuid}/cost-estimation/message/save`, { content }),
  getMessages: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/cost-estimation/messages`),
  getFindings: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/cost-estimation/findings`),
  extract: (sessionUuid, apiKey) =>
    api.post(`/api/sessions/${sessionUuid}/cost-estimation/extract`, { api_key: apiKey || apiKeyManager.get() }),

  // Streaming endpoints using fetch (SSE)
  startStream: async (sessionUuid, onChunk, onDone, onError, apiKey) => {
    const key = apiKey || apiKeyManager.get();
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/sessions/${sessionUuid}/cost-estimation/start/stream`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ api_key: key }),
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value, { stream: true });
        const lines = text.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              onDone?.();
            } else if (data.startsWith('{')) {
              try {
                const parsed = JSON.parse(data);
                if (parsed.status === 'already_started') {
                  onError?.('Cost estimation already started');
                }
              } catch (e) {
                onChunk?.(data);
              }
            } else {
              onChunk?.(data);
            }
          }
        }
      }
    } catch (error) {
      onError?.(error.message);
    }
  },

  sendMessageStream: async (sessionUuid, content, onChunk, onDone, onError, apiKey) => {
    const key = apiKey || apiKeyManager.get();
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/sessions/${sessionUuid}/cost-estimation/message/stream`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content, api_key: key }),
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value, { stream: true });
        const lines = text.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              onDone?.();
            } else {
              onChunk?.(data);
            }
          }
        }
      }
    } catch (error) {
      onError?.(error.message);
    }
  },

  requestAiResponseStream: async (sessionUuid, onChunk, onDone, onError, apiKey) => {
    const key = apiKey || apiKeyManager.get();
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/sessions/${sessionUuid}/cost-estimation/request-response/stream`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ api_key: key }),
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value, { stream: true });
        const lines = text.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              onDone?.();
            } else if (data.startsWith('{')) {
              try {
                const parsed = JSON.parse(data);
                if (parsed.error) {
                  onError?.(parsed.error);
                }
              } catch (e) {
                onChunk?.(data);
              }
            } else {
              onChunk?.(data);
            }
          }
        }
      }
    } catch (error) {
      onError?.(error.message);
    }
  },
};

// Export endpoints
export const exportAPI = {
  generatePDF: (sessionUuid) =>
    api.post(`/api/sessions/${sessionUuid}/export/pdf`, {}, {
      responseType: 'blob',
    }),
  downloadPDF: (sessionUuid, exportId) =>
    api.get(`/api/sessions/${sessionUuid}/export/pdf/${exportId}`, {
      responseType: 'blob',
    }),
  getData: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/export/data`),

  // Transition briefing endpoints
  getTransitionBriefing: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/transition-briefing`),
  generateTransitionBriefing: (sessionUuid, options = {}) =>
    api.post(`/api/sessions/${sessionUuid}/transition-briefing/generate`, {
      model: options.model,  // Backend uses session's LLM settings if not specified
      api_key: options.apiKey || apiKeyManager.get(),
      api_base: options.apiBase,
      language: options.language,  // Backend uses session language if not specified
    }),

  // SWOT analysis endpoints
  getSwotAnalysis: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/swot-analysis`),
  generateSwotAnalysis: (sessionUuid, options = {}) =>
    api.post(`/api/sessions/${sessionUuid}/swot-analysis/generate`, {
      model: options.model,  // Backend uses session's LLM settings if not specified
      api_key: options.apiKey || apiKeyManager.get(),
      api_base: options.apiBase,
      language: options.language,  // Backend uses session language if not specified
    }),

  // Auto-update analysis (regenerate SWOT and Briefing)
  autoUpdateAnalysis: (sessionUuid, options = {}) =>
    api.post(`/api/sessions/${sessionUuid}/analysis/auto-update`, {
      api_key: options.apiKey || apiKeyManager.get(),
      api_base: options.apiBase,
      language: options.language,
    }),
};

// Findings API - aggregate all findings for Results page
export const findingsAPI = {
  getAll: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/all-findings`),
};

// Session backup/restore endpoints
export const sessionBackupAPI = {
  exportBackup: async (sessionUuid) => {
    const response = await api.get(`/api/sessions/${sessionUuid}/backup`);
    // Trigger download
    const blob = new Blob([JSON.stringify(response.data, null, 2)], {
      type: 'application/json',
    });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `session-backup-${sessionUuid.slice(0, 8)}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    return response.data;
  },
  restoreBackup: async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/api/sessions/restore', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};

// Expert settings endpoints
export const expertSettingsAPI = {
  get: (sessionUuid) =>
    api.get(`/api/sessions/${sessionUuid}/expert-settings`),
  update: (sessionUuid, settings) =>
    api.put(`/api/sessions/${sessionUuid}/expert-settings`, settings),
  getDefaults: () =>
    api.get('/api/sessions/expert-settings/defaults'),
  getMetadata: () =>
    api.get('/api/sessions/expert-settings/metadata'),
  getLLMProviders: () =>
    api.get('/api/sessions/expert-settings/llm-providers'),
  fetchModels: (apiBase, apiKey) =>
    api.post('/api/sessions/expert-settings/fetch-models', { api_base: apiBase, api_key: apiKey }),
  testLLM: (config) =>
    api.post('/api/sessions/expert-settings/test-llm', config),
  resetPrompt: (sessionUuid, promptKey) =>
    api.post(`/api/sessions/${sessionUuid}/expert-settings/reset-prompt/${promptKey}`),
  resetAll: (sessionUuid) =>
    api.post(`/api/sessions/${sessionUuid}/expert-settings/reset-all`),
};

export default api;
