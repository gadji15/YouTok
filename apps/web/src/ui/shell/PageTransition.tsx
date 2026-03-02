'use client';

import * as React from 'react';
import { usePathname } from 'next/navigation';

export function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div
      key={pathname}
      className="animate-[youtok-page-enter_220ms_cubic-bezier(0.2,0,0,1)] motion-reduce:animate-none"
    >
      {children}
    </div>
  );
}
