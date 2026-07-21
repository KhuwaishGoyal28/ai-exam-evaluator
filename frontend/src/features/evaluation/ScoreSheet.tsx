/**
 * Premium score sheet with animated ring, parameter bars, and overall remark.
 */
import { Award, TrendingUp, MessageCircle } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { ScoreRing } from './ScoreRing';
import type { EvaluationResult } from '@/types';

interface ScoreSheetProps {
  evaluation: EvaluationResult;
}

function gradeFromScore(score: number, max: number) {
  const pct = (score / max) * 100;
  if (pct >= 80) return { label: 'A', colour: 'text-emerald-500', bg: 'bg-emerald-50', border: 'border-emerald-200', remark: 'Excellent' };
  if (pct >= 60) return { label: 'B', colour: 'text-brand-500',   bg: 'bg-brand-50',   border: 'border-brand-200',   remark: 'Good' };
  if (pct >= 40) return { label: 'C', colour: 'text-amber-500',   bg: 'bg-amber-50',   border: 'border-amber-200',   remark: 'Average' };
  return           { label: 'D', colour: 'text-rose-500',     bg: 'bg-rose-50',     border: 'border-rose-200',     remark: 'Needs Work' };
}

const PARAM_ICONS: Record<string, string> = {
  'Structure':             '🏗️',
  'Content & Accuracy':   '📚',
  'Language & Expression':'✍️',
  'Relevance to Question':'🎯',
  'Critical Thinking':    '🧠',
};

export function ScoreSheet({ evaluation }: ScoreSheetProps) {
  const grade = gradeFromScore(evaluation.total_score, evaluation.max_total_score);

  return (
    <div className="space-y-4">
      {/* Score Hero Card */}
      <Card noPadding>
        <div className="flex items-center gap-6 p-5">
          {/* Ring */}
          <ScoreRing
            score={evaluation.total_score}
            maxScore={evaluation.max_total_score}
            grade={grade.label}
            gradeColor={grade.colour}
          />

          {/* Summary */}
          <div className="flex-1 min-w-0">
            <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 ${grade.bg} ${grade.border} mb-3`}>
              <Award className={`h-3.5 w-3.5 ${grade.colour}`} />
              <span className={`text-xs font-bold ${grade.colour}`}>{grade.remark}</span>
            </div>
            <p className="text-2xl font-black text-surface-900 leading-none">
              {evaluation.total_score}
              <span className="text-base font-normal text-surface-400"> / {evaluation.max_total_score}</span>
            </p>
            <p className="mt-1 text-xs text-surface-500">
              Top {Math.round((1 - evaluation.total_score / evaluation.max_total_score) * 100)}% improvement possible
            </p>
          </div>
        </div>

        {/* Thin grade bar at bottom */}
        <div className="h-1.5 rounded-b-2xl overflow-hidden">
          <div
            className={`h-full bg-gradient-to-r ${
              grade.label === 'A' ? 'from-emerald-400 to-teal-500' :
              grade.label === 'B' ? 'from-brand-400 to-indigo-500' :
              grade.label === 'C' ? 'from-amber-400 to-orange-400' :
              'from-rose-400 to-red-500'
            } transition-all duration-700`}
            style={{ width: `${(evaluation.total_score / evaluation.max_total_score) * 100}%` }}
          />
        </div>
      </Card>

      {/* Parameter Scores */}
      <Card titleIcon={<TrendingUp className="h-4 w-4" />} title="Parameter Breakdown">
        <div className="space-y-5">
          {evaluation.parameter_scores.map((ps, idx) => (
            <div
              key={ps.parameter}
              className="space-y-2 animate-in"
              style={{ animationDelay: `${idx * 80}ms` }}
            >
              <div className="flex items-center gap-2">
                <span className="text-base">{PARAM_ICONS[ps.parameter] ?? '📋'}</span>
                <ProgressBar value={ps.score} max={ps.max_score} label={ps.parameter} />
              </div>
              <p className="pl-8 text-xs text-surface-500 leading-relaxed">{ps.justification}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* Overall Remark */}
      <Card titleIcon={<MessageCircle className="h-4 w-4" />} title="Examiner's Remark">
        <blockquote className="relative pl-4">
          <div className="absolute left-0 top-0 bottom-0 w-1 rounded-full bg-gradient-to-b from-brand-400 to-accent-500" />
          <p className="text-sm text-surface-700 leading-relaxed italic">
            "{evaluation.overall_remark}"
          </p>
        </blockquote>
      </Card>
    </div>
  );
}
