## ADDED Requirements

### Requirement: Tipos TypeScript de DireccionEntrega
El sistema SHALL tener tipos TypeScript en `frontend/src/entities/direccion-entrega/model/types.ts` que reflejen el contrato de la API:

```typescript
interface DireccionEntrega {
  id: number;
  usuarioId: number;
  alias: string | null;
  linea1: string;
  linea2: string | null;
  ciudad: string | null;
  provincia: string | null;
  codigoPostal: string | null;
  referencia: string | null;
  esPrincipal: boolean;
  createdAt: string; // ISO 8601
  updatedAt: string; // ISO 8601
}

interface DireccionEntregaCreateDto {
  alias?: string | null;
  linea1: string;
  linea2?: string | null;
  ciudad?: string | null;
  provincia?: string | null;
  codigoPostal?: string | null;
  referencia?: string | null;
}

interface DireccionEntregaUpdateDto {
  alias?: string | null;
  linea1?: string;
  linea2?: string | null;
  ciudad?: string | null;
  provincia?: string | null;
  codigoPostal?: string | null;
  referencia?: string | null;
}
```

Los tipos SHALL usar camelCase en frontend. El mapeo snake_case→camelCase SHALL realizarse mediante el mismo patrón ya usado en `frontend-profile-page` (Change 13) para transformación de responses — ya sea la función `transformKeys` en `shared/lib/` o el interceptor de Axios en `shared/api/axios-instance.ts`. No reimplementar manualmente en cada función del API client.

#### Scenario: Tipos exportados desde index barrel
- **WHEN** una feature importa `DireccionEntrega` desde `@/entities/direccion-entrega`
- **THEN** el import resuelve correctamente sin path directo a subcarpetas

---

### Requirement: API client functions para DireccionEntrega
El sistema SHALL tener funciones de API client en `frontend/src/entities/direccion-entrega/api/direccion-entrega-api.ts` usando el Axios instance con interceptor JWT. SHALL implementar:

- `getAddresses(): Promise<DireccionEntrega[]>` — `GET /api/v1/direcciones`
- `getAddress(id: number): Promise<DireccionEntrega>` — `GET /api/v1/direcciones/{id}`
- `createAddress(data: DireccionEntregaCreateDto): Promise<DireccionEntrega>` — `POST /api/v1/direcciones`
- `updateAddress(id: number, data: DireccionEntregaUpdateDto): Promise<DireccionEntrega>` — `PATCH /api/v1/direcciones/{id}`
- `setMainAddress(id: number): Promise<DireccionEntrega>` — `PATCH /api/v1/direcciones/{id}/principal` (sin body)
- `deleteAddress(id: number): Promise<void>` — `DELETE /api/v1/direcciones/{id}`

Las funciones SHALL usar el cliente Axios de `shared/api` (no crear instancias nuevas). Los errores de red y HTTP SHALL propagarse como `AxiosError` para que TanStack Query los maneje.

#### Scenario: createAddress llama al endpoint correcto
- **WHEN** se llama `createAddress({ linea1: 'Av. Siempre Viva 742' })`
- **THEN** Axios hace POST a `/api/v1/direcciones` con el body correcto
- **THEN** retorna la dirección creada

#### Scenario: setMainAddress envía PATCH sin body
- **WHEN** se llama `setMainAddress(5)`
- **THEN** Axios hace PATCH a `/api/v1/direcciones/5/principal` sin body
- **THEN** retorna la dirección actualizada

#### Scenario: deleteAddress retorna void en 204
- **WHEN** se llama `deleteAddress(3)` y el servidor responde 204
- **THEN** la función retorna `undefined` sin error

---

### Requirement: Hooks TanStack Query para DireccionEntrega
El sistema SHALL tener hooks de TanStack Query v5 en `frontend/src/entities/direccion-entrega/api/use-direcciones.ts`:

- `useAddresses()`: query key `['addresses']`, llama `getAddresses()`. Activo solo si el usuario está autenticado: `enabled: !!useAuthStore(state => state.usuario)` (usando el authStore del proyecto — campo `usuario` establecido en Change 07).
- `useAddress(id: number)`: query key `['addresses', id]`, llama `getAddress(id)`.
- `useCreateAddress()`: mutation que llama `createAddress`, invalida `['addresses']` en `onSuccess`.
- `useUpdateAddress()`: mutation que llama `updateAddress(id, data)`. La mutation recibe `variables: { id: number, data: DireccionEntregaUpdateDto }`. En `onSuccess(_, variables)`: invalidar `queryClient.invalidateQueries({ queryKey: ['addresses'] })` y `queryClient.invalidateQueries({ queryKey: ['addresses', variables.id] })`.
- `useSetMainAddress()`: mutation que llama `setMainAddress(id)`, invalida `['addresses']` en `onSuccess`.
- `useDeleteAddress()`: mutation que llama `deleteAddress(id)`, invalida `['addresses']` en `onSuccess`.

Los hooks SHALL usar `useQueryClient` para invalidaciones. NOT SHALL duplicar estado en Zustand (las direcciones son server state).

#### Scenario: useAddresses solo activo con usuario autenticado
- **WHEN** el usuario no está autenticado
- **THEN** `useAddresses` no ejecuta el fetch (`enabled: false`)

#### Scenario: useCreateAddress invalida cache tras éxito
- **WHEN** la mutation de crear dirección tiene éxito
- **THEN** TanStack Query invalida `['addresses']`
- **THEN** el componente que usa `useAddresses` re-fetcha automáticamente

#### Scenario: useDeleteAddress invalida cache y la lista se actualiza
- **WHEN** la mutation de eliminar dirección tiene éxito
- **THEN** TanStack Query invalida `['addresses']`
- **THEN** la lista de direcciones se actualiza sin la dirección eliminada
