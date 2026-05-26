import type { ApiEnvelope } from '../../../shared/api/apiEnvelope';

export type MasterDataRow = Record<string, unknown>;

export type RawPagination = {
  page?: number;
  page_size?: number;
  total?: number;
  total_items?: number;
  total_pages?: number;
  has_next?: boolean;
  has_previous?: boolean;
};

export type Pagination = {
  page: number;
  page_size: number;
  total: number;
  total_pages?: number;
  has_next?: boolean;
  has_previous?: boolean;
};

export type PaginatedListResponse<T> = {
  items: T[];
  pagination?: RawPagination;
};

export type ListQuery = {
  page?: number;
  page_size?: number;
};

export type MasterDataListQuery = ListQuery & {
  query?: string;
  status?: string;
};

export type DeactivatePayload = {
  reason: string;
  force?: boolean;
};

function readFiniteNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

export function normalizePagination(pagination?: RawPagination): Pagination | undefined {
  if (!pagination) {
    return undefined;
  }

  const page = readFiniteNumber(pagination.page) ?? 1;
  const pageSize = readFiniteNumber(pagination.page_size) ?? 20;
  const total = readFiniteNumber(pagination.total) ?? readFiniteNumber(pagination.total_items) ?? 0;
  const totalPages = readFiniteNumber(pagination.total_pages) ?? (pageSize > 0 ? Math.ceil(total / pageSize) : undefined);
  const hasNext = typeof pagination.has_next === 'boolean' ? pagination.has_next : totalPages != null ? page < totalPages : undefined;
  const hasPrevious = typeof pagination.has_previous === 'boolean' ? pagination.has_previous : page > 1;

  return {
    page,
    page_size: pageSize,
    total,
    total_pages: totalPages,
    has_next: hasNext,
    has_previous: hasPrevious,
  };
}

export function normalizePaginatedListEnvelope<T>(
  envelope: ApiEnvelope<PaginatedListResponse<T>>
): ApiEnvelope<{ items: T[]; pagination?: Pagination }> {
  if (!envelope.ok) {
    return envelope;
  }

  return {
    ...envelope,
    data: {
      items: envelope.data.items,
      pagination: normalizePagination(envelope.data.pagination),
    },
  };
}

export function normalizeListQuery(query?: ListQuery, defaults: Required<ListQuery> = { page: 1, page_size: 20 }): Required<ListQuery> {
  return {
    page: query?.page ?? defaults.page,
    page_size: query?.page_size ?? defaults.page_size,
  };
}

export function buildQueryString(params: Record<string, string | number | boolean | null | undefined>): string {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') {
      continue;
    }
    searchParams.set(key, String(value));
  }
  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : '';
}