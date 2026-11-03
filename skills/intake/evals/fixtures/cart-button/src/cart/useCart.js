import { useState } from 'react';

export function useCart(initialItems = []) {
  const [items, setItems] = useState(initialItems);
  const removeItem = (id) => setItems((xs) => xs.filter((x) => x.id !== id));
  const clear = () => setItems([]);
  const total = items.reduce((s, x) => s + x.price * x.quantity, 0);
  return { items, removeItem, clear, total };
}
