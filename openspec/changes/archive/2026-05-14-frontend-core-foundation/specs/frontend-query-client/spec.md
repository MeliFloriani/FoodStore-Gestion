## ADDED Requirements

### Requirement: QueryClientProvider configured at app root
`src/app/providers/QueryProvider.tsx` SHALL export a `QueryProvider` component that wraps children with a TanStack Query 5 `QueryClientProvider`. The `QueryClient` instance SHALL be created inside the component (or with `useState` to avoid re-creation on re-render) and SHALL apply the project-standard default options.

#### Scenario: QueryProvider wraps the application
- **WHEN** `App.tsx` renders the `QueryProvider`
- **THEN** any descendant component can call `useQuery` or `useMutation` without receiving a "QueryClient not found" error

---

### Requirement: QueryClient default query options
The `QueryClient` SHALL be instantiated with:
- `defaultOptions.queries.staleTime`: `60_000` (1 minute)
- `defaultOptions.queries.gcTime`: `300_000` (5 minutes)
- `defaultOptions.queries.refetchOnWindowFocus`: `false` in development (`import.meta.env.DEV`), `true` in production
- `defaultOptions.queries.retry`: a function that returns `false` for 4xx responses (except status 408 and 429), and allows up to 2 retries for 5xx responses and network errors

#### Scenario: 404 error is not retried
- **WHEN** a query receives a 404 AxiosError response
- **THEN** TanStack Query does not retry the request

#### Scenario: 500 error retries up to 2 times
- **WHEN** a query receives a 500 AxiosError response
- **THEN** TanStack Query retries the request at most 2 additional times

#### Scenario: 401 error is not retried by query layer
- **WHEN** a query receives a 401 AxiosError response
- **THEN** the retry function returns `false` (the Axios interceptor handles 401 separately)

---

### Requirement: Centralized query keys factory
`src/shared/lib/queryKeys.ts` SHALL export a `queryKeys` object with namespaced factory functions for the following domains: `auth`, `catalog`, `cart`, `orders`, `payment`. Each namespace SHALL provide at minimum an `all` key (tuple) usable for broad cache invalidation, plus specific keys for common queries.

The shape SHALL follow the pattern:
```
queryKeys.<domain>.all()          → ['<domain>']
queryKeys.<domain>.<resource>(id) → ['<domain>', '<resource>', id]
```

#### Scenario: Query key factory returns stable tuples
- **WHEN** `queryKeys.catalog.all()` is called twice
- **THEN** both calls return arrays with the same content (`['catalog']`)

#### Scenario: All domain namespaces are present
- **WHEN** `queryKeys` is imported
- **THEN** it contains keys for `auth`, `catalog`, `cart`, `orders`, and `payment` namespaces

---

### Requirement: Invalidation strategy documented (no implementation)
The design SHALL document (in `design.md`) that after any mutation affecting a domain, the caller SHALL call `queryClient.invalidateQueries({ queryKey: queryKeys.<domain>.all() })` to trigger refetch. This invalidation is NOT implemented in this change — it is the contract for feature changes.

#### Scenario: No query invalidation code in this change
- **WHEN** the files created in this change are inspected
- **THEN** there are no `queryClient.invalidateQueries` calls (this is an infrastructure change only)
