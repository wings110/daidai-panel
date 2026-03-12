import { create } from 'zustand'

interface ThemeState {
  darkMode: boolean
  toggleDark: () => void
}

export const useThemeStore = create<ThemeState>((set) => ({
  darkMode: localStorage.getItem('theme') === 'dark',
  toggleDark: () =>
    set((state) => {
      const next = !state.darkMode
      localStorage.setItem('theme', next ? 'dark' : 'light')
      return { darkMode: next }
    }),
}))
