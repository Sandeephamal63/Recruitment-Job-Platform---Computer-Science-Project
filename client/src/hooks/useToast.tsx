import { Button } from '@mui/material'
import { type OptionsObject, type SnackbarKey, useSnackbar } from 'notistack'
import { useCallback } from 'react'

export interface ToastOptions {
  title?: string
  actionLabel?: string
  onAction?: () => void
  autoHideDuration?: number
  persist?: boolean
}

export function useToast() {
  const { enqueueSnackbar, closeSnackbar } = useSnackbar()

  const show = useCallback(
    (
      variant: 'success' | 'error' | 'info' | 'warning',
      message: string,
      options?: ToastOptions,
    ) => {
      const fullMessage = options?.title ? `${options.title}\n${message}` : message

      const snackOpts: OptionsObject = {
        variant,
        autoHideDuration: options?.autoHideDuration,
        persist: options?.persist,
      }

      if (options?.actionLabel && options?.onAction) {
        snackOpts.action = (key: SnackbarKey) => (
          <Button
            size="small"
            variant="outlined"
            onClick={() => {
              options.onAction?.()
              closeSnackbar(key)
            }}
            sx={{
              py: 0.25,
              px: 1.25,
              fontSize: '0.75rem',
              minWidth: 'auto',
              borderRadius: '6px',
              borderColor: 'rgba(22, 26, 18, 0.2)',
              color: '#161A12',
              textTransform: 'none',
              fontWeight: 600,
              '&:hover': {
                borderColor: '#161A12',
                backgroundColor: 'rgba(22, 26, 18, 0.04)',
              },
            }}
          >
            {options.actionLabel}
          </Button>
        )
      }

      return enqueueSnackbar(fullMessage, snackOpts)
    },
    [enqueueSnackbar, closeSnackbar],
  )

  const success = useCallback(
    (message: string, options?: ToastOptions) => show('success', message, options),
    [show],
  )

  const error = useCallback(
    (message: string, options?: ToastOptions) => show('error', message, options),
    [show],
  )

  const info = useCallback(
    (message: string, options?: ToastOptions) => show('info', message, options),
    [show],
  )

  const warning = useCallback(
    (message: string, options?: ToastOptions) => show('warning', message, options),
    [show],
  )

  return { success, error, info, warning, dismiss: closeSnackbar }
}
