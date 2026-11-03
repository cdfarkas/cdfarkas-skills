import { Button } from '../components/Button/Button.jsx';
import { useCart } from '../cart/useCart.js';

export function CartPage({ initialItems }) {
  const { items, removeItem, total } = useCart(initialItems);
  if (items.length === 0) return <p>Votre panier est vide.</p>;
  return (
    <section>
      <h1>Panier</h1>
      <ul>
        {items.map((x) => (
          <li key={x.id}>
            {x.name} x {x.quantity}
            <Button variant="secondary" onClick={() => removeItem(x.id)}>Retirer</Button>
          </li>
        ))}
      </ul>
      <p>Total : {total} EUR</p>
      <Button>Payer</Button>
    </section>
  );
}
