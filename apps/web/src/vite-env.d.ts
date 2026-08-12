/// <reference types="vite/client" />
/// <reference types="react/canary" />
/// <reference types="react-dom/canary" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
