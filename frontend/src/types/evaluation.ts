/**
 * TypeScript types mirroring the backend Pydantic schemas.
 * Single source of truth — all components import from here.
 */

export type RubricParameter =
  | 'Structure'
  | 'Content & Accuracy'
  | 'Language & Expression'
  | 'Relevance to Question'
  | 'Critical Thinking';

export type Sentiment = 'positive' | 'neutral' | 'negative';

export interface ParameterScore {
  parameter: RubricParameter;
  score: number;
  max_score: number;
  justification: string;
  suggestions: string[];
}

export interface AnnotationComment {
  paragraph_index: number;
  comment_text: string;
  sentiment: Sentiment;
}

export interface EvaluationResult {
  parameter_scores: ParameterScore[];
  total_score: number;
  max_total_score: number;
  overall_remark: string;
  /** Which exam type was used for evaluation */
  exam_type: string;
  strengths: string[];
  improvements: string[];
}

export interface EvaluateResponse {
  job_id: string;
  original_file_url: string;
  annotated_file_url: string;
  /** Full evaluation report stored in cloud (JSON) */
  report_url: string;
  extracted_text: string;
  word_count: number;
  ocr_low_confidence: boolean;
  evaluation: EvaluationResult;
  annotation_comments: AnnotationComment[];
}

export interface ApiError {
  code: string;
  message: string;
}
