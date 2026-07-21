/**
 * Global state for the evaluation flow.
 * Zustand slice — no prop drilling needed.
 * Single responsibility: manage loading/error/result state.
 */
import { create } from 'zustand';
import type { EvaluateResponse, ApiError } from '@/types';

type EvaluationStatus = 'idle' | 'loading' | 'success' | 'error';

interface EvaluationState {
  status: EvaluationStatus;
  result: EvaluateResponse | null;
  error: ApiError | null;
  setLoading: () => void;
  setResult: (result: EvaluateResponse) => void;
  setError: (error: ApiError) => void;
  reset: () => void;
}

export const useEvaluationStore = create<EvaluationState>((set) => ({
  status: 'idle',
  result: null,
  error: null,

  setLoading: () => set({ status: 'loading', result: null, error: null }),
  setResult: (result) => set({ status: 'success', result, error: null }),
  setError: (error) => set({ status: 'error', error, result: null }),
  reset: () => set({ status: 'idle', result: null, error: null }),
}));
