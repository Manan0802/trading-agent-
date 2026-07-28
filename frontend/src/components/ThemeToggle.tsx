import { useEffect, useState } from 'react'
import { Monitor, Moon, Sun } from 'lucide-react'
import { cn } from '@/lib/utils'

type Theme = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'nextrade-theme'

function apply(theme: Theme) {
  const dark =
    theme === 'dark' ||
    (theme === 'system' &&
      window.matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark', dark)
}

function stored(): Theme {
  const value = localStorage.getItem(STORAGE_KEY)
  return value === 'light' || value === 'dark' ? value : 'system'
}

const OPTIONS: { value: Theme; label: string; Icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', Icon: Sun },
  { value: 'system', label: 'System', Icon: Monitor },
  { value: 'dark', label: 'Dark', Icon: Moon },
]

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(stored)

  useEffect(() => {
    apply(theme)
    if (theme === 'system') {
      localStorage.removeItem(STORAGE_KEY)
      // Follow the OS while on "system": without this the page keeps whatever
      // mode it happened to load in when the user switches theme at night.
      const media = window.matchMedia('(prefers-color-scheme: dark)')
      const onChange = () => apply('system')
      media.addEventListener('change', onChange)
      return () => media.removeEventListener('change', onChange)
    }
    localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  return (
    <div
      role="radiogroup"
      aria-label="Colour theme"
      className="flex items-center rounded-md border p-0.5"
    >
      {OPTIONS.map(({ value, label, Icon }) => (
        <button
          key={value}
          role="radio"
          aria-checked={theme === value}
          aria-label={label}
          title={label}
          onClick={() => setTheme(value)}
          className={cn(
            // A 26px square is a miss on a phone. The icon stays 14px; the
            // thing a thumb has to land on does not.
            'flex size-8 items-center justify-center rounded-sm transition-colors',
            'pointer-coarse:size-9',
            'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
            theme === value
              ? 'bg-secondary text-foreground'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          <Icon className="size-3.5" aria-hidden />
        </button>
      ))}
    </div>
  )
}

/** Applied before React mounts so the first paint is already in the right mode. */
export function initTheme() {
  apply(stored())
}
