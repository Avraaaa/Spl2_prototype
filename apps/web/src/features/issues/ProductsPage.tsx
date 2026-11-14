import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import { errorMessage } from '../auth/hooks';

export function ProductsPage() {
  const qc = useQueryClient();
  const [name, setName] = useState('');
  const [moduleName, setModuleName] = useState('');
  const [productId, setProductId] = useState<number | ''>('');
  const products = useQuery({
    queryKey: ['products'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/products/');
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
  const addProduct = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST('/api/admin/products/', { body: { name } });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
    onSuccess: () => { setName(''); qc.invalidateQueries({ queryKey: ['products'] }); },
  });
  const addModule = useMutation({
    mutationFn: async () => {
      if (!productId) throw new Error('Select a product.');
      const { data, error } = await api.POST('/api/admin/products/{product_id}/modules/', { params: { path: { product_id: productId } }, body: { name: moduleName } });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
    onSuccess: () => { setModuleName(''); qc.invalidateQueries({ queryKey: ['products'] }); },
  });
  return <section className="stack"><div className="page-head"><h1>Products &amp; modules</h1></div>
    <div className="two-col"><form className="card form-grid" onSubmit={(e: FormEvent) => { e.preventDefault(); addProduct.mutate(); }}><h3>Add product</h3><label>Name<input maxLength={160} required value={name} onChange={e => setName(e.target.value)} /></label>{addProduct.isError && <p className="alert error">{addProduct.error.message}</p>}<button className="btn primary" disabled={addProduct.isPending}>Add product</button></form>
    <form className="card form-grid" onSubmit={(e: FormEvent) => { e.preventDefault(); addModule.mutate(); }}><h3>Add module</h3><label>Product<select required value={productId} onChange={e => setProductId(e.target.value ? Number(e.target.value) : '')}><option value="">Select…</option>{(products.data ?? []).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label><label>Name<input maxLength={160} required value={moduleName} onChange={e => setModuleName(e.target.value)} /></label>{addModule.isError && <p className="alert error">{addModule.error.message}</p>}<button className="btn primary" disabled={addModule.isPending}>Add module</button></form></div>
    {products.isError && <p className="alert error">{products.error.message}</p>}
    <div className="card"><h3>Register</h3><ul>{(products.data ?? []).map(p => <li key={p.id}><strong>{p.name}</strong>{p.modules.length > 0 && ` — ${p.modules.map(m => m.name).join(', ')}`}</li>)}</ul></div>
  </section>;
}
