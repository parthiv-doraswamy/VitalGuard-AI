import { useContext } from 'react';
import { SimCtx } from './simInit.ts';
import type { SimValue } from './simInit.ts';
export function useSimulation(): SimValue {
  const v = useContext(SimCtx);
  if (!v) throw new Error('useSimulation outside provider');
  return v;
}
export type { SimValue };
