import { createSlice } from '@reduxjs/toolkit';

const userSlice = createSlice({ name: 'user', initialState: { name: null }, reducers: { setName: (s, a) => { s.name = a.payload; } } });
export const { setName } = userSlice.actions;
export default userSlice.reducer;
