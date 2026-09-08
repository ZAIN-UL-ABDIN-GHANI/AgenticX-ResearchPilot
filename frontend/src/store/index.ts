/**
 * Redux store configuration for ResearchPilot AI frontend.
 */

import { configureStore } from '@reduxjs/toolkit';
import researchReducer from './researchSlice';

export const store = configureStore({
  reducer: {
    research: researchReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        // Ignore certain action types that may contain non-serializable values
        ignoredActions: ['research/setError'],
        ignoredPaths: ['research.error'],
      },
    }),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

export default store;
