'use client';

import * as React from 'react';

import { buttonStyles, type ButtonSize, type ButtonVariant } from '@/ui/primitives/buttonStyles';

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = 'secondary', size = 'md', ...props },
  ref
) {
  return (
    <button ref={ref} className={buttonStyles({ variant, size, className })} {...props} />
  );
});
