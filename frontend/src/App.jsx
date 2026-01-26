import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { SessionProvider } from './context/SessionContext';
import HomePage from './pages/HomePage';
import Step1aPage from './pages/Step1aPage';
import Step1bPage from './pages/Step1bPage';
import Step2Page from './pages/Step2Page';
import Step3Page from './pages/Step3Page';
import Step4Page from './pages/Step4Page';
import Step5Page from './pages/Step5Page';
import Step6Page from './pages/Step6Page';

function App() {
  return (
    <SessionProvider>
      <Router>
        <div className="min-h-screen bg-gray-50">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/session/:sessionUuid/step1a" element={<Step1aPage />} />
            <Route path="/session/:sessionUuid/step1b" element={<Step1bPage />} />
            {/* Keep old step1 route for backwards compatibility, redirect to step1a */}
            <Route path="/session/:sessionUuid/step1" element={<Navigate to="../step1a" replace />} />
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
  );
}

export default App;
