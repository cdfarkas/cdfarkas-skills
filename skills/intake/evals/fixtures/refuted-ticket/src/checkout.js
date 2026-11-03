import { computeTotal } from './cart.js';

export function onPay(cart) {
  if (cart.items.length === 0) {
    return { error: 'EMPTY_CART' };
  }
  return { total: computeTotal(cart.items) };
}
