import React from 'react'

function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(' ')
}

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        'flex h-10 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-black',
        className,
      )}
      {...props}
    />
  ),
)
Input.displayName = 'Input'

export default Input


