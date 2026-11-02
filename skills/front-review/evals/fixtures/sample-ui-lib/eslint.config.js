import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';

export default tseslint.config({
  files: ['src/**/*.{ts,tsx}'],
  extends: [tseslint.configs.recommended],
  plugins: { 'react-hooks': reactHooks },
  rules: { 'react-hooks/rules-of-hooks': 'error' },
});
