import { useSelector } from 'react-redux';

export function Header() {
  const count = useSelector((s) => s.cart.items.length);
  return <header>Panier ({count})</header>;
}
