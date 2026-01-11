import { RouterProvider } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { AuthProvider } from './contexts/AuthContext'
import { NotificationProvider } from './contexts/NotificationContext'
import { router } from './router'
import './App.css'

function App() {
  return (
    <AuthProvider>
      <NotificationProvider>
        <Toaster 
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              background: 'var(--surface-elevated)',
              color: 'var(--text-primary)',
              boxShadow: 'var(--shadow-lg)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              padding: '1rem',
              fontSize: '0.95rem',
            },
            success: {
              duration: 3000,
              iconTheme: {
                primary: 'var(--success)',
                secondary: 'white',
              },
            },
            error: {
              duration: 5000,
              iconTheme: {
                primary: 'var(--accent)',
                secondary: 'white',
              },
            },
            loading: {
              iconTheme: {
                primary: 'var(--accent)',
                secondary: 'white',
              },
            },
          }}
          containerStyle={{
            top: 20,
            right: 20,
          }}
        />
        <RouterProvider router={router} />
      </NotificationProvider>
    </AuthProvider>
  )
}

export default App



