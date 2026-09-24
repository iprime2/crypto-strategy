/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_OEMS_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
