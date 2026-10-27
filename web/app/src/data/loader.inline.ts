// 离线模式：glb 以 base64 data URL 内联进单文件 HTML，file:// 下也能读取。
const inlined = import.meta.glob<string>('../generated/models/*.glb', { query: '?inline', import: 'default' });

export async function loadModelBuffer(id: string): Promise<ArrayBuffer> {
  const get = inlined[`../generated/models/${id}.glb`];
  if (!get) throw new Error(`缺少模型 ${id}`);
  const res = await fetch(await get());
  return res.arrayBuffer();
}

const assetInline = import.meta.glob<string>('../generated/textures/*', { query: '?inline', import: 'default' });

/** 材质纹理 / HDR 天空（离线模式为内联 data URL）。 */
export async function loadAssetUrl(file: string): Promise<string> {
  const get = assetInline[`../generated/textures/${file}`];
  if (!get) throw new Error(`缺少纹理 ${file}`);
  return get();
}
