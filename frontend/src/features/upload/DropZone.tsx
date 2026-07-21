/**
 * Drag-and-drop file input with animated border and icon.
 */
import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { UploadCloud, FileImage, AlertCircle } from 'lucide-react';
import { clsx } from 'clsx';

const ACCEPTED_TYPES = {
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'image/webp': ['.webp'],
  'application/pdf': ['.pdf'],
};

interface DropZoneProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

export function DropZone({ onFileSelected, disabled }: DropZoneProps) {
  const onDrop = useCallback(
    (accepted: File[]) => { if (accepted[0]) onFileSelected(accepted[0]); },
    [onFileSelected],
  );

  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxFiles: 1,
    maxSize: 10 * 1024 * 1024,
    disabled,
  });

  const hasRejection = fileRejections.length > 0;

  return (
    <div
      {...getRootProps()}
      className={clsx(
        'group relative flex cursor-pointer flex-col items-center justify-center gap-4',
        'rounded-2xl border-2 border-dashed p-10 transition-all duration-300',
        isDragActive
          ? 'border-brand-400 bg-brand-50 scale-[1.01] shadow-glow'
          : 'border-surface-200 bg-surface-50/50 hover:border-brand-300 hover:bg-brand-50/30',
        disabled && 'cursor-not-allowed opacity-50',
        hasRejection && 'border-rose-300 bg-rose-50',
      )}
      aria-label="File upload area"
    >
      <input {...getInputProps()} aria-label="Upload answer image or PDF" />

      {/* Icon */}
      <div className={clsx(
        'flex h-16 w-16 items-center justify-center rounded-2xl transition-all duration-300',
        isDragActive
          ? 'bg-brand-500 shadow-glow scale-110'
          : 'bg-white shadow-card group-hover:bg-brand-50 group-hover:shadow-md',
      )}>
        {isDragActive ? (
          <UploadCloud className="h-8 w-8 text-white" aria-hidden="true" />
        ) : (
          <FileImage className={clsx(
            'h-8 w-8 transition-colors duration-300',
            hasRejection ? 'text-rose-400' : 'text-surface-400 group-hover:text-brand-400',
          )} aria-hidden="true" />
        )}
      </div>

      {/* Text */}
      <div className="text-center">
        <p className={clsx(
          'text-sm font-semibold transition-colors duration-300',
          isDragActive ? 'text-brand-600' : 'text-surface-700',
        )}>
          {isDragActive ? 'Release to upload' : 'Drop your answer sheet here'}
        </p>
        <p className="mt-1.5 text-xs text-surface-400">
          or <span className="font-medium text-brand-500 hover:underline">click to browse</span>
        </p>
        <p className="mt-3 text-xs text-surface-400">
          JPEG · PNG · WebP · PDF &mdash; max 10 MB
        </p>
      </div>

      {hasRejection && (
        <div className="flex items-center gap-2 rounded-lg bg-rose-100 px-3 py-2" role="alert">
          <AlertCircle className="h-4 w-4 text-rose-500 shrink-0" />
          <p className="text-xs text-rose-600 font-medium">
            {fileRejections[0]?.errors[0]?.message ?? 'File rejected — check type and size'}
          </p>
        </div>
      )}
    </div>
  );
}
