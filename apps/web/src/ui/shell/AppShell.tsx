'use client';

import { useEffect, useState } from 'react';

import { AppSidebar } from '@/ui/shell/AppSidebar';
import { SidebarContent } from '@/ui/shell/SidebarContent';
import { Topbar } from '@/ui/shell/Topbar';

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setMobileNavOpen(false);
      }
    }

    if (mobileNavOpen) {
      window.addEventListener('keydown', onKeyDown);
      return () => window.removeEventListener('keydown', onKeyDown);
    }
  }, [mobileNavOpen]);

  return (
    <div className="min-h-dvh bg-[var(--page-bg)]">
      <div className="mx-auto flex min-h-dvh max-w-screen-2xl">
        <AppSidebar />

        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar onOpenMobileNav={() => setMobileNavOpen(true)} />

          <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
            <div className="mx-auto w-full max-w-6xl">{children}</div>
          </main>
        </div>
      </div>

      <div
        className={
          'fixed inset-0 z-50 lg:hidden ' +
          (mobileNavOpen ? 'pointer-events-auto' : 'pointer-events-none')
        }
        aria-hidden={!mobileNavOpen}
      >
        <div
          className={
            'absolute inset-0 bg-black/30 backdrop-blur-sm transition-opacity motion-reduce:transition-none ' +
            (mobileNavOpen ? 'opacity-100' : 'opacity-0')
          }
          onClick={() => setMobileNavOpen(false)}
        />

        <div
          className={
            'absolute left-0 top-0 h-full w-[min(20rem,85vw)] border-r border-[color:var(--border)] bg-[var(--surface)] shadow-xl transition-transform motion-reduce:transition-none ' +
            (mobileNavOpen ? 'translate-x-0' : '-translate-x-full')
          }
        >
          <SidebarContent onNavigate={() => setMobileNavOpen(false)} />
        </div>
      </div>
    </div>
  );
}
