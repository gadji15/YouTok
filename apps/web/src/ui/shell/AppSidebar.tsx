'use client';

import { SidebarContent } from '@/ui/shell/SidebarContent';

export function AppSidebar() {
  return (
    <aside className="hidden w-64 shrink-0 border-r border-[color:var(--border)] bg-[var(--surface)] lg:block">
      <SidebarContent />
    </aside>
  );
}
