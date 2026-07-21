/** Question/topic input with character counter and focus styling. */
import { type ChangeEvent } from 'react';
import { HelpCircle } from 'lucide-react';

interface QuestionInputProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

const MAX_LENGTH = 500;

export function QuestionInput({ value, onChange, disabled }: QuestionInputProps) {
  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    if (e.target.value.length <= MAX_LENGTH) onChange(e.target.value);
  };
  const remaining = MAX_LENGTH - value.length;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <HelpCircle className="h-3.5 w-3.5 text-surface-400" aria-hidden="true" />
        <label htmlFor="question-input" className="text-sm font-medium text-surface-700">
          Exam Question / Topic
          <span className="ml-1.5 text-xs font-normal text-surface-400">(optional)</span>
        </label>
      </div>
      <textarea
        id="question-input"
        value={value}
        onChange={handleChange}
        disabled={disabled}
        rows={2}
        placeholder="e.g. Discuss the role of civil services in India's democratic governance."
        className="w-full resize-none rounded-xl border border-surface-200 bg-white px-4 py-3 text-sm
                   text-surface-800 placeholder:text-surface-400
                   focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100
                   disabled:cursor-not-allowed disabled:bg-surface-50 disabled:text-surface-400
                   transition-all duration-200"
      />
      <div className="flex items-center justify-between">
        <p className="text-xs text-surface-400">Helps the AI evaluate relevance more accurately</p>
        <p className={`text-xs tabular-nums ${remaining < 50 ? 'text-amber-500 font-medium' : 'text-surface-400'}`}>
          {remaining} left
        </p>
      </div>
    </div>
  );
}
