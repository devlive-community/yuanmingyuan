import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { viteSingleFile } from 'vite-plugin-singlefile';

// mode=offline：模型以 base64 内联、整体打成单个 HTML（双击离线打开）；
// 其余模式：glb 作为静态资源按需加载。两者只差 @model-loader 的实现。
export default defineConfig(({ mode }) => {
  const offline = mode === 'offline';
  const loader = offline ? './src/data/loader.inline.ts' : './src/data/loader.url.ts';
  return {
    base: './',
    plugins: [react(), ...(offline ? [viteSingleFile()] : [])],
    assetsInclude: ['**/*.glb', '**/*.hdr'],
    resolve: {
      alias: { '@model-loader': fileURLToPath(new URL(loader, import.meta.url)) },
    },
    build: {
      outDir: offline ? 'dist-offline' : 'dist',
      chunkSizeWarningLimit: 8000,
    },
  };
});
