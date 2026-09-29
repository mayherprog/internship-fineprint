import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The app shell's Content-Security-Policy. Unlike the static page (which is
// fully inline and needs 'unsafe-inline'), the app loads only its own bundled
// script and stylesheet and fetches its own data.json — so everything is
// 'self', plus the data: URI for the select caret in styles.css. Injected at
// build time only: the dev server needs its inline react-refresh preamble and
// websocket, and must not be governed by the production policy.
const CSP =
  "default-src 'none'; script-src 'self'; style-src 'self'; " +
  "connect-src 'self'; img-src 'self' data:; base-uri 'none'; " +
  "form-action 'none'";

// Deployed under /app/ on the project Pages site.
export default defineConfig({
  plugins: [
    react(),
    {
      name: "inject-csp-meta",
      apply: "build",
      transformIndexHtml: (html: string) => ({
        html,
        tags: [{
          tag: "meta",
          attrs: { "http-equiv": "Content-Security-Policy", content: CSP },
          injectTo: "head-prepend" as const,
        }],
      }),
    },
  ],
  base: "/internship-fineprint/app/",
  // The build date for the About stamp. The Pages workflow rebuilds on
  // every deploy, so this stays honest; the data-checked half of the stamp
  // is derived from the records at runtime.
  define: {
    __BUILD_DATE__: JSON.stringify(new Date().toISOString().slice(0, 10)),
  },
});
