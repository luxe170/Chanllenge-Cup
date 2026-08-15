import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { AnchorHTMLAttributes, MouseEvent, ReactNode } from 'react'

interface RouterValue {
  path: string
  navigate: (path: string) => void
}

const RouterContext = createContext<RouterValue | null>(null)

const normalizePath = (path: string) => path === '/' ? '/dashboard' : path.replace(/\/$/, '')

export function RouterProvider({ children }: { children: ReactNode }) {
  const [path, setPath] = useState(() => normalizePath(window.location.pathname))

  useEffect(() => {
    const handlePopState = () => setPath(normalizePath(window.location.pathname))
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  const value = useMemo<RouterValue>(() => ({
    path,
    navigate: (nextPath) => {
      const normalized = normalizePath(nextPath)
      if (normalized === path) return
      window.history.pushState({}, '', normalized)
      setPath(normalized)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    },
  }), [path])

  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>
}

export function useAppRouter() {
  const value = useContext(RouterContext)
  if (!value) throw new Error('useAppRouter must be used within RouterProvider')
  return value
}

export function AppLink({ to, onClick, children, ...props }: AnchorHTMLAttributes<HTMLAnchorElement> & { to: string }) {
  const { navigate } = useAppRouter()
  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event)
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    event.preventDefault()
    navigate(to)
  }

  return <a href={to} onClick={handleClick} {...props}>{children}</a>
}
