import { configureStore } from '@reduxjs/toolkit';
import cart from './cartSlice.js';
import user from './userSlice.js';

export const store = configureStore({ reducer: { cart, user } });
