/**
 * Generates a local object URL preview for a selected File.
 * Cleans up the URL on unmount to avoid memory leaks.
 */
import { useState, useEffect } from 'react';

export function useFilePreview(file: File | null): string | null {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }

    const url = URL.createObjectURL(file);
    setPreviewUrl(url);

    return () => {
      URL.revokeObjectURL(url);
    };
  }, [file]);

  return previewUrl;
}
