import { statusLabel } from './labels';
import { ColorChip } from './ColorChip';
import { useDisplayColors } from './useDisplayColors';

export function StatusBadge({ status = '' }: { status?: string }) {
  const colors = useDisplayColors();
  return <ColorChip color={colors.data?.statuses[status]}>{statusLabel(status)}</ColorChip>;
}
