import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    watch: {
      // Complete local art lives behind this junction and is served separately on 5175.
      // Watching it makes a single link refresh enqueue tens of thousands of HMR events.
      ignored: ["**/public/dev-runtime", "**/public/dev-runtime/**"],
    },
  },
});
