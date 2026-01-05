import { useMemo } from 'react';
import toast, { Toast } from 'react-hot-toast';

interface ToastOptions {
  duration?: number;
  id?: string;
}

export const useToast = () => {
  return useMemo(() => ({
    success: (message: string, options?: ToastOptions) => {
      return toast.success(message, {
        duration: options?.duration ?? 3000,
        id: options?.id,
        style: {
          background: 'var(--surface-elevated)',
          color: 'var(--text-primary)',
          boxShadow: 'var(--shadow-lg)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-md)',
        },
        iconTheme: {
          primary: 'var(--success)',
          secondary: 'white',
        },
      });
    },

    error: (message: string, options?: ToastOptions) => {
      return toast.error(message, {
        duration: options?.duration ?? 5000,
        id: options?.id,
        style: {
          background: 'var(--surface-elevated)',
          color: 'var(--text-primary)',
          boxShadow: 'var(--shadow-lg)',
          border: '1px solid var(--accent)',
          borderRadius: 'var(--radius-md)',
        },
        iconTheme: {
          primary: 'var(--accent)',
          secondary: 'white',
        },
      });
    },

    loading: (message: string, options?: ToastOptions) => {
      return toast.loading(message, {
        duration: options?.duration ?? Infinity,
        id: options?.id,
        style: {
          background: 'var(--surface-elevated)',
          color: 'var(--text-primary)',
          boxShadow: 'var(--shadow-lg)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-md)',
        },
      });
    },

    info: (message: string, options?: ToastOptions) => {
      return toast(message, {
        duration: options?.duration ?? 4000,
        id: options?.id,
        icon: 'ℹ️',
        style: {
          background: 'var(--surface-elevated)',
          color: 'var(--text-primary)',
          boxShadow: 'var(--shadow-lg)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-md)',
        },
      });
    },

    dismiss: (toastId?: string) => {
      toast.dismiss(toastId);
    },

    promise: <T,>(
      promise: Promise<T>,
      messages: {
        loading: string;
        success: string | ((data: T) => string);
        error: string | ((error: any) => string);
      }
    ) => {
      return toast.promise(
        promise,
        {
          loading: messages.loading,
          success: messages.success,
          error: messages.error,
        },
        {
          style: {
            background: 'var(--surface-elevated)',
            color: 'var(--text-primary)',
            boxShadow: 'var(--shadow-lg)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)',
          },
          success: {
            iconTheme: {
              primary: 'var(--success)',
              secondary: 'white',
            },
          },
          error: {
            iconTheme: {
              primary: 'var(--accent)',
              secondary: 'white',
            },
          },
        }
      );
    },
  }), []); // Array vuoto = stesso oggetto per tutta la vita del componente
};
