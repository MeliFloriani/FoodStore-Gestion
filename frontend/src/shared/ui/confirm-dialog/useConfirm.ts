import { useConfirmContext } from './ConfirmDialogProvider'
import type { ConfirmOptions } from './confirm-dialog.types'

export function useConfirm() {
  const { openConfirm } = useConfirmContext()
  return {
    confirm: (options: ConfirmOptions) => openConfirm(options),
  }
}
