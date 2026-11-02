import type { ButtonHTMLAttributes } from 'react';
import styles from './Button.module.css';

const sizeClass = {
  sm: styles.sm,
  md: styles.md,
  lg: styles.lg,
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variantSize?: keyof typeof sizeClass;
}

export function Button({ variantSize = 'md', className, type = 'button', ...rest }: ButtonProps) {
  const classes = [styles.button, sizeClass[variantSize], className].filter(Boolean).join(' ');
  return <button {...rest} type={type} className={classes} />;
}
