import type { ButtonHTMLAttributes, ReactNode } from 'react';
import styles from './Switch.module.css';

type NativeButton = Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children' | 'onChange' | 'onClick' | 'role' | 'type'>;

export interface SwitchProps extends NativeButton {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  children: ReactNode;
}

export function Switch({ checked, onCheckedChange, children, className, ...rest }: SwitchProps) {
  return (
    <button
      {...rest}
      type="button"
      role="switch"
      aria-checked={checked}
      className={[styles.switch, className].filter(Boolean).join(' ')}
      onClick={() => onCheckedChange(!checked)}
    >
      <span className={styles.track} aria-hidden="true">
        <span className={styles.thumb} />
      </span>
      <span>{children}</span>
    </button>
  );
}
