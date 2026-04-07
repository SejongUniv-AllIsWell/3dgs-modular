'use client';

import { useRef } from 'react';
import SplatViewerCore, { SplatViewerCoreRef } from './SplatViewerCore';
import { useGaussianSelector } from './tools/useGaussianSelector';
import { DoorPosition } from '@/types';

interface SplatViewerProps {
  sogUrl: string;
  mode: 'edit' | 'readonly';
  onDoorPositionSet?: (position: DoorPosition) => void;
  onSelectionDone?: (indices: number[]) => void;
}

export default function SplatViewer({ sogUrl, mode, onSelectionDone }: SplatViewerProps) {
  const coreRef = useRef<SplatViewerCoreRef>(null);
  const selector = useGaussianSelector(coreRef, { onSelectionDone });

  return (
    <SplatViewerCore ref={coreRef} sogUrl={sogUrl} onSplatLoaded={selector.onSplatLoaded}>
      {mode === 'edit' && selector.ui}
    </SplatViewerCore>
  );
}
