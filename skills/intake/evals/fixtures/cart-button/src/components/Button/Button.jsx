export function Button({ variant = 'primary', children, ...props }) {
  return <button className={`btn btn--${variant}`} {...props}>{children}</button>;
}
// variants: 'primary' | 'secondary' | 'danger'
