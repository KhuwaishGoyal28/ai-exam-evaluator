/**
 * Exam type selector — visual card grid, one per category group.
 * Single responsibility: let the user pick the exam context before submitting.
 */
import { clsx } from 'clsx';

export type ExamTypeValue =
  | 'Class 6–8 Test'
  | 'Class 9–10 / Board'
  | 'Class 11–12 / Board'
  | 'JEE / Engineering'
  | 'NEET / Medical'
  | 'UPSC / Civil Services'
  | 'CLAT / Law'
  | 'CAT / MBA'
  | 'College / University'
  | 'Language / Literature'
  | 'Custom / General';

interface ExamOption {
  value: ExamTypeValue;
  label: string;
  emoji: string;
  group: string;
}

const EXAM_OPTIONS: ExamOption[] = [
  // School
  { value: 'Class 6–8 Test',       label: 'Class 6–8',     emoji: '📝', group: 'School' },
  { value: 'Class 9–10 / Board',   label: 'Class 9–10',    emoji: '📖', group: 'School' },
  { value: 'Class 11–12 / Board',  label: 'Class 11–12',   emoji: '🎓', group: 'School' },
  // Entrance
  { value: 'JEE / Engineering',    label: 'JEE',           emoji: '⚙️',  group: 'Entrance' },
  { value: 'NEET / Medical',       label: 'NEET',          emoji: '🩺', group: 'Entrance' },
  { value: 'UPSC / Civil Services',label: 'UPSC',          emoji: '🏛️', group: 'Entrance' },
  { value: 'CLAT / Law',           label: 'CLAT',          emoji: '⚖️',  group: 'Entrance' },
  { value: 'CAT / MBA',            label: 'CAT / MBA',     emoji: '📊', group: 'Entrance' },
  // Higher
  { value: 'College / University', label: 'College',       emoji: '🏫', group: 'Higher' },
  { value: 'Language / Literature',label: 'Language',      emoji: '📚', group: 'Higher' },
  { value: 'Custom / General',     label: 'Other / Custom',emoji: '✏️',  group: 'Higher' },
];

const GROUPS = ['School', 'Entrance', 'Higher'];
const GROUP_LABELS: Record<string, string> = {
  School:   'School',
  Entrance: 'Entrance Exams',
  Higher:   'College & Others',
};

interface ExamTypeSelectorProps {
  value: ExamTypeValue;
  onChange: (v: ExamTypeValue) => void;
  disabled?: boolean;
}

export function ExamTypeSelector({ value, onChange, disabled }: ExamTypeSelectorProps) {
  return (
    <div className="space-y-3">
      <label className="block text-sm font-semibold text-slate-700">
        Exam / Class Type
      </label>

      {GROUPS.map((group) => (
        <div key={group}>
          <p className="mb-1.5 text-[11px] font-bold uppercase tracking-widest text-slate-400">
            {GROUP_LABELS[group]}
          </p>
          <div className="flex flex-wrap gap-2">
            {EXAM_OPTIONS.filter((o) => o.group === group).map((opt) => {
              const selected = value === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  disabled={disabled}
                  onClick={() => onChange(opt.value)}
                  className={clsx(
                    'inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5',
                    'text-xs font-semibold transition-all duration-150',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500',
                    'disabled:cursor-not-allowed disabled:opacity-50',
                    selected
                      ? 'border-violet-500 bg-violet-500 text-white shadow-md'
                      : 'border-slate-200 bg-white text-slate-600 hover:border-violet-300 hover:text-violet-700',
                  )}
                  aria-pressed={selected}
                >
                  <span aria-hidden="true">{opt.emoji}</span>
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
