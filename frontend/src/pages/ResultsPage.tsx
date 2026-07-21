/**
 * Results page — full evaluation output.
 */
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, CheckCircle2, FileText, Image as ImageIcon, BarChart3, MessageSquare } from 'lucide-react';
import { PageLayout } from '@/components/layout/PageLayout';
import { ImageComparison } from '@/features/results/ImageComparison';
import { ExtractedText } from '@/features/results/ExtractedText';
import { ScoreSheet } from '@/features/evaluation/ScoreSheet';
import { AnnotationList } from '@/features/evaluation/AnnotationList';
import { useEvaluationStore } from '@/store/evaluationStore';

export function ResultsPage() {
  const { result, reset } = useEvaluationStore();
  const navigate = useNavigate();

  useEffect(() => {
    if (!result) navigate('/');
  }, [result, navigate]);

  if (!result) return null;

  return (
    <PageLayout>

      {/* ── Results hero banner ───────────────────────────────────────── */}
      <div className="bg-gradient-to-r from-violet-700 to-teal-600">
        <div className="container-pad py-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">

            {/* Left — status */}
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/20">
                <CheckCircle2 className="h-5 w-5 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-white">Evaluation Complete</h1>
                <p className="text-sm text-white/70">
                  {result.evaluation.exam_type ?? 'Answer sheet'} · {result.word_count} words
                </p>
              </div>
            </div>

            {/* Right — score pill + back button */}
            <div className="flex items-center gap-3">
              <div className="rounded-2xl bg-white/15 px-5 py-2.5 text-center backdrop-blur">
                <p className="text-xs font-medium text-white/70">Total Score</p>
                <p className="text-2xl font-black tabular-nums text-white">
                  {result.evaluation.total_score}
                  <span className="text-base font-normal text-white/60">
                    /{result.evaluation.max_total_score}
                  </span>
                </p>
              </div>
              <button
                onClick={() => { reset(); navigate('/'); }}
                className="flex items-center gap-2 rounded-2xl border border-white/20 bg-white/15 px-4 py-2.5 text-sm font-semibold text-white backdrop-blur hover:bg-white/25 transition-all duration-200"
              >
                <ArrowLeft className="h-4 w-4" />
                New Evaluation
              </button>
            </div>

          </div>
        </div>
      </div>

      {/* ── Main grid ────────────────────────────────────────────────── */}
      <div className="container-pad space-y-8 py-8">

        {/* Row 1 — Answer sheet viewer + Score sheet */}
        <div className="grid gap-6 xl:grid-cols-2">
          <div className="space-y-5">
            <SectionLabel icon={<ImageIcon className="h-4 w-4" />} label="Your Answer Sheet" />
            <ImageComparison
              originalUrl={result.original_file_url}
              annotatedUrl={result.annotated_file_url}
              reportUrl={result.report_url}
            />
          </div>
          <div className="space-y-5">
            <SectionLabel icon={<BarChart3 className="h-4 w-4" />} label="Score Breakdown" />
            <ScoreSheet evaluation={result.evaluation} />
          </div>
        </div>

        {/* Row 2 — Extracted text + Annotations */}
        <div className="grid gap-6 xl:grid-cols-2">
          <div className="space-y-5">
            <SectionLabel icon={<FileText className="h-4 w-4" />} label="Extracted Text" />
            <ExtractedText
              text={result.extracted_text}
              wordCount={result.word_count}
              lowConfidence={result.ocr_low_confidence}
            />
          </div>
          <div className="space-y-5">
            <SectionLabel icon={<MessageSquare className="h-4 w-4" />} label="Inline Feedback" />
            <AnnotationList comments={result.annotation_comments} />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-center gap-3 border-t border-slate-100 pt-6">
          <div className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          <p className="font-mono text-xs text-slate-400">ID: {result.job_id}</p>
        </div>

      </div>
    </PageLayout>
  );
}

function SectionLabel({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-50 text-violet-500">
        {icon}
      </span>
      <h2 className="text-xs font-bold uppercase tracking-widest text-slate-400">{label}</h2>
    </div>
  );
}
