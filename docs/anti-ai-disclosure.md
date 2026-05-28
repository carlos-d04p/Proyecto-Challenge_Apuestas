# Declaración de uso de IA — Sleyter Correa

## App asignada: `markets` (Catálogo de eventos y mercados)

---

## ¿Qué consulté a la IA?

### 1. Entender el concepto de margen del operador
- **Qué pedí:** Que me explicara cómo funciona el "vigorish" o margen en las
  apuestas deportivas y cómo se aplica matemáticamente a las cuotas.
- **Para qué:** Estudiar el concepto antes de implementar `apply_margin()`.
- **Lo que hice yo:** Decidí que el margen se aplica al crear la selección y no
  se almacena como campo separado, basándome en el esquema del proyecto.

### 2. Repaso de `prefetch_related` vs `select_related` en Django
- **Qué pedí:** Explicación de cuándo usar uno u otro con relaciones ForeignKey
  y ManyToMany.
- **Para qué:** Optimizar los queries en los ViewSets al devolver eventos con
  sus mercados y selecciones anidados.
- **Lo que hice yo:** Apliqué `prefetch_related("markets__selections")` en el
  queryset del EventViewSet.

### 3. Revisión del error de routing en DRF
- **Qué pedí:** Ayuda para entender por qué el `DefaultRouter` no encontraba
  la acción personalizada `@action(detail=True, url_path="markets")`.
- **Para qué:** Depurar un error 404 al llamar `/api/markets/events/{id}/markets/`.
- **Lo que hice yo:** Identifiqué que el problema era el nombre del `basename`
  en el router, no el decorador.

---

## Lo que NO generé con IA
- La lógica de estados del evento (FSM)
- La estructura de los tests con pytest fixtures
- La decisión de usar UUID como PK para permitir referencias desde `linea_apuesta`
- El ADR-0001

---

> Ningún bloque de código fue copiado y pegado directamente sin comprenderlo.
> Todo fue revisado, ajustado y es defendible línea por línea.
