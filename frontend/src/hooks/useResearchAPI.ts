/**
 * Phase 13: Custom React hook for research API communication.
 * 
 * Provides methods for:
 * - Starting research
 * - Polling research status
 * - Fetching sources, tools, claims
 * - Error handling and retry logic
 */

import { useState, useCallback } from 'react';
import { useDispatch } from 'react-redux';
import axios from 'axios';
import {
  setResearchInitialized,
  setResearchStatus,
  addSource,
  addToolCall,
  addClaim,
  setError,
  setLoading,
} from '@/store/researchSlice';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_CLIENT = axios.create({
  baseURL: API_URL,
  timeout: 30000,
});

export interface UseResearchAPIOptions {
  pollInterval?: number; // milliseconds between polling
  maxRetries?: number;
}

export const useResearchAPI = (options: UseResearchAPIOptions = {}) => {
  const dispatch = useDispatch();
  const {
    pollInterval = 2000,
    maxRetries = 3,
  } = options;

  const [isPolling, setIsPolling] = useState(false);

  /**
   * Start a new research task.
   */
  const startResearch = useCallback(
    async (question: string, maxSteps: number = 8) => {
      try {
        dispatch(setLoading(true));

        const response = await API_CLIENT.post('/api/v1/research', {
          question,
          max_steps: maxSteps,
        });

        const { research_id, status, created_at } = response.data;

        dispatch(
          setResearchInitialized({
            research_id,
            question,
            max_steps: maxSteps,
            created_at,
          })
        );

        return research_id;
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : 'Failed to start research';
        dispatch(setError(errorMessage));
        throw error;
      } finally {
        dispatch(setLoading(false));
      }
    },
    [dispatch]
  );

  /**
   * Fetch research status by ID.
   */
  const fetchResearchStatus = useCallback(
    async (researchId: string) => {
      try {
        const response = await API_CLIENT.get(`/api/v1/research/${researchId}`);
        const data = response.data;

        dispatch(
          setResearchStatus({
            status: data.status,
            steps_used: data.steps_used,
            final_answer: data.final_answer,
            completed_at: data.completed_at,
          })
        );

        return data;
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : 'Failed to fetch research status';
        dispatch(setError(errorMessage));
        throw error;
      }
    },
    [dispatch]
  );

  /**
   * Fetch sources for research.
   */
  const fetchSources = useCallback(
    async (researchId: string) => {
      try {
        const response = await API_CLIENT.get(
          `/api/v1/research/${researchId}/sources`
        );
        const { sources } = response.data;

        // Add each source to Redux
        sources.forEach((source: any) => {
          dispatch(addSource(source));
        });

        return sources;
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : 'Failed to fetch sources';
        dispatch(setError(errorMessage));
        throw error;
      }
    },
    [dispatch]
  );

  /**
   * Fetch tool calls for research.
   */
  const fetchToolCalls = useCallback(
    async (researchId: string) => {
      try {
        const response = await API_CLIENT.get(
          `/api/v1/research/${researchId}/tools`
        );
        const { tool_calls } = response.data;

        // Add each tool call to Redux
        tool_calls.forEach((call: any) => {
          dispatch(addToolCall(call));
        });

        return tool_calls;
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : 'Failed to fetch tool calls';
        dispatch(setError(errorMessage));
        throw error;
      }
    },
    [dispatch]
  );

  /**
   * Fetch claims and citations for research.
   */
  const fetchClaims = useCallback(
    async (researchId: string) => {
      try {
        const response = await API_CLIENT.get(
          `/api/v1/research/${researchId}/claims`
        );
        const { claims } = response.data;

        // Add each claim to Redux
        claims.forEach((claim: any) => {
          dispatch(addClaim(claim));
        });

        return claims;
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : 'Failed to fetch claims';
        dispatch(setError(errorMessage));
        throw error;
      }
    },
    [dispatch]
  );

  /**
   * Poll research until completion.
   * 
   * Continuously fetches research status, sources, and tools
   * until research is completed or failed.
   */
  const pollResearch = useCallback(
    async (researchId: string) => {
      setIsPolling(true);

      try {
        let isCompleted = false;
        let attempts = 0;
        const maxAttempts = 300; // 10 minutes at 2-second intervals

        while (!isCompleted && attempts < maxAttempts) {
          try {
            const status = await fetchResearchStatus(researchId);

            // Fetch associated data
            await Promise.all([
              fetchSources(researchId),
              fetchToolCalls(researchId),
              fetchClaims(researchId),
            ]);

            // Check if completed
            if (
              status.status === 'completed' ||
              status.status === 'failed' ||
              status.status === 'step_limit_reached'
            ) {
              isCompleted = true;
            }

            if (!isCompleted) {
              // Wait before next poll
              await new Promise((resolve) => setTimeout(resolve, pollInterval));
            }
          } catch (error) {
            console.error('Error during polling:', error);
            // Retry on error
            attempts++;
            if (attempts < maxAttempts) {
              await new Promise((resolve) =>
                setTimeout(resolve, pollInterval * 2)
              );
            }
          }

          attempts++;
        }

        if (attempts >= maxAttempts) {
          throw new Error('Research polling timeout');
        }
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : 'Polling failed';
        dispatch(setError(errorMessage));
        throw error;
      } finally {
        setIsPolling(false);
      }
    },
    [dispatch, fetchResearchStatus, fetchSources, fetchToolCalls, fetchClaims, pollInterval]
  );

  /**
   * Health check endpoint.
   */
  const checkHealth = useCallback(async () => {
    try {
      const response = await API_CLIENT.get('/health');
      return response.data;
    } catch (error) {
      console.error('Health check failed:', error);
      return { status: 'error' };
    }
  }, []);

  return {
    startResearch,
    fetchResearchStatus,
    fetchSources,
    fetchToolCalls,
    fetchClaims,
    pollResearch,
    checkHealth,
    isPolling,
  };
};
