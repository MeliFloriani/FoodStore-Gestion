/**
 * AllergenBadge — visual badge for an allergen ingredient.
 */

interface AllergenBadgeProps {
  nombre: string
}

export function AllergenBadge({ nombre }: AllergenBadgeProps) {
  return (
    <span
      title={`Alérgeno: ${nombre}`}
      className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800 dark:bg-amber-900/20 dark:text-amber-400"
    >
      <span aria-hidden="true">⚠</span>
      {nombre}
    </span>
  )
}
