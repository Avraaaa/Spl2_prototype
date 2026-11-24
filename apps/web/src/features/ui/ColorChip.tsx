import type { ReactNode } from 'react';
import { contrastText, displayColor } from './colors';
import './colors.css';

export function ColorChip({ color, children }: { color?: string; children: ReactNode }) {
  const background = displayColor(color);
  return <span className="color-chip" style={{ backgroundColor: background, color: contrastText(background) }}>{children}</span>;
}
