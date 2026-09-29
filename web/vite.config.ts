import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Deployed under /app/ on the project Pages site.
export default defineConfig({
  plugins: [react()],
  base: "/internship-fineprint/app/",
  // The build date for the About stamp. The Pages workflow rebuilds on
  // every deploy, so this stays honest; the data-checked half of the stamp
  // is derived from the records at runtime.
  define: {
    __BUILD_DATE__: JSON.stringify(new Date().toISOString().slice(0, 10)),
  },
});
