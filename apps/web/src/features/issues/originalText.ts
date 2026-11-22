export type OriginalTextState = 'hidden' | 'confirm' | 'revealed';
export type OriginalTextAction = 'show' | 'reveal' | 'cancel' | 'hide';

export const canRequestOriginalText = (state: OriginalTextState) => state === 'confirm';

export function originalTextAction(state: OriginalTextState, action: OriginalTextAction): OriginalTextState {
  if (state === 'hidden' && action === 'show') return 'confirm';
  if (state === 'confirm' && action === 'reveal') return 'revealed';
  if (state === 'confirm' && action === 'cancel') return 'hidden';
  if (state === 'revealed' && action === 'hide') return 'hidden';
  return state;
}
