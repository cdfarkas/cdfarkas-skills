import type { InputHTMLAttributes } from 'react';

export interface OldFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  hintId?: string;
}

export function OldField({ hintId, ...props }: OldFieldProps) {
  return <input aria-describedby={hintId} {...props} />;
}
