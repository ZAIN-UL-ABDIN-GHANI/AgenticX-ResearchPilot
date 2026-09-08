'use client';

import React from 'react';
import { useParams } from 'next/navigation';
import { useSelector } from 'react-redux';
import { RootState } from '@/store';
import { ResearchWorkspace } from '@/components/ResearchWorkspace';
import { ResearchResults } from '@/components/ResearchResults';

export default function ResearchDetailPage() {
  const params = useParams<{ id: string }>();
  const researchId = params.id;
  const status = useSelector((state: RootState) => state.research.status);

  const isFinished = status === 'completed' || status === 'failed';

  return (
    <main>
      {isFinished ? (
        <ResearchResults researchId={researchId} />
      ) : (
        <ResearchWorkspace researchId={researchId} />
      )}
    </main>
  );
}
