/**
 * Phase 13/14: Research results page with citations and sources.
 */

'use client';

import React from 'react';
import { useSelector } from 'react-redux';
import { RootState } from '@/store';

export interface ResearchResultsProps {
  researchId: string;
}

export const ResearchResults: React.FC<ResearchResultsProps> = ({
  researchId,
}) => {
  const research = useSelector((state: RootState) => state.research);

  if (!research.final_answer) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 rounded">
          <p className="text-sm text-yellow-700">
            Research did not produce a final answer. Check the research status for details.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* Research Question */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-4">
          {research.question}
        </h1>
        <div className="flex gap-4 text-sm text-gray-600">
          <span>✓ Completed</span>
          <span>• {research.steps_used} steps</span>
          <span>• {research.sources.length} sources</span>
          <span>• {research.claims.length} claims</span>
        </div>
      </div>

      {/* Final Answer Section */}
      <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Answer</h2>
        <div className="prose prose-lg max-w-none">
          <p className="text-lg text-gray-800 leading-relaxed whitespace-pre-wrap">
            {research.final_answer}
          </p>
        </div>
      </div>

      {/* Citations Section */}
      {research.claims.length > 0 && (
        <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">
            Citations ({research.claims.length})
          </h2>
          <div className="space-y-6">
            {research.claims.map((claim, idx) => (
              <div key={claim.claim_id} className="border border-gray-200 rounded-lg p-6">
                {/* Claim Text */}
                <div className="mb-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">
                    Claim {idx + 1}
                  </h3>
                  <p className="text-gray-700">{claim.claim_text}</p>
                </div>

                {/* Supporting Citations */}
                {claim.citations && claim.citations.length > 0 && (
                  <div className="space-y-3">
                    <h4 className="text-sm font-semibold text-gray-700 uppercase">
                      Supporting Sources
                    </h4>
                    {claim.citations.map((citation, cidx) => (
                      <div
                        key={cidx}
                        className="bg-gray-50 rounded p-4 border-l-4 border-indigo-500"
                      >
                        <div className="flex justify-between items-start">
                          <div className="flex-grow">
                            <h5 className="font-semibold text-gray-900">
                              {citation.title || 'Untitled Source'}
                            </h5>
                            {citation.url && (
                              <a
                                href={citation.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-sm text-indigo-600 hover:text-indigo-800 truncate"
                              >
                                {citation.url}
                              </a>
                            )}
                            {citation.source_id && (
                              <p className="text-xs text-gray-500">
                                Domain: {citation.source_id}
                              </p>
                            )}
                            {citation.evidence && (
                              <p className="text-sm text-gray-600 mt-2 italic">
                                &quot;{citation.evidence}&quot;
                              </p>
                            )}
                          </div>
                          {citation.confidence !== null && (
                            <div className="flex-shrink-0 ml-4">
                              <div className="text-xs font-semibold text-gray-600">
                                Confidence
                              </div>
                              <div className="text-lg font-bold text-indigo-600">
                                {(citation.confidence * 100).toFixed(0)}%
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* No Citations Warning */}
                {(!claim.citations || claim.citations.length === 0) && (
                  <div className="bg-yellow-50 border-l-4 border-yellow-500 p-3 rounded">
                    <p className="text-xs text-yellow-700">
                      No sources cited for this claim
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sources Reference */}
      {research.sources.length > 0 && (
        <div className="bg-white rounded-lg shadow-lg p-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">
            All Sources Used
          </h2>
          <div className="space-y-4">
            {research.sources.map((source, idx) => (
              <div key={source.source_id} className="border border-gray-200 rounded p-4">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <h3 className="font-semibold text-gray-900">
                      [{idx + 1}] {source.title || 'Untitled'}
                    </h3>
                    {source.url && (
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-indigo-600 hover:text-indigo-800 truncate block"
                      >
                        {source.url}
                      </a>
                    )}
                  </div>
                  <span
                    className={`px-3 py-1 rounded text-xs font-semibold flex-shrink-0 ml-2 ${
                      source.fetch_status === 'success'
                        ? 'bg-green-100 text-green-800'
                        : 'bg-red-100 text-red-800'
                    }`}
                  >
                    {source.fetch_status.toUpperCase()}
                  </span>
                </div>
                <div className="text-xs text-gray-500">
                  {source.domain && <span>Domain: {source.domain}</span>}
                  {source.word_count && (
                    <span> • {source.word_count} words</span>
                  )}
                  {source.fetched_at && (
                    <span> • Fetched: {new Date(source.fetched_at).toLocaleString()}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Export/Share Options */}
      <div className="mt-8 flex gap-4">
        <button
          onClick={() => window.print()}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
        >
          Print Results
        </button>
        <button
          onClick={() => {
            const text = `${research.question}\n\n${research.final_answer}`;
            navigator.clipboard.writeText(text);
            alert('Results copied to clipboard');
          }}
          className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
        >
          Copy to Clipboard
        </button>
      </div>
    </div>
  );
};

export default ResearchResults;
