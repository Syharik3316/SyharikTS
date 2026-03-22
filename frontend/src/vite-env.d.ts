// Minimal Vite env typings for this MVP.
// We avoid depending on `vite/client` ambient types to prevent TS errors
// when node_modules are not yet installed in the editor.

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_RECAPTCHA_SITE_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "react-google-recaptcha" {
  import * as React from "react";
  export interface ReCAPTCHAProps {
    sitekey: string;
    onChange?: (token: string | null) => void;
    onExpired?: () => void;
    theme?: "dark" | "light";
    size?: "compact" | "normal" | "invisible";
  }
  export default class ReCAPTCHA extends React.Component<ReCAPTCHAProps> {
    reset(): void;
    getValue(): string | null;
    execute(): void;
    executeAsync(): Promise<string | null>;
  }
}

