import { createSlice } from '@reduxjs/toolkit';

const cartSlice = createSlice({
  name: 'cart',
  initialState: { items: [] },
  reducers: {
    add: (s, a) => { s.items.push(a.payload); },
    remove: (s, a) => { s.items = s.items.filter((x) => x.id !== a.payload); },
  },
});
export const { add, remove } = cartSlice.actions;
export default cartSlice.reducer;
