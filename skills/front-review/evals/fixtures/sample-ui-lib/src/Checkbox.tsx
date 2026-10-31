import { useLayoutEffect, useRef, type InputHTMLAttributes, type ReactNode } from 'react';
import styles from './Checkbox.module.css';

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'children'> {
  checked: boolean;
  indeterminate?: boolean;
  onChange: NonNullable<InputHTMLAttributes<HTMLInputElement>['onChange']>;
  children: ReactNode;
}

export function Checkbox({ indeterminate = false, className, children, ...rest }: CheckboxProps) {
  const ref = useRef<HTMLInputElement>(null);

  useLayoutEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate;
  });

  return (
    <label className={styles.root}>
      <input
        {...rest}
        ref={ref}
        type="checkbox"
        className={[styles.box, className].filter(Boolean).join(' ')}
      />
      {children}
    </label>
  );
}
