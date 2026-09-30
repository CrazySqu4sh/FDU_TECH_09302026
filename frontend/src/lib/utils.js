import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

// Merge Tailwind classes the way shadcn/ui and v0 components expect.
export function cn(...inputs) {
  return twMerge(clsx(inputs))
}
