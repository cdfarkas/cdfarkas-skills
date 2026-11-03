# SHOP-142 Checkout crashes on an empty cart

Since release 3.2, clicking "Pay" with an empty cart throws
`TypeError: Cannot read properties of undefined (reading 'price')` in `computeTotal`.
Every customer with an empty cart is affected.

Fix: make `computeTotal` in `src/cart.js` handle an empty cart.
