// 在线模式：glb 作为静态资源，切换模型时按需请求。
const urls = import.meta.glob<string>('../generated/models/*.glb', { query: '?url', import: 'default' });

export async function loadModelBuffer(id: string): Promise<ArrayBuffer> {
  const get = urls[`../generated/models/${id}.glb`];
  if (!get) throw new Error(`缺少模型文件 ${id}.glb（先运行 npm run data）`);
  const res = await fetch(await get());
  if (!res.ok) throw new Error(`模型请求失败 ${res.status}: ${id}`);
  return res.arrayBuffer();
}

const assetUrls = import.meta.glob<string>('../generated/textures/*', { query: '?url', import: 'default' });

/** 材质纹理 / HDR 天空的 URL（在线模式为静态资源路径）。 */
export async function loadAssetUrl(file: string): Promise<string> {
  const get = assetUrls[`../generated/textures/${file}`];
  if (!get) throw new Error(`缺少纹理 ${file}（先运行 npm run data）`);
  return get();
}
