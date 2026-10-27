// 把离线单文件构建产物复制到仓库根目录「圆明园全景-打开这个.html」。
import { copyFileSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const src = fileURLToPath(new URL('../dist-offline/index.html', import.meta.url));
const dst = fileURLToPath(new URL('../../../圆明园全景-打开这个.html', import.meta.url));
copyFileSync(src, dst);
console.log(`[offline] ${dst}（${statSync(dst).size.toLocaleString()} 字节）`);
