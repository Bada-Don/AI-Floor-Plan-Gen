import React from 'react'

function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(' ')
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        'flex min-h-[80px] w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-black',
        className,
      )}
      {...props}
    />
  ),
)
Textarea.displayName = 'Textarea'

export default Textarea


