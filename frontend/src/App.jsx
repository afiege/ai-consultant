import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { SessionProvider } from './context/SessionContext';
import { ErrorBoundary } from './components/common';
import HomePage from './pages/HomePage';
import Step1Page from './pages/Step1Page';
import Step2Page from './pages/Step2Page';
import Step3Page from './pages/Step3Page';
import Step4Page from './pages/Step4Page';
import Step5Page from './pages/Step5Page';
import Step6Page from './pages/Step6Page';

function App() {
  return (
    <ErrorBoundary>
      <SessionProvider>
        <Router>
        <div className="min-h-screen bg-gray-50">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/session/:sessionUuid/step1" element={<Step1Page />} />
            {/* Keep old step1a/step1b routes for backwards compatibility */}
            <Route path="/session/:sessionUuid/step1a" element={<Navigate to="../step1" replace />} />
            <Route path="/session/:sessionUuid/step1b" element={<Navigate to="../step1" replace />} />
            <Route path="/session/:sessionUuid/step2" element={<Step2Page />} />
            <Route path="/session/:sessionUuid/step3" element={<Step3Page />} />
            <Route path="/session/:sessionUuid/step4" element={<Step4Page />} />
            <Route path="/session/:sessionUuid/step5" element={<Step5Page />} />
            <Route path="/session/:sessionUuid/step6" element={<Step6Page />} />
            {/* Keep old export route for backwards compatibility */}
            <Route path="/session/:sessionUuid/export" element={<Step6Page />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
        </Router>
      </SessionProvider>
    </ErrorBoundary>
  );
}

export default App;
