// Minimal Vite env typings for this MVP.
// We avoid depending on `vite/client` ambient types to prevent TS errors
// when node_modules are not yet installed in the editor.

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

