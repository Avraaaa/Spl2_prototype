export const FALLBACK_COLOR = '#64748B';
export const COLOR_KEYS = ['DRAFT', 'SUBMITTED', 'ACCEPTED', 'REJECTED', 'PENDING', 'IN_PROGRESS', 'AWAITING_VERIFICATION', 'VERIFIED', 'CLOSED'] as const;
export const TYPE_COLOR_KEYS = ['BUG', 'CHANGE', 'FEATURE', 'SUPPORT'] as const;

export function displayColor(value: string | undefined): string {
  return value && /^#[\da-f]{6}$/i.test(value) ? value : FALLBACK_COLOR;
}

export function contrastText(value: string | undefined): string {
  const color = displayColor(value).slice(1);
  const linear = (index: number) => {
    const channel = parseInt(color.slice(index, index + 2), 16) / 255;
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2;
  };
  const luminance = linear(0) * 0.2126 + linear(2) * 0.7152 + linear(4) * 0.0722;
  return luminance > 0.179 ? '#000000' : '#FFFFFF';
}
