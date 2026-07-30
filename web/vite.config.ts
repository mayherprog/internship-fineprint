import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Deployed under /app/ on the project Pages site.
export default defineConfig({
  plugins: [react()],
  base: "/internship-fineprint/app/",
});
