## ADDED Requirements

### Requirement: Página /addresses con lista de direcciones
El sistema SHALL tener un componente `AddressesPage` en `frontend/src/pages/AddressesPage/` (o `frontend/src/pages/addresses/`) que se renderice en la ruta `/addresses`. La página SHALL:
- Mostrar la lista de direcciones del usuario autenticado usando `useAddresses()`.
- Indicar visualmente cuál es la dirección principal (badge/tag "Principal").
- Mostrar un estado de loading mientras se carga la lista.
- Mostrar un estado vacío cuando el usuario no tiene direcciones, con mensaje: "No tenés direcciones guardadas. Podés retirar tu pedido en nuestro local o agregar una dirección."
- Incluir un botón "Agregar dirección" que abre el formulario de creación.
- Por cada dirección en la lista, mostrar acciones: "Editar", "Establecer como principal" (oculto si ya es principal), "Eliminar".

#### Scenario: Lista con direcciones se renderiza correctamente
- **WHEN** el usuario navega a `/addresses` y tiene 2 direcciones
- **THEN** se muestran ambas con su alias, linea1 y estado principal
- **THEN** la dirección principal tiene indicador visual "Principal"

#### Scenario: Estado vacío muestra mensaje y CTA
- **WHEN** el usuario navega a `/addresses` y no tiene direcciones
- **THEN** se muestra un mensaje explicativo del flujo "sin dirección"
- **THEN** hay un botón para agregar la primera dirección

#### Scenario: Estado loading mientras carga
- **WHEN** el usuario navega a `/addresses` y la query está pendiente
- **THEN** se muestra un skeleton o spinner (no un estado vacío prematuro)

---

### Requirement: Formulario de creación y edición de dirección
El sistema SHALL tener un formulario en la página `/addresses` (modal o sección inline) usando TanStack Form para crear y editar direcciones. El formulario SHALL:
- Incluir campos: `alias` (opcional, placeholder "Casa, Trabajo…"), `linea1` (requerido), `linea2` (opcional), `ciudad` (opcional), `provincia` (opcional), `codigo_postal` (opcional), `referencia` (opcional).
- Validar `linea1` como requerido con mínimo 3 caracteres antes del submit.
- Validar `alias` con máximo 50 caracteres.
- En modo edición: pre-cargar los valores actuales de la dirección seleccionada.
- El submit SHALL llamar `useCreateAddress()` o `useUpdateAddress()` según corresponda.
- Mostrar errores de validación inline bajo cada campo.
- Deshabilitar el botón de submit mientras la mutation está pendiente: usar `mutation.isPending` (TanStack Query v5 — reemplaza `isLoading` deprecado de v4 para mutations).

#### Scenario: Submit con linea1 vacía muestra error inline
- **WHEN** el usuario intenta enviar el formulario sin completar `linea1`
- **THEN** se muestra un mensaje de error bajo el campo `linea1`
- **THEN** la mutation no se ejecuta

#### Scenario: Formulario de edición precarga datos
- **WHEN** el usuario abre el formulario de edición para una dirección con alias "Casa"
- **THEN** el campo alias muestra "Casa" pre-cargado

#### Scenario: Submit exitoso cierra formulario y actualiza lista
- **WHEN** el usuario envía el formulario de creación con datos válidos
- **THEN** la mutation se ejecuta, el formulario se cierra
- **THEN** la lista se actualiza con la nueva dirección

---

### Requirement: Acción "Establecer como principal"
La página `/addresses` SHALL incluir la acción de marcar una dirección como principal. SHALL:
- El botón "Establecer como principal" solo estar visible en direcciones que NO son la principal actual.
- Al hacer clic, llamar `useSetMainAddress(id)`.
- Mostrar loading state en el botón mientras la mutation procesa: usar `useSetMainAddress().isPending` (TanStack Query v5).
- Actualizar la lista automáticamente (invalidación de cache) tras el éxito.
- NO mostrar confirmación previa (la acción es reversible).

#### Scenario: Solo una dirección tiene el badge "Principal"
- **WHEN** el usuario marca la dirección B como principal (antes lo era la A)
- **THEN** la dirección A pierde el badge "Principal"
- **THEN** la dirección B muestra el badge "Principal"
- **THEN** el botón "Establecer como principal" reaparece en A y desaparece de B

---

### Requirement: Acción "Eliminar dirección" con confirmación
La página `/addresses` SHALL incluir la acción de eliminar con diálogo de confirmación. SHALL:
- Al hacer clic en "Eliminar", mostrar un diálogo de confirmación: "¿Querés eliminar esta dirección? Esta acción no se puede deshacer."
- Solo ejecutar `useDeleteAddress(id)` si el usuario confirma.
- Si la dirección era la principal y hay otras, el badge "Principal" SHALL aparecer en la nueva principal automáticamente (reflejo de la respuesta del servidor via cache invalidation).
- Mostrar loading state en el botón de confirmar mientras la mutation procesa: usar `useDeleteAddress().isPending` (TanStack Query v5).

#### Scenario: Cancelar eliminación no modifica la lista
- **WHEN** el usuario hace clic en "Eliminar" y luego cancela en el diálogo
- **THEN** la lista permanece sin cambios
- **THEN** la mutation no se ejecuta

#### Scenario: Eliminar principal actualiza visualmente la nueva principal
- **WHEN** el usuario elimina su dirección principal y tiene otras
- **THEN** la lista se actualiza (via cache invalidation)
- **THEN** otra dirección muestra el badge "Principal"

---

### Requirement: Integración con design system y accesibilidad básica
Los componentes de la página `/addresses` SHALL usar los tokens de Tailwind del design system del proyecto (`frontend-tailwind-tokens`). SHALL:
- Usar variantes de color, espaciado y tipografía consistentes con el resto de la UI.
- Los botones SHALL tener `aria-label` descriptivo cuando el texto no es suficiente.
- Los formularios SHALL tener `<label>` asociados correctamente a sus `<input>` vía `htmlFor`.
- El diálogo de confirmación SHALL ser accesible con foco atrapado mientras está abierto.

#### Scenario: Formulario tiene labels accesibles
- **WHEN** se renderiza el formulario de dirección
- **THEN** cada campo input tiene un elemento `<label>` asociado con `htmlFor` correcto

#### Scenario: Botones de acción tienen texto o aria-label descriptivo
- **WHEN** se renderizan los botones de la lista de direcciones
- **THEN** cada botón tiene texto o `aria-label` que describe la acción claramente
