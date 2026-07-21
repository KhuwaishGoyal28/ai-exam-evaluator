/**
 * Upload form — file drop + exam type selector + question input + submit.
 * Passes exam_type through to the evaluate hook so the backend uses the right rubric.
 */
import { useState, useEffect, useRef } from 'react';
import { Zap } from 'lucide-react';
import { DropZone } from './DropZone';
import { FilePreview } from './FilePreview';
import { QuestionInput } from './QuestionInput';
import { ProcessingStatus } from './ProcessingStatus';
import { Button } from '@/components/ui/Button';
import { ErrorBanner } from '@/components/ui/ErrorBanner';
import { useEvaluate } from '@/hooks/useEvaluate';

export function UploadForm() {
  const [file, setFile]         = useState<File | null>(null);
  const [question, setQuestion] = useState('');
  const [elapsedMs, setElapsedMs] = useState(0);
  const timerRef = useRef<number | null>(null);

  const { evaluate, status, error, reset } = useEvaluate();
  const isLoading = status === 'loading';

  /* elapsed timer for the processing indicator */
  useEffect(() => {
    if (isLoading) {
      setElapsedMs(0);
      timerRef.current = window.setInterval(
        () => setElapsedMs((ms) => ms + 500),
        500,
      );
    } else {
      if (timerRef.current !== null) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
    return () => {
      if (timerRef.current !== null) clearInterval(timerRef.current);
    };
  }, [isLoading]);

  const handleRemoveFile = () => { setFile(null); reset(); };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    await evaluate(file, question || null);
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">

      {/* ── File drop or preview ── */}
      {file ? (
        <FilePreview file={file} onRemove={handleRemoveFile} />
      ) : (
        <DropZone onFileSelected={setFile} disabled={isLoading} />
      )}

      <div className="h-px bg-slate-100" />

      {/* ── Optional question ── */}
      <QuestionInput
        value={question}
        onChange={setQuestion}
        disabled={isLoading}
      />

      {/* ── Processing indicator ── */}
      {isLoading && <ProcessingStatus elapsedMs={elapsedMs} />}

      {/* ── Error ── */}
      {error && !isLoading && (
        <ErrorBanner
          error={error}
          onRetry={() => { reset(); setFile(null); }}
        />
      )}

      {/* ── Submit ── */}
      <Button
        type="submit"
        size="lg"
        disabled={!file || isLoading}
        isLoading={isLoading}
        className="w-full"
        leftIcon={!isLoading ? <Zap className="h-4 w-4" /> : undefined}
      >
        {isLoading ? 'Evaluating…' : 'Evaluate Answer Sheet'}
      </Button>

      <p className="text-center text-xs text-slate-400">
        Works for any subject · any class · any exam
      </p>
    </form>
  );
}
