import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import { errorMessage } from '../auth/hooks';

export function useDisplayColors() {
  return useQuery({
    queryKey: ['display-colors'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/display-colors/');
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
    staleTime: 60_000,
  });
}
