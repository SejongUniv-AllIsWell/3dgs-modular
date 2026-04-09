# Frontend — 3DGS Digital Twin Viewer

Next.js 14 App Router + TypeScript + Tailwind CSS 기반 프론트엔드.

## 디렉토리 구조

```
src/
├── app/                    # Next.js App Router 페이지
│   ├── viewer/             # 3DGS 뷰어 페이지 (ply 로드 & 편집)
│   ├── upload/             # 영상/ply 업로드 → 학습 요청
│   ├── buildings/          # 건물 선택 (카카오맵)
│   ├── door-select/        # 문 선택 페이지
│   ├── explore/            # 탐색 페이지
│   ├── dashboard/          # 대시보드
│   ├── admin/              # 관리자
│   └── login/              # 구글 로그인
├── components/
│   └── viewer/             # 3DGS 뷰어 컴포넌트 (아래 상세)
├── lib/                    # 유틸리티, API 클라이언트
└── types/                  # 공유 TypeScript 타입
```

## 뷰어 아키텍처 (`components/viewer/`)

### 핵심 컴포넌트

| 파일 | 역할 |
|------|------|
| `SplatViewerCore.tsx` | PlayCanvas 2.x 앱 초기화, GSplat 로드, 카메라(fly/orbit), `SplatViewerCoreRef` 노출 |
| `SplatViewer.tsx` | 편집 모드 UI — 선택, 변환, 문 애니메이션, 경첩 편집 통합 |
| `RefineViewer.tsx` | 정제(refine) 전용 뷰어 |

### `SplatViewerCoreRef` (imperative handle)

모든 도구 훅이 이 ref를 통해 PlayCanvas에 접근한다:

- `getApp()` — PlayCanvas `Application`
- `getCamera()` — 카메라 Entity
- `getCanvas()` — `<canvas>` DOM 요소
- `getPC()` — PlayCanvas 모듈 (`pc` namespace)
- `getSplatData()` — 로드된 splat의 CPU/GPU 데이터
- `float2Half(v)` / `half2Float(h)` — IEEE 754 half-float 변환
- `onUpdate(cb)` — 매 프레임 콜백 등록, 해제함수 반환
- `drawLine(a, b, color, depthTest?)` — 디버그/UI 라인 렌더링

### `SplatData` 구조

```typescript
{
  numSplats: number;
  posX / posY / posZ: Float32Array;    // CPU 위치 배열
  colorTexture: Texture;               // 색상 GPU 텍스처
  origColorData: Uint16Array | null;   // 원본 색상 (half-float RGBA)
  splatEntity: Entity;                 // PlayCanvas Entity
  transformATexture: Texture;          // GPU: [posX(f32), posY(f32), posZ(f32), rotXY(packed half)]
  transformBTexture: Texture;          // GPU: [scaleX(half), scaleY(half), scaleZ(half), rotZ(half)]
  resource: GSplatResource;            // centers, sorter 접근
  gsplatData: GSplatData;              // rot_0(w), rot_1(x), rot_2(y), rot_3(z) 등 속성
}
```

### 도구 훅 (`tools/`)

모든 훅은 `useXxx(coreRef)` 패턴을 따른다.

| 파일 | 기능 |
|------|------|
| `useGaussianSelector.tsx` | 브러쉬/BBox로 가우시안 선택, 하이라이트, undo, 반전, `.idx` 저장/불러오기 |
| `useTransformTool.ts` | 선택된 가우시안에 이동(축 화살표)/회전(축 링) 기즈모 적용 |
| `useDoorAnimation.ts` | 문 열기/닫기 애니메이션 (위치+쿼터니언 회전, easing) |
| `usePivotEditor.ts` | 경첩(피벗) 축 시각 편집 — 끝점 드래그, 평행이동, 회전 |
| `useRefineTool.tsx` | 가우시안 정제 도구 |

### 공유 유틸리티 (`tools/`)

| 파일 | 내용 |
|------|------|
| `quatUtils.ts` | 쿼터니언 연산: `axisAngleToQuat`, `quatMul`, `quatNormalize`, `rotatePoint` |
| `gpuSync.ts` | `syncGPU()` — transformA/B 텍스처 + sorter 동기화, `snapshotSplatData()` — 위치+쿼터니언 백업 |

## GPU 동기화 패턴

가우시안 위치/회전을 변경할 때 반드시 3단계를 거쳐야 한다:

1. **CPU 데이터 수정**: `splatData.posX/Y/Z` + `gsplatData.rot_0~3`
2. **GPU 텍스처 업데이트**: `transformA.lock()` → f32 위치 + packed half rotXY 기록 → `unlock()`, `transformB.lock()` → rotZ 기록 → `unlock()`
3. **Sorter 갱신**: `sorter.centers[idx*3+0..2]` 업데이트 → `setMapping(null)` → `lastCameraPosition.set(Infinity, ...)`

이 패턴은 `gpuSync.ts`의 `syncGPU()` 함수에 캡슐화되어 있다.

## 쿼터니언 규칙

- PlayCanvas GSplat 쿼터니언: `rot_0=w, rot_1=x, rot_2=y, rot_3=z`
- 정규화 후 `w >= 0` 보장 (음수면 전체 부호 반전)
- 회전 적용: `rotation_quat × original_quat` (왼쪽 곱)

## 작업 규칙

- 도커 빌드/재시작은 사용자가 직접 수행. 코드 수정만 할 것.
- PlayCanvas는 dynamic import로 로드됨 — `window.pc` 대신 `coreRef.current?.getPC()` 사용.
- 캔버스 크기는 `FILLMODE_NONE` + ResizeObserver로 컨테이너에 맞춤 (navbar 침범 방지).
