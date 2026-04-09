'use client';

import { useEffect, useRef, useState } from 'react';
import { DoorPosition } from '@/types';

interface SplatViewerProps {
  sogUrl: string;       // presigned URL (ply / splat / sog)
  mode: 'edit' | 'readonly';
  onDoorPositionSet?: (position: DoorPosition) => void;
}

export default function SplatViewer({ sogUrl, mode, onDoorPositionSet }: SplatViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current || !sogUrl) return;

    let app: any = null;
    let destroyed = false;

    (async () => {
      try {
        const pc = await import('playcanvas');
        if (destroyed) return;

        // ── Canvas ──
        const canvas = document.createElement('canvas');
        canvas.style.width = '100%';
        canvas.style.height = '100%';
        containerRef.current!.appendChild(canvas);

        // ── App ──
        app = new pc.Application(canvas, {
          mouse: new pc.Mouse(canvas),
          touch: new pc.TouchDevice(canvas),
          graphicsDeviceOptions: { antialias: false },
        });
        app.setCanvasFillMode(pc.FILLMODE_FILL_WINDOW);
        app.setCanvasResolution(pc.RESOLUTION_AUTO);

        // ── Camera ──
        const cameraEntity = new pc.Entity('camera');
        cameraEntity.addComponent('camera', {
          clearColor: new pc.Color(0.08, 0.08, 0.08),
          farClip: 10000,
          nearClip: 0.01,
        });
        app.root.addChild(cameraEntity);

        // ── Orbit state ──
        let azimuth = 0;
        let elevation = 15;
        let radius = 3;
        const target = new pc.Vec3(0, 0, 0);

        const syncCamera = () => {
          const az = (azimuth * Math.PI) / 180;
          const el = (elevation * Math.PI) / 180;
          cameraEntity.setPosition(
            target.x + radius * Math.cos(el) * Math.sin(az),
            target.y + radius * Math.sin(el),
            target.z + radius * Math.cos(el) * Math.cos(az),
          );
          cameraEntity.lookAt(target);
        };
        syncCamera();

        // Mouse orbit
        let dragging = false;
        let prevX = 0, prevY = 0;
        canvas.addEventListener('mousedown', (e) => {
          dragging = true;
          prevX = e.clientX;
          prevY = e.clientY;
        });
        const onMouseUp = () => { dragging = false; };
        window.addEventListener('mouseup', onMouseUp);
        canvas.addEventListener('mousemove', (e) => {
          if (!dragging) return;
          azimuth -= (e.clientX - prevX) * 0.35;
          elevation = Math.max(-89, Math.min(89, elevation + (e.clientY - prevY) * 0.35));
          prevX = e.clientX;
          prevY = e.clientY;
          syncCamera();
        });

        // Wheel zoom
        canvas.addEventListener('wheel', (e) => {
          e.preventDefault();
          radius = Math.max(0.1, radius * (1 + e.deltaY * 0.001));
          syncCamera();
        }, { passive: false });

        // Touch orbit (single finger = rotate, pinch = zoom)
        let lastTouchDist = 0;
        let lastTouches: Touch[] = [];
        canvas.addEventListener('touchstart', (e) => {
          lastTouches = Array.from(e.touches);
          if (e.touches.length === 2) {
            const dx = e.touches[0].clientX - e.touches[1].clientX;
            const dy = e.touches[0].clientY - e.touches[1].clientY;
            lastTouchDist = Math.hypot(dx, dy);
          }
        });
        canvas.addEventListener('touchmove', (e) => {
          e.preventDefault();
          if (e.touches.length === 1 && lastTouches.length === 1) {
            azimuth -= (e.touches[0].clientX - lastTouches[0].clientX) * 0.35;
            elevation = Math.max(-89, Math.min(89, elevation + (e.touches[0].clientY - lastTouches[0].clientY) * 0.35));
          } else if (e.touches.length === 2) {
            const dx = e.touches[0].clientX - e.touches[1].clientX;
            const dy = e.touches[0].clientY - e.touches[1].clientY;
            const dist = Math.hypot(dx, dy);
            if (lastTouchDist > 0) {
              radius = Math.max(0.1, radius * (lastTouchDist / dist));
            }
            lastTouchDist = dist;
          }
          lastTouches = Array.from(e.touches);
          syncCamera();
        }, { passive: false });

        // ── Edit mode: click to set door position ──
        if (mode === 'edit' && onDoorPositionSet) {
          canvas.addEventListener('click', (e) => {
            const rect = canvas.getBoundingClientRect();
            const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
            const y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
            onDoorPositionSet({ x, y, z: 0 });
          });
        }

        // ── Load GSplat ──
        const asset = new pc.Asset('splat', 'gsplat', { url: sogUrl });
        app.assets.add(asset);

        asset.on('error', (_: string, err: Error) => {
          if (!destroyed) setError(`파일 로드 실패: ${err?.message ?? '알 수 없는 오류'}`);
          setLoading(false);
        });

        asset.ready(() => {
          if (destroyed) return;

          const splatEntity = new pc.Entity('splat');
          splatEntity.addComponent('gsplat', { asset });
          app.root.addChild(splatEntity);

          // 자동 카메라 거리 조정 (AABB 기준)
          const meshInstance = (splatEntity as any).gsplat?.meshInstance;
          if (meshInstance?.aabb) {
            const aabb = meshInstance.aabb;
            const size = aabb.halfExtents.length();
            radius = size * 2.5;
            target.copy(aabb.center);
            syncCamera();
          }

          setLoading(false);
        });

        app.assets.load(asset);
        app.start();

        // ── ResizeObserver: 컨테이너 크기 변화 시 canvas 리사이즈 ──
        const resizeObserver = new ResizeObserver(() => {
          if (!destroyed && app) {
            app.resizeCanvas();
          }
        });
        resizeObserver.observe(containerRef.current!);

        const origDestroy = app.destroy.bind(app);
        app.destroy = () => {
          resizeObserver.disconnect();
          window.removeEventListener('mouseup', onMouseUp);
          origDestroy();
        };

      } catch (e: any) {
        if (!destroyed) setError(e?.message ?? '뷰어 초기화에 실패했습니다.');
        setLoading(false);
      }
    })();

    return () => {
      destroyed = true;
      if (app) {
        try { app.destroy(); } catch {}
      }
      if (containerRef.current) {
        const c = containerRef.current.querySelector('canvas');
        if (c) containerRef.current.removeChild(c);
      }
    };
  }, [sogUrl]);

  return (
    <div className="relative w-full h-full min-h-[400px] bg-[#141414]">
      <div ref={containerRef} className="w-full h-full" />

      {loading && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#141414]/90 gap-3">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-gray-400">3DGS 파일 로딩 중...</p>
        </div>
      )}

      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#141414]/90">
          <div className="text-center px-6">
            <p className="text-red-400 text-sm mb-1">로드 실패</p>
            <p className="text-gray-500 text-xs">{error}</p>
          </div>
        </div>
      )}

      {!loading && !error && (
        <div className="absolute bottom-3 right-3 bg-black/50 text-gray-400 text-xs px-2 py-1 rounded select-none pointer-events-none">
          드래그: 회전 &nbsp;|&nbsp; 스크롤: 줌
        </div>
      )}
    </div>
  );
}
