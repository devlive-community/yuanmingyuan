import { LEGEND, partZh } from '../labels';
import type { RenderMode } from '../viewer/SceneViewer';

export function Legend({ mode }: { mode: RenderMode }) {
  return (
    <>
      <div className="legend">
        {mode === 'realistic' ? (
          <span>
            设色依史料：粉红色灰墙、孔雀绿琉璃瓦、黄琉璃脊、汉白玉、铜窗铜首（海晏堂）；灰筒瓦、朱红柱（中式殿宇）
            · 瓦垄石缝等纹理为程序生成示意
          </span>
        ) : (
          <>
            {LEGEND.map(([part, color]) => (
              <span key={part}>
                <i style={{ background: color }} />
                {partZh(part)}
              </span>
            ))}
            <span className="muted"> · 示意色，用于区分构件</span>
          </>
        )}
      </div>
      <div className="hint">拖动旋转 · Shift+拖动或右键平移 · 滚轮缩放 · 方向键移动</div>
    </>
  );
}
