import { useDispatch, useSelector } from 'react-redux';
import { remove } from '../store/cartSlice.js';

export function CartPage() {
  const items = useSelector((s) => s.cart.items);
  const dispatch = useDispatch();
  return <ul>{items.map((x) => <li key={x.id} onClick={() => dispatch(remove(x.id))}>{x.name}</li>)}</ul>;
}
