/**
 * Scrollable extracted text view with word count and confidence warning.
 */
import { useState } from 'react';
import { FileText, AlertTriangle, ChevronDown, ChevronUp, Copy, Check } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { clsx } from 'clsx';

interface ExtractedTextProps {
  text: string;
  wordCount: number;
  lowConfidence: boolean;
}

export function ExtractedText({ text, wordCount, lowConfidence }: ExtractedTextProps) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Card titleIcon={<FileText className="h-4 w-4" />} title="Extracted Text (OCR)">
      {lowConfidence && (
        <div className="mb-4 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3.5">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" aria-hidden="true" />
          <div>
            <p className="text-sm font-medium text-amber-800">Low OCR Confidence</p>
            <p className="mt-0.5 text-xs text-amber-700">
              Handwriting may be difficult to read accurately. Upload a clearer scan for better results.
            </p>
          </div>
        </div>
      )}

      {/* Stats row */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5 text-xs text-surface-500">
            <div className="h-1.5 w-1.5 rounded-full bg-brand-400" />
            <span className="font-semibold tabular-nums text-surface-800">{wordCount}</span>
            <span>words</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-surface-500">
            <div className="h-1.5 w-1.5 rounded-full bg-accent-400" />
            <span className="font-semibold tabular-nums text-surface-800">{text.length}</span>
            <span>characters</span>
          </div>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-surface-500 hover:bg-surface-50 hover:text-surface-700 transition-all duration-200"
        >
          {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>

      {/* Text area */}
      <div className={clsx(
        'relative overflow-hidden rounded-xl border border-surface-100 bg-surface-50',
        'transition-all duration-500',
      )}>
        <pre className={clsx(
          'whitespace-pre-wrap p-4 text-sm leading-relaxed text-surface-700 font-sans',
          'transition-all duration-500',
          !expanded && 'max-h-52 overflow-hidden',
        )}>
          {text}
        </pre>

        {/* Fade overlay when collapsed */}
        {!expanded && (
          <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-surface-50 to-transparent" />
        )}
      </div>

      {/* Expand/Collapse */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="mt-2.5 flex w-full items-center justify-center gap-1.5 rounded-xl border border-surface-100 py-2 text-xs font-medium text-surface-500 hover:bg-surface-50 hover:text-surface-700 transition-all duration-200"
      >
        {expanded ? (
          <><ChevronUp className="h-3.5 w-3.5" />Show less</>
        ) : (
          <><ChevronDown className="h-3.5 w-3.5" />Show full text</>
        )}
      </button>
    </Card>
  );
}
