import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import { errorMessage } from '../auth/hooks';
import { ColorChip } from '../ui/ColorChip';
import { COLOR_KEYS, TYPE_COLOR_KEYS } from '../ui/colors';
import { useDisplayColors } from '../ui/useDisplayColors';
import { PageHeader } from '../ui/PageHeader';

type ColorKind = 'status' | 'request_type' | 'label' | 'product';

function ColorEditor({
  label,
  value,
  onSave,
  pending,
}: {
  label: string;
  value: string;
  onSave: (color: string) => void;
  pending: boolean;
}) {
  const [draft, setDraft] = useState(value);
  const valid = /^#[\da-f]{6}$/i.test(draft);

  return (
    <div className="color-editor">
      <span>{label}</span>
      <input
        aria-label={`${label} color`}
        type="color"
        value={valid ? draft : value}
        onChange={event => setDraft(event.target.value)}
        disabled={pending}
      />
      <input
        aria-label={`${label} hex`}
        value={draft}
        pattern="^#[0-9A-Fa-f]{6}$"
        onChange={event => setDraft(event.target.value)}
        maxLength={7}
        disabled={pending}
      />
      <ColorChip color={draft}>{label}</ColorChip>
      <button
        type="button"
        className="btn small"
        disabled={pending || !valid || draft === value}
        onClick={() => onSave(draft)}
      >
        Save
      </button>
    </div>
  );
}

export function ColorsAdminPage() {
  const queryClient = useQueryClient();
  const colors = useDisplayColors();
  const labels = useQuery({
    queryKey: ['admin-labels'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/search/labels/');
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
  const products = useQuery({
    queryKey: ['products'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/products/');
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
  const save = useMutation({
    mutationFn: async ({ kind, key, color }: { kind: ColorKind; key: string; color: string }) => {
      if (kind === 'status' || kind === 'request_type') {
        const { data, error } = await api.PUT('/api/display-colors/{kind}/{key}/', {
          params: { path: { kind, key } },
          body: { color },
        });
        if (!data) throw new Error(errorMessage(error));
      } else if (kind === 'label') {
        const { data, error } = await api.PATCH('/api/search/labels/{id}/', {
          params: { path: { id: Number(key) } },
          body: { color },
        });
        if (!data) throw new Error(errorMessage(error));
      } else {
        const { data, error } = await api.PATCH('/api/admin/products/{product_id}/', {
          params: { path: { product_id: Number(key) } },
          body: { color },
        });
        if (!data) throw new Error(errorMessage(error));
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['display-colors'] });
      queryClient.invalidateQueries({ queryKey: ['admin-labels'] });
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
  });
  const update = (kind: ColorKind, key: string, color: string) =>
    save.mutate({ kind, key, color });
  const content = colors.data;

  return (
    <section className="stack">
      <PageHeader
        title="Colours"
        subtitle="Set the colours used for labels, products, request types and statuses."
      />
      {save.isError && <p className="alert error" role="alert">{save.error.message}</p>}
      {colors.isError && <p className="alert error" role="alert">{colors.error.message}</p>}
      <section className="card stack">
        <h2>Request types</h2>
        {TYPE_COLOR_KEYS.map(key => (
          <ColorEditor
            key={`${key}-${content?.request_types[key] ?? ''}`}
            label={key}
            value={content?.request_types[key] ?? '#64748B'}
            pending={save.isPending}
            onSave={color => update('request_type', key, color)}
          />
        ))}
      </section>
      <section className="card stack">
        <h2>Statuses</h2>
        {COLOR_KEYS.map(key => (
          <ColorEditor
            key={`${key}-${content?.statuses[key] ?? ''}`}
            label={key.replaceAll('_', ' ')}
            value={content?.statuses[key] ?? '#64748B'}
            pending={save.isPending}
            onSave={color => update('status', key, color)}
          />
        ))}
      </section>
      <section className="card stack">
        <h2>Labels</h2>
        {(labels.data ?? []).filter(label => label.is_active).map(label => (
          <ColorEditor
            key={`${label.id}-${content?.labels[String(label.id)] ?? label.color}`}
            label={label.name}
            value={content?.labels[String(label.id)] ?? label.color}
            pending={save.isPending}
            onSave={color => update('label', String(label.id), color)}
          />
        ))}
      </section>
      <section className="card stack">
        <h2>Products</h2>
        {(products.data ?? []).map(product => (
          <ColorEditor
            key={`${product.id}-${content?.products[String(product.id)] ?? product.color ?? ''}`}
            label={product.name}
            value={content?.products[String(product.id)] ?? product.color ?? '#64748B'}
            pending={save.isPending}
            onSave={color => update('product', String(product.id), color)}
          />
        ))}
      </section>
    </section>
  );
}
