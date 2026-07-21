/** File preview card with thumbnail or PDF icon. */
import { FileText, X, Image as ImageIcon } from 'lucide-react';
import { useFilePreview } from '@/hooks/useFilePreview';
import { clsx } from 'clsx';

interface FilePreviewProps {
  file: File;
  onRemove: () => void;
}

function isImage(file: File) { return file.type.startsWith('image/'); }
function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function FilePreview({ file, onRemove }: FilePreviewProps) {
  const previewUrl = useFilePreview(isImage(file) ? file : null);
  const isPdf = file.type === 'application/pdf';

  return (
    <div className="flex items-center gap-4 rounded-2xl border border-surface-100 bg-white p-4 shadow-card animate-in">
      {/* Thumbnail */}
      <div className={clsx(
        'relative flex h-16 w-16 shrink-0 items-center justify-center rounded-xl overflow-hidden',
        previewUrl ? '' : 'bg-surface-50',
      )}>
        {previewUrl ? (
          <img src={previewUrl} alt="Preview" className="h-full w-full object-cover" />
        ) : (
          <div className={clsx(
            'flex h-full w-full items-center justify-center rounded-xl',
            isPdf ? 'bg-rose-50' : 'bg-blue-50',
          )}>
            {isPdf
              ? <FileText className="h-7 w-7 text-rose-400" />
              : <ImageIcon className="h-7 w-7 text-blue-400" />
            }
          </div>
        )}
      </div>

      {/* Info */}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-surface-800">{file.name}</p>
        <p className="mt-0.5 text-xs text-surface-400">
          {formatBytes(file.size)} &middot; {file.type.split('/')[1]?.toUpperCase()}
        </p>
        <div className="mt-1.5 flex items-center gap-1.5">
          <div className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          <span className="text-xs text-emerald-600 font-medium">Ready to evaluate</span>
        </div>
      </div>

      {/* Remove */}
      <button
        type="button"
        onClick={onRemove}
        className="shrink-0 rounded-xl p-2 text-surface-400 hover:bg-rose-50 hover:text-rose-500 transition-all duration-200"
        aria-label="Remove selected file"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
