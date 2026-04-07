텍스트 프롬프트로 지정한 물체의 가우시안 인덱스 배열을 추출하는 범용 모듈이다.
basemap, module 구분 없이 동일하게 재사용된다.
선택된 입자들은 노란색 형광빛으로 변해서 선택되었음을 유저가 알 수 있게 한다.

입력:
- ply파일 경로
- 학습에 사용된 이미지 경로
- COLMAP sparse 경로 (카메라 내/외부 파라미터 획득용, 역투영에 필요)
- 텍스트 프롬프트 (추출할 물체 지정, 예: "door")

출력: 해당 물체의 가우시안 인덱스 배열 (N,)

사용 시점:
- basemap: 이 모듈을 이용해 각 문의 가우시안 인덱스가 이미 추출되어 저장된 상태라고 가정
- module 추가 시: 사용자 업로드 및 3DGS 학습 완료 후 파이프라인에서 자동 실행
- 추출된 인덱스는 door_alignment/의 입력으로 사용됨


선택 방법
- 수동 모드 (SplatViewer.tsx에 웹 구현 완료): 두 가지 도구를 이용해서 문의 가우시안 입자들을 수동으로 추출해낸다.
    - 바운딩박스 도구: 3D 와이어프레임 박스의 면을 좌클릭+드래그하여 크기 조절, 박스 내부의 가우시안 입자 전부 선택
    - 페인팅 도구: 보는 각도를 바꿔가며 좌클릭+드래그로 브러쉬로 칠하여 가우시안 입자들을 선택
        - 합집합 모드: 현재 선택 ∪ 새로 칠한 영역 (새로 칠한 영역 추가)
        - 차집합 모드: 현재 선택 - 새로 칠한 영역 (원래 칠해진 영역에서 새롭게 칠한 영역의 차집합만을 남김)
        - 반전: 현재 선택의 여집합 (선택 ↔ 비선택 토글)
        - 브러쉬 크기 조절 가능, 커서에 브러쉬 크기 미리보기 표시
    - 공통: Undo/반전/Reset 지원, 선택된 입자는 노란색 형광빛 하이라이트
    - 선택 결과: onSelectionDone 콜백으로 부모 컴포넌트에 인덱스 배열 전달 (door_alignment 입력용)
- 자동 모드 (auto.py): SAM3로 이미지에서 텍스트 프롬프트에 해당하는 물체를 탐지하고, 탐지된 2D mask를 학습된 가우시안 공간에 역투영하여 해당 물체의 가우시안 인덱스를 자동으로 추출한다.

    2D segmentation 파이프라인:
    - SAM3 (github.com/facebookresearch/sam3) 사용
    - 텍스트 프롬프트로 직접 탐지 + 정밀 mask 생성 (Grounding DINO 별도 불필요)
    - SAM3 video mode: 인접 프레임에 mask 전파하여 뷰 간 일관성 확보
    - 848M 파라미터, 4M 이상 개념 학습, open-vocabulary 지원

    역투영 방법 (세 가지 중 선택):

    방법 A - Alpha × Transmittance 역투영 (구현 난이도: 낮음)
    - 각 픽셀의 가우시안 기여도 weight = alpha_k * T_k 로 계산
      (T_k = 가우시안 k 앞에 있는 모든 가우시안의 (1-alpha) 곱 = transmittance)
    - door mask 안 픽셀에 기여한 가우시안들에 weight만큼 vote 누적
    - 전체 뷰에서 normalized score가 threshold 이상인 가우시안을 door로 판정
    - 단순 alpha 가중치(alpha만 사용)는 occlusion을 무시하므로 틀림. 반드시 alpha*T 사용
    - 단점: 경계 가우시안에서 bleeding 발생, threshold 튜닝 필요
    - 참고: github.com/JojiJoseph/3dgs-gradient-backprojection (SIGGRAPH Asia 2025)

    방법 B - LBG Max-Contributor (구현 난이도: 중간) ← 추천
    - 각 픽셀에서 alpha*T가 가장 높은 가우시안 하나(max-contributor)에만 1표
    - soft voting 대신 hard assignment → 경계 bleeding 없음
    - 뷰 간 일관성은 CLIP/DINO feature 코사인 유사도로 검증
    - threshold 튜닝 불필요
    - 단점: 유리문 등 반투명 문에서 불안정
    - 참고: Lifting by Gaussians (WACV 2025), arxiv.org/abs/2502.00173

    방법 C - B3-Seg Bayesian (구현 난이도: 높음)
    - 각 가우시안의 "문일 확률"을 Beta 분포 Beta(α_k, β_k)로 모델링 (초기값 α=β=1)
    - 뷰마다 door mask 안이면 α_k += alpha*T, 아니면 β_k += alpha*T 로 업데이트
    - 최종 확률 = α_k / (α_k + β_k)
    - EIG(Expected Information Gain)로 정보량이 높은 뷰만 선택하므로 전체 이미지 불필요
    - 카메라 포즈 없이도 동작
    - 단점: 구현 복잡, 공개 코드 미확인
    - 참고: B3-Seg (2026), arxiv.org/abs/2602.17134

    공통 후처리:
    - opacity < 0.1 가우시안은 floater로 제외
    - KNN(3D 위치 기준)으로 이웃 가우시안 투표값 스무딩하여 경계 노이즈 제거
    - 전체 뷰 중 30% 이상에서 투표받은 가우시안만 채택 권장

