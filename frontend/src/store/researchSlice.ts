/**
 * Phase 12: Redux Toolkit slice for research state management.
 * 
 * Manages:
 * - Current research status
 * - Research results and sources
 * - Tool execution history
 * - Claims and citations
 * - Loading and error states
 */

import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export interface Source {
  source_id: string;
  url: string;
  title: string | null;
  domain: string | null;
  fetch_status: string;
  word_count: number | null;
  fetched_at: string | null;
}

export interface ToolCall {
  step_number: number | null;
  tool_name: string;
  status: string;
  input: Record<string, any> | null;
  output: Record<string, any> | null;
  created_at: string;
}

export interface Citation {
  source_id: string | null;
  url: string | null;
  title: string | null;
  citation_number: number | null;
  confidence: number | null;
  evidence: string | null;
}

export interface Claim {
  claim_id: number;
  claim_text: string;
  citations: Citation[];
}

export interface ResearchState {
  research_id: string | null;
  question: string;
  status: 'idle' | 'loading' | 'completed' | 'failed' | 'step_limit_reached';
  max_steps: number;
  steps_used: number;
  final_answer: string | null;
  created_at: string | null;
  completed_at: string | null;
  
  // Research data
  sources: Source[];
  tool_calls: ToolCall[];
  claims: Claim[];
  
  // UI state
  is_loading: boolean;
  error: string | null;
  current_step: number;
  last_tool_used: string | null;
}

const initialState: ResearchState = {
  research_id: null,
  question: '',
  status: 'idle',
  max_steps: 8,
  steps_used: 0,
  final_answer: null,
  created_at: null,
  completed_at: null,
  
  sources: [],
  tool_calls: [],
  claims: [],
  
  is_loading: false,
  error: null,
  current_step: 0,
  last_tool_used: null,
};

export const researchSlice = createSlice({
  name: 'research',
  initialState,
  reducers: {
    // Initialize new research
    setResearchInitialized: (
      state,
      action: PayloadAction<{
        research_id: string;
        question: string;
        max_steps: number;
        created_at: string;
      }>
    ) => {
      state.research_id = action.payload.research_id;
      state.question = action.payload.question;
      state.max_steps = action.payload.max_steps;
      state.created_at = action.payload.created_at;
      state.status = 'loading';
      state.is_loading = true;
      state.error = null;
    },

    // Update research status
    setResearchStatus: (
      state,
      action: PayloadAction<{
        status: ResearchState['status'];
        steps_used: number;
        final_answer?: string | null;
        completed_at?: string | null;
      }>
    ) => {
      state.status = action.payload.status;
      state.steps_used = action.payload.steps_used;
      if (action.payload.final_answer !== undefined) {
        state.final_answer = action.payload.final_answer;
      }
      if (action.payload.completed_at !== undefined) {
        state.completed_at = action.payload.completed_at;
      }
      if (action.payload.status === 'completed') {
        state.is_loading = false;
      }
    },

    // Add source to research
    addSource: (state, action: PayloadAction<Source>) => {
      const exists = state.sources.find(
        (s) => s.source_id === action.payload.source_id
      );
      if (!exists) {
        state.sources.push(action.payload);
      }
    },

    // Update source fetch status
    updateSourceFetchStatus: (
      state,
      action: PayloadAction<{
        source_id: string;
        fetch_status: string;
        word_count?: number;
        fetched_at?: string;
      }>
    ) => {
      const source = state.sources.find(
        (s) => s.source_id === action.payload.source_id
      );
      if (source) {
        source.fetch_status = action.payload.fetch_status;
        if (action.payload.word_count !== undefined) {
          source.word_count = action.payload.word_count;
        }
        if (action.payload.fetched_at !== undefined) {
          source.fetched_at = action.payload.fetched_at;
        }
      }
    },

    // Add tool call record
    addToolCall: (state, action: PayloadAction<ToolCall>) => {
      state.tool_calls.push(action.payload);
      state.current_step = (action.payload.step_number || 0) + 1;
      state.last_tool_used = action.payload.tool_name;
    },

    // Add claim with citations
    addClaim: (state, action: PayloadAction<Claim>) => {
      const exists = state.claims.find(
        (c) => c.claim_id === action.payload.claim_id
      );
      if (!exists) {
        state.claims.push(action.payload);
      }
    },

    // Set research error
    setError: (state, action: PayloadAction<string>) => {
      state.error = action.payload;
      state.is_loading = false;
      state.status = 'failed';
    },

    // Clear research error
    clearError: (state) => {
      state.error = null;
    },

    // Reset research state
    resetResearch: (state) => {
      return initialState;
    },

    // Set loading state
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.is_loading = action.payload;
    },

    // Set step limit reached
    setStepLimitReached: (state) => {
      state.status = 'step_limit_reached';
      state.is_loading = false;
    },

    // Bulk update research data
    updateResearchData: (
      state,
      action: PayloadAction<Partial<ResearchState>>
    ) => {
      return { ...state, ...action.payload };
    },
  },
});

export const {
  setResearchInitialized,
  setResearchStatus,
  addSource,
  updateSourceFetchStatus,
  addToolCall,
  addClaim,
  setError,
  clearError,
  resetResearch,
  setLoading,
  setStepLimitReached,
  updateResearchData,
} = researchSlice.actions;

export default researchSlice.reducer;
