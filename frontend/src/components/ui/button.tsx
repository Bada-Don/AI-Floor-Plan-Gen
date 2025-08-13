import React from 'react'

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'default' | 'outline' | 'secondary'
  size?: 'default' | 'sm' | 'icon'
}

function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(' ')
}

export const Button: React.FC<ButtonProps> = ({
  className,
  variant = 'default',
  size = 'default',
  children,
  ...props
}) => {
  const base = 'inline-flex items-center justify-center rounded-md transition-colors disabled:opacity-50 disabled:pointer-events-none'
  const variants: Record<string, string> = {
    default: 'bg-black text-white hover:bg-black/90 border border-transparent',
    outline: 'bg-transparent text-black border border-slate-300 hover:bg-slate-100',
    secondary: 'bg-slate-900/80 text-white hover:bg-slate-900',
  }
  const sizes: Record<string, string> = {
    default: 'h-10 px-4 py-2 text-sm',
    sm: 'h-8 px-3 py-1.5 text-sm',
    icon: 'h-10 w-10',
  }
  return (
    <button
      className={cn(base, variants[variant], sizes[size], className)}
      {...props}
    >
      {children}
    </button>
  )
}

export default Button


