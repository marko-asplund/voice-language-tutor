import { defineConfig } from 'vite';
import solid from 'vite-plugin-solid';
export default defineConfig({plugins:[solid()],build:{outDir:'../src/voice_tutor/web/static',emptyOutDir:true}});
