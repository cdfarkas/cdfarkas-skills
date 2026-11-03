import { CartPage } from './CartPage.jsx';

export default { title: 'Pages/CartPage', component: CartPage };
export const Default = { args: { initialItems: [{ id: 1, name: 'Mug', price: 12, quantity: 2 }] } };
export const Empty = { args: { initialItems: [] } };
