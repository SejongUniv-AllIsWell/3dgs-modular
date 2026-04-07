3DGS 학습 후 방 경계면을 기준으로 가우시안 입자들을 정제하는 모듈이다.
두 공간을 이어붙였을 때 floater가 인접 공간에 영향을 주지 않도록, 방 외부의 가우시안을 제거하고 경계면을 마감한다.

파이프라인 (평면 1개 단위로 반복):
    경계면 설정 (웹 프론트엔드) → clip.py → flat_opaque.py
    사용자는 평면 하나를 설정하고 "정렬" → 반복하여 방의 모든 벽을 처리

---

경계면 설정 (웹 프론트엔드 RefineViewer / useRefineTool)
- 3가지 모드: plane(평면), brush(브러쉬), bbox(바운딩박스)
- plane 모드:
    - 평면 추가/삭제, T키로 법선방향 이동 기즈모, R키로 3축 회전 기즈모
    - 평면이 공간을 둘로 나누고, 가우시안이 적은 쪽을 빨간색으로 표시
    - "정렬" 버튼: 해당 평면에 대해 clip → align 실행
- brush/bbox 모드:
    - outlier 가우시안을 수동으로 선택(빨간색)하여 삭제
    - 삭제는 누적 가능 (여러 번 반복)
- 출력: 평면 (normal, d), 삭제할 가우시안 인덱스

---

clip.py — 유틸리티 (바깥 판정)
- determine_outside(): 평면 기준 가우시안이 적은 쪽을 '바깥'으로 판정
- clip_single_plane(): 필요 시 바깥 가우시안 삭제 (현재 메인 파이프라인에서는 미사용)
- 삭제는 프론트엔드 브러쉬/BBox 도구가 담당

---

flat_opaque.py — 단일 평면 기반 벽면 정렬 (핵심 모듈)
- 바깥(가우시안이 적은 쪽) 가우시안 전부를 평면에 투영하여 정렬:
    1. 위치 스냅: signed_dist만큼 평면으로 이동 (x_new = x - signed_dist * normal)
    2. 회전 정렬: 가우시안의 가장 정렬된 축이 정확히 벽 법선을 향하도록 쿼터니언 보정
    3. 공분산 flatten: 법선 방향 축의 scale → log(epsilon) (납작하게)
    4. SH 계수 회전: 보정 회전과 동일한 회전을 degree 1 SH에 적용
       - 3DGS convention: C1 * (-y*sh1 + z*sh2 - x*sh3)
       - T행렬로 [sh1,sh2,sh3] ↔ 방향벡터 변환 후 R 적용
       - TODO: degree 2, 3 (Wigner D-matrix)
    5. opacity 증가: 벽이 투명하게 보이지 않도록 sigmoid(raw) → target_opacity
- 예외: 창문(window) 가우시안은 처리하지 않고 유지
    - TODO: SAM3(select_gaussians/auto.py) "window" 프롬프트로 인덱스 생성
- 입력: ply 경로, 단일 평면, thickness, window 인덱스(선택)
- 출력: 벽면 정렬된 ply

---

사용자 워크플로우:
1. 브러쉬/BBox로 outlier 가우시안 수동 삭제
2. 평면 1개 설정 → "정렬" (clip + align)
3. 2번을 벽 수만큼 반복 (직육면체 방이면 6번)
4. 결과 저장

전체 입출력:
- 입력: 3DGS 학습 결과 ply
- 출력: 경계면이 정제된 ply (outlier 제거 + 벽면 마감)
- 결과는 스토리지 서버에 저장 (사용자가 나중에 돌아와도 유지)
