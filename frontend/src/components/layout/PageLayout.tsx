/** Root layout — header + main content. */
import { type ReactNode } from 'react';
import { Header } from './Header';

interface PageLayoutProps {
  children: ReactNode;
}

export function PageLayout({ children }: PageLayoutProps) {
  return (
    <div className="flex min-h-screen flex-col bg-surface-50 font-sans antialiased">
      <Header />
      <main className="flex-1">{children}</main>
    </div>
  );
}
