import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'
import prettier from 'eslint-config-prettier'
import boundaries from 'eslint-plugin-boundaries'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
      prettier,
    ],
    languageOptions: {
      globals: globals.browser,
    },
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    plugins: {
      boundaries,
    },
    settings: {
      'boundaries/elements': [
        { type: 'app', pattern: 'src/app/**' },
        { type: 'pages', pattern: 'src/pages/**' },
        { type: 'widgets', pattern: 'src/widgets/**' },
        { type: 'features', pattern: 'src/features/**' },
        { type: 'entities', pattern: 'src/entities/**' },
        { type: 'shared', pattern: 'src/shared/**' },
      ],
      'boundaries/ignore': ['src/test/**'],
    },
    rules: {
      // Using v6 rule name "boundaries/dependencies"
      'boundaries/dependencies': [
        'error',
        {
          default: 'disallow',
          rules: [
            // app can import from everything
            { from: [['app']], allow: [['pages'], ['widgets'], ['features'], ['entities'], ['shared']] },
            // pages can import from below
            { from: [['pages']], allow: [['widgets'], ['features'], ['entities'], ['shared']] },
            // widgets can import from below
            { from: [['widgets']], allow: [['features'], ['entities'], ['shared']] },
            // features can import from below
            { from: [['features']], allow: [['entities'], ['shared']] },
            // entities can import from shared only
            { from: [['entities']], allow: [['shared']] },
            // shared cannot import from any FSD layer above it
            { from: [['shared']], allow: [] },
          ],
        },
      ],
    },
  },
])
