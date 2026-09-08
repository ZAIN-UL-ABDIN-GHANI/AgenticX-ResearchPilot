/**
 * Phase 13: Research workspace component showing live research progress.
 */

'use client';

import React, { useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { RootState } from '@/store';
import { useResearchAPI } from '@/hooks/useResearchAPI';

export interface ResearchWorkspaceProps {
  researchId: string;
}

export const ResearchWorkspace: React.FC<ResearchWorkspaceProps> = ({
  researchId,
}) => {
  const dispatch = useDispatch();
  const research = useSelector((state: RootState) => state.research);
  const { pollResearch } = useResearchAPI();

  useEffect(() => {
    // Start polling when component mounts
    pollResearch(researchId).catch(console.error);
  }, [researchId, pollResearch]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'loading':
        return '⏳';
      case 'completed':
        return '✓';
      case 'failed':
        return '✗';
      case 'step_limit_reached':
        return '⚠';
      default:
        return '○';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-green-600';
      case 'failed':
        return 'text-red-600';
      case 'step_limit_reached':
        return 'text-yellow-600';
      default:
        return 'text-blue-600';
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-2">
          {research.question}
        </h1>
        <div className={`text-lg font-semibold ${getStatusColor(research.status)}`}>
          {getStatusIcon(research.status)} {research.status.replace('_', ' ').toUpperCase()}
        </div>
      </div>

      {/* Progress Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Steps Used</div>
          <div className="text-3xl font-bold text-indigo-600">
            {research.steps_used}/{research.max_steps}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Sources Found</div>
          <div className="text-3xl font-bold text-blue-600">
            {research.sources.length}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Tools Used</div>
          <div className="text-3xl font-bold text-purple-600">
            {research.tool_calls.length}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Claims Found</div>
          <div className="text-3xl font-bold text-green-600">
            {research.claims.length}
          </div>
        </div>
      </div>

      {/* Timeline of Tool Calls */}
      {research.tool_calls.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Research Timeline
          </h2>
          <div className="space-y-3">
            {research.tool_calls.map((tool, idx) => (
              <div
                key={idx}
                className="flex items-center space-x-4 p-3 bg-gray-50 rounded"
              >
                <div className="flex-shrink-0 w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center">
                  <span className="text-sm font-semibold text-indigo-600">
                    {tool.step_number || idx + 1}
                  </span>
                </div>
                <div className="flex-grow">
                  <div className="font-semibold text-gray-900">
                    {tool.tool_name.replace('_', ' ').toUpperCase()}
                  </div>
                  {tool.input && (
                    <div className="text-xs text-gray-500">
                      Input: {JSON.stringify(tool.input).substring(0, 50)}...
                    </div>
                  )}
                </div>
                <div className="flex-shrink-0">
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-semibold ${
                      tool.status === 'success'
                        ? 'bg-green-100 text-green-800'
                        : 'bg-red-100 text-red-800'
                    }`}
                  >
                    {tool.status.toUpperCase()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sources Section */}
      {research.sources.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Sources Collected ({research.sources.length})
          </h2>
          <div className="space-y-3">
            {research.sources.map((source) => (
              <div key={source.source_id} className="border border-gray-200 rounded p-4">
                <div className="flex justify-between items-start">
                  <div className="flex-grow">
                    <h3 className="font-semibold text-gray-900">
                      {source.title || 'Untitled'}
                    </h3>
                    <p className="text-sm text-gray-600 truncate">{source.url}</p>
                    <div className="text-xs text-gray-500 mt-1">
                      Domain: {source.domain} • Words: {source.word_count || '?'}
                    </div>
                  </div>
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-semibold ${
                      source.fetch_status === 'success'
                        ? 'bg-green-100 text-green-800'
                        : source.fetch_status === 'pending'
                        ? 'bg-yellow-100 text-yellow-800'
                        : 'bg-red-100 text-red-800'
                    }`}
                  >
                    {source.fetch_status.toUpperCase()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Loading State */}
      {research.status === 'loading' && (
        <div className="bg-blue-50 border-l-4 border-blue-500 p-4 rounded">
          <p className="text-sm text-blue-700">
            Research in progress... This may take a few minutes.
          </p>
        </div>
      )}

      {/* Error State */}
      {research.error && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded">
          <p className="text-sm text-red-700">{research.error}</p>
        </div>
      )}
    </div>
  );
};

export default ResearchWorkspace;
