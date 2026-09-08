/**
 * Phase 15: Frontend Jest tests for React components.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import researchReducer from '@/store/researchSlice';
import HomePage from '@/components/HomePage';
import ResearchWorkspace from '@/components/ResearchWorkspace';
import ResearchResults from '@/components/ResearchResults';

// Mock Next.js router
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
}));

// Mock the API hook
jest.mock('@/hooks/useResearchAPI', () => ({
  useResearchAPI: () => ({
    startResearch: jest.fn().mockResolvedValue('123'),
    pollResearch: jest.fn().mockResolvedValue(undefined),
    fetchResearchStatus: jest.fn(),
    fetchSources: jest.fn(),
    fetchToolCalls: jest.fn(),
    fetchClaims: jest.fn(),
  }),
}));

const createTestStore = () => {
  return configureStore({
    reducer: {
      research: researchReducer,
    },
  });
};

describe('HomePage', () => {
  it('renders home page with form', () => {
    const store = createTestStore();
    render(
      <Provider store={store}>
        <HomePage />
      </Provider>
    );

    expect(screen.getByText('ResearchPilot AI')).toBeInTheDocument();
    expect(screen.getByLabelText(/what would you like to research/i)).toBeInTheDocument();
  });

  it('shows error on empty question submit', async () => {
    const store = createTestStore();
    render(
      <Provider store={store}>
        <HomePage />
      </Provider>
    );

    const submitButton = screen.getByRole('button', { name: /start research/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/please enter a research question/i)).toBeInTheDocument();
    });
  });

  it('updates character count as user types', () => {
    const store = createTestStore();
    render(
      <Provider store={store}>
        <HomePage />
      </Provider>
    );

    const textarea = screen.getByLabelText(/what would you like to research/i) as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Test question' } });

    expect(textarea.value).toBe('Test question');
  });

  it('updates max steps slider', () => {
    const store = createTestStore();
    render(
      <Provider store={store}>
        <HomePage />
      </Provider>
    );

    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '12' } });

    expect(screen.getByText('Max Research Steps: 12')).toBeInTheDocument();
  });

  it('shows error on question too long', async () => {
    const store = createTestStore();
    render(
      <Provider store={store}>
        <HomePage />
      </Provider>
    );

    const textarea = screen.getByLabelText(/what would you like to research/i) as HTMLTextAreaElement;
    const longText = 'a'.repeat(501);

    fireEvent.change(textarea, { target: { value: longText } });
    const submitButton = screen.getByRole('button', { name: /start research/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/must be 500 characters or less/i)).toBeInTheDocument();
    });
  });
});

describe('ResearchWorkspace', () => {
  it('renders workspace with research stats', () => {
    const store = configureStore({
      reducer: {
        research: researchReducer,
      },
      preloadedState: {
        research: {
          research_id: '123',
          question: 'Test question',
          status: 'loading',
          max_steps: 8,
          steps_used: 2,
          final_answer: null,
          created_at: new Date().toISOString(),
          completed_at: null,
          sources: [],
          tool_calls: [],
          claims: [],
          is_loading: true,
          error: null,
          current_step: 2,
          last_tool_used: 'web_search',
        },
      },
    });

    render(
      <Provider store={store}>
        <ResearchWorkspace researchId="123" />
      </Provider>
    );

    expect(screen.getByText('Test question')).toBeInTheDocument();
    expect(screen.getByText('2/8')).toBeInTheDocument();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('renders tool calls timeline', () => {
    const store = configureStore({
      reducer: {
        research: researchReducer,
      },
      preloadedState: {
        research: {
          research_id: '123',
          question: 'Test',
          status: 'completed',
          max_steps: 8,
          steps_used: 3,
          final_answer: 'Answer',
          created_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
          sources: [],
          tool_calls: [
            {
              step_number: 1,
              tool_name: 'web_search',
              status: 'success',
              input: { query: 'test' },
              output: null,
              created_at: new Date().toISOString(),
            },
          ],
          claims: [],
          is_loading: false,
          error: null,
          current_step: 3,
          last_tool_used: 'web_search',
        },
      },
    });

    render(
      <Provider store={store}>
        <ResearchWorkspace researchId="123" />
      </Provider>
    );

    expect(screen.getByText('WEB SEARCH')).toBeInTheDocument();
    expect(screen.getByText('SUCCESS')).toBeInTheDocument();
  });
});

describe('ResearchResults', () => {
  it('renders final answer', () => {
    const store = configureStore({
      reducer: {
        research: researchReducer,
      },
      preloadedState: {
        research: {
          research_id: '123',
          question: 'What is AI?',
          status: 'completed',
          max_steps: 8,
          steps_used: 5,
          final_answer: 'AI is artificial intelligence.',
          created_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
          sources: [],
          tool_calls: [],
          claims: [],
          is_loading: false,
          error: null,
          current_step: 5,
          last_tool_used: null,
        },
      },
    });

    render(
      <Provider store={store}>
        <ResearchResults researchId="123" />
      </Provider>
    );

    expect(screen.getByText('What is AI?')).toBeInTheDocument();
    expect(screen.getByText('AI is artificial intelligence.')).toBeInTheDocument();
  });

  it('renders sources with citations', () => {
    const store = configureStore({
      reducer: {
        research: researchReducer,
      },
      preloadedState: {
        research: {
          research_id: '123',
          question: 'Test',
          status: 'completed',
          max_steps: 8,
          steps_used: 3,
          final_answer: 'Answer',
          created_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
          sources: [
            {
              source_id: 'SRC-001',
              url: 'https://example.com',
              title: 'Example',
              domain: 'example.com',
              fetch_status: 'success',
              word_count: 100,
              fetched_at: new Date().toISOString(),
            },
          ],
          tool_calls: [],
          claims: [
            {
              claim_id: 1,
              claim_text: 'Test claim',
              citations: [
                {
                  source_id: 'SRC-001',
                  url: 'https://example.com',
                  title: 'Example',
                  citation_number: 1,
                  confidence: 0.95,
                  evidence: 'Test evidence',
                },
              ],
            },
          ],
          is_loading: false,
          error: null,
          current_step: 3,
          last_tool_used: null,
        },
      },
    });

    render(
      <Provider store={store}>
        <ResearchResults researchId="123" />
      </Provider>
    );

    expect(screen.getByText('All Sources Used')).toBeInTheDocument();
    expect(screen.getByText('Example')).toBeInTheDocument();
    expect(screen.getByText('Test claim')).toBeInTheDocument();
  });

  it('shows message when no final answer', () => {
    const store = configureStore({
      reducer: {
        research: researchReducer,
      },
      preloadedState: {
        research: {
          research_id: '123',
          question: 'Test',
          status: 'failed',
          max_steps: 8,
          steps_used: 0,
          final_answer: null,
          created_at: new Date().toISOString(),
          completed_at: null,
          sources: [],
          tool_calls: [],
          claims: [],
          is_loading: false,
          error: 'Failed',
          current_step: 0,
          last_tool_used: null,
        },
      },
    });

    render(
      <Provider store={store}>
        <ResearchResults researchId="123" />
      </Provider>
    );

    expect(screen.getByText(/did not produce/i)).toBeInTheDocument();
  });
});
