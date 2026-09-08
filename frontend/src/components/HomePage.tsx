/**
 * Phase 13: Home page with research form.
 */

'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useDispatch } from 'react-redux';
import { useResearchAPI } from '@/hooks/useResearchAPI';
import { setError } from '@/store/researchSlice';

export const HomePage: React.FC = () => {
  const router = useRouter();
  const dispatch = useDispatch();
  const { startResearch } = useResearchAPI();

  const [question, setQuestion] = useState('');
  const [maxSteps, setMaxSteps] = useState(8);
  const [isLoading, setIsLoading] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);

    if (!question.trim()) {
      setLocalError('Please enter a research question');
      return;
    }

    if (question.length > 500) {
      setLocalError('Question must be 500 characters or less');
      return;
    }

    try {
      setIsLoading(true);
      const researchId = await startResearch(question, maxSteps);
      router.push(`/research/${researchId}`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to start research';
      setLocalError(errorMessage);
      dispatch(setError(errorMessage));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="max-w-2xl w-full">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-gray-900 mb-4">
            ResearchPilot AI
          </h1>
          <p className="text-xl text-gray-600">
            AI-Powered Evidence-Based Research
          </p>
          <p className="text-sm text-gray-500 mt-2">
            Ask a question, and we&apos;ll research it using verified sources
          </p>
        </div>

        {/* Research Form Card */}
        <div className="bg-white rounded-lg shadow-xl p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Question Input */}
            <div>
              <label
                htmlFor="question"
                className="block text-sm font-semibold text-gray-700 mb-3"
              >
                What would you like to research?
              </label>
              <textarea
                id="question"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Example: What are the latest approaches for reducing LLM hallucinations?"
                className="w-full px-4 py-3 border-2 border-gray-300 rounded-lg focus:border-indigo-500 focus:outline-none resize-none"
                rows={4}
                maxLength={500}
                disabled={isLoading}
              />
              <div className="mt-2 flex justify-between items-center">
                <span className="text-xs text-gray-500">
                  {question.length}/500 characters
                </span>
              </div>
            </div>

            {/* Max Steps Control */}
            <div>
              <label
                htmlFor="maxSteps"
                className="block text-sm font-semibold text-gray-700 mb-3"
              >
                Max Research Steps: {maxSteps}
              </label>
              <input
                id="maxSteps"
                type="range"
                min="1"
                max="20"
                value={maxSteps}
                onChange={(e) => setMaxSteps(parseInt(e.target.value))}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                disabled={isLoading}
              />
              <p className="text-xs text-gray-500 mt-2">
                More steps allow deeper research but take longer
              </p>
            </div>

            {/* Error Display */}
            {localError && (
              <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded">
                <p className="text-sm text-red-700">{localError}</p>
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 px-6 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-400 text-white font-semibold rounded-lg transition-colors duration-200"
            >
              {isLoading ? 'Starting Research...' : 'Start Research'}
            </button>
          </form>

          {/* Features */}
          <div className="mt-12 pt-8 border-t border-gray-200">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">
              How it works
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="text-center">
                <div className="text-2xl mb-2">🔍</div>
                <p className="text-sm text-gray-600">
                  <strong>Search</strong> the web for sources
                </p>
              </div>
              <div className="text-center">
                <div className="text-2xl mb-2">📄</div>
                <p className="text-sm text-gray-600">
                  <strong>Fetch</strong> and analyze pages
                </p>
              </div>
              <div className="text-center">
                <div className="text-2xl mb-2">✓</div>
                <p className="text-sm text-gray-600">
                  <strong>Verify</strong> with citations
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center mt-8">
          <p className="text-xs text-gray-500">
            © 2026 ResearchPilot AI - Evidence-Based Research Assistant
          </p>
        </div>
      </div>
    </div>
  );
};

export default HomePage;
