import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies API calls to the FastAPI backend on :8000 so the app
// behaves the same as production (same-origin from the browser's point of
// view), just with Vite's fast refresh on top. Production instead builds to
// dist/ and FastAPI serves that directory directly — no proxy, no CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/units": "http://localhost:8000",
      "/sessions": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
  build: {
    outDir: "dist",
  },
});
