import React from 'react'

type Variant = 'default' | 'secondary' | 'destructive' | 'outline'

function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(' ')
}

export const Badge: React.FC<React.HTMLAttributes<HTMLSpanElement> & { variant?: Variant } > = ({
  className,
  variant = 'default',
  ...props
}) => {
  const variants: Record<Variant, string> = {
    default: 'bg-black text-white',
    secondary: 'bg-slate-200 text-slate-900',
    destructive: 'bg-red-600 text-white',
    outline: 'border border-slate-300 text-slate-700',
  }
  return (
    <span
      className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs', variants[variant], className)}
      {...props}
    />
  )
}

export default Badge


