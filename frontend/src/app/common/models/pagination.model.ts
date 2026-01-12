export interface PaginatedResponse<T> {
  count: number;
  data: T[];
  page: number;
  pageSize: number;
  totalPages: number;
}
