import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite: geliştirme sunucusu (5173) ve üretim derlemesi.
export default defineConfig({
  plugins: [react()],
});
