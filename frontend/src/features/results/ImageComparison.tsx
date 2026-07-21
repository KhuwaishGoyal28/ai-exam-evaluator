/**
 * Answer sheet viewer — toggles between original and annotated.
 *
 * Smart rendering:
 *   - Original URL ending in .pdf → inline PDF viewer (<iframe>)
 *   - Everything else → image (<img>)
 *
 * Download actions:
 *   - Download annotated image
 *   - Download original file (image or PDF)
 *   - Download full JSON report
 */
import { useState } from 'react';
import { Download, Eye, PenLine, Maximize2, FileJson, FileText } from 'lucide-react';
import { clsx } from 'clsx';

type ViewMode = 'annotated' | 'original';

interface ImageComparisonProps {
  originalUrl: string;
  annotatedUrl: string;
  reportUrl?: string;
}

function isPdfUrl(url: string): boolean {
  return url.toLowerCase().includes('.pdf') || url.toLowerCase().includes('/original.pdf');
}

export function ImageComparison({ originalUrl, annotatedUrl, reportUrl }: ImageComparisonProps) {
  const [mode, setMode] = useState<ViewMode>('annotated');
  const [isFullscreen, setIsFullscreen] = useState(false);

  const currentUrl   = mode === 'annotated' ? annotatedUrl : originalUrl;
  const showPdf      = mode === 'original' && isPdfUrl(originalUrl);

  return (
    <div className="space-y-3">

      {/* ── Mode toggle ──────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 rounded-2xl border border-slate-100 bg-white p-1.5 shadow-sm">
        {(['annotated', 'original'] as ViewMode[]).map((m) => {
          const Icon = m === 'annotated' ? PenLine : Eye;
          return (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={clsx(
                'flex flex-1 items-center justify-center gap-2 rounded-xl px-4 py-2',
                'text-sm font-medium transition-all duration-200',
                mode === m
                  ? 'bg-gradient-to-r from-violet-500 to-teal-500 text-white shadow-md'
                  : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700',
              )}
              aria-pressed={mode === m}
            >
              <Icon className="h-3.5 w-3.5" />
              {m === 'annotated' ? 'Annotated' : 'Original'}
              {m === 'original' && isPdfUrl(originalUrl) && (
                <span className="ml-1 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-500">
                  PDF
                </span>
              )}
            </button>
          );
        })}
        <button
          type="button"
          onClick={() => setIsFullscreen(!isFullscreen)}
          title="Toggle fullscreen"
          className="ml-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-slate-400 hover:bg-slate-50 hover:text-slate-700 transition-all duration-200"
          aria-label="Toggle fullscreen"
        >
          <Maximize2 className="h-4 w-4" />
        </button>
      </div>

      {/* ── Viewer ───────────────────────────────────────────────────── */}
      <div className={clsx(
        'group relative overflow-hidden rounded-2xl border border-slate-100 bg-white',
        'shadow-[0_1px_3px_rgba(0,0,0,0.06),0_4px_16px_rgba(0,0,0,0.04)]',
        'transition-all duration-300',
        isFullscreen && 'fixed inset-4 z-50 flex flex-col bg-slate-950 shadow-2xl',
      )}>

        {/* Fullscreen close button */}
        {isFullscreen && (
          <button
            onClick={() => setIsFullscreen(false)}
            className="absolute right-3 top-3 z-10 rounded-full bg-black/60 p-2 text-white backdrop-blur hover:bg-black/80 transition-all"
            aria-label="Close fullscreen"
          >
            ✕
          </button>
        )}

        {/* PDF inline viewer */}
        {showPdf ? (
          <div className="flex flex-col">
            {/* PDF label bar */}
            <div className="flex items-center gap-2 border-b border-slate-100 bg-slate-50 px-4 py-2">
              <FileText className="h-4 w-4 text-violet-500" aria-hidden="true" />
              <span className="text-xs font-semibold text-slate-600">Original PDF document</span>
              <a
                href={originalUrl}
                target="_blank"
                rel="noreferrer"
                className="ml-auto text-xs text-violet-600 hover:underline"
              >
                Open in new tab ↗
              </a>
            </div>
            <iframe
              src={originalUrl}
              title="Original PDF"
              className={clsx(
                'w-full border-0 bg-white',
                isFullscreen ? 'flex-1' : 'h-[560px]',
              )}
              allow="fullscreen"
            />
          </div>
        ) : (
          /* Image viewer */
          <>
            <img
              key={mode}
              src={currentUrl}
              alt={mode === 'annotated' ? 'Annotated answer with margin feedback' : 'Original uploaded answer'}
              className={clsx(
                'w-full object-contain',
                isFullscreen ? 'max-h-[calc(100vh-4rem)]' : 'max-h-[560px]',
              )}
              loading="lazy"
            />
            {!isFullscreen && (
              <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/8 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
            )}
          </>
        )}
      </div>

      {/* ── Download actions ─────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2">

        {/* Annotated image */}
        <a
          href={annotatedUrl}
          download="annotated.jpg"
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-medium text-slate-600 shadow-xs hover:border-violet-200 hover:text-violet-700 hover:shadow-sm transition-all duration-200"
        >
          <Download className="h-3.5 w-3.5" />
          Annotated image
        </a>

        {/* Original file — label adapts to PDF vs image */}
        <a
          href={originalUrl}
          download={isPdfUrl(originalUrl) ? 'original.pdf' : 'original.jpg'}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-medium text-slate-600 shadow-xs hover:border-teal-200 hover:text-teal-700 hover:shadow-sm transition-all duration-200"
        >
          {isPdfUrl(originalUrl)
            ? <FileText className="h-3.5 w-3.5" />
            : <Download className="h-3.5 w-3.5" />
          }
          {isPdfUrl(originalUrl) ? 'Original PDF' : 'Original image'}
        </a>

        {/* Full JSON report */}
        {reportUrl && (
          <a
            href={reportUrl}
            download="evaluation_report.json"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-xl border border-violet-200 bg-violet-50 px-4 py-2 text-xs font-semibold text-violet-700 shadow-xs hover:bg-violet-100 hover:shadow-sm transition-all duration-200"
          >
            <FileJson className="h-3.5 w-3.5" />
            Full report (JSON)
          </a>
        )}

      </div>
    </div>
  );
}
