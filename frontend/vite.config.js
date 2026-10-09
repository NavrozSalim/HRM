import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  envDir: "..",
  plugins: [react(), tailwindcss()],
  server: { port: 5173, host: "127.0.0.1" },
});
