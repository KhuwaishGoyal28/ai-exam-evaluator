import { Link } from 'react-router-dom';
import { PageLayout } from '@/components/layout/PageLayout';

export function NotFoundPage() {
  return (
    <PageLayout>
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <p className="text-6xl font-black text-gray-200">404</p>
        <h1 className="mt-4 text-xl font-semibold text-gray-700">Page not found</h1>
        <Link to="/" className="mt-6 text-sm text-brand-500 hover:underline">
          ← Back to home
        </Link>
      </div>
    </PageLayout>
  );
}
