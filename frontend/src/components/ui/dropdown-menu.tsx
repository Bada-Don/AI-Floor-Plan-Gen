// @ts-nocheck
import React from 'react'

type DropdownContextValue = {
  open: boolean
  setOpen: (o: boolean) => void
}
const DropdownContext = React.createContext<DropdownContextValue | null>(null)

export const DropdownMenu: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [open, setOpen] = React.useState(false)
  return (
    <DropdownContext.Provider value={{ open, setOpen }}>
      <div className="relative inline-block">{children}</div>
    </DropdownContext.Provider>
  )
}

export const DropdownMenuTrigger: React.FC<{ asChild?: boolean, children: React.ReactElement } & React.HTMLAttributes<HTMLButtonElement>>
  = ({ children }) => {
  const ctx = React.useContext(DropdownContext)!
  return React.cloneElement(children, {
    onClick: (e: any) => {
      children.props.onClick?.(e)
      ctx.setOpen(!ctx.open)
    },
  })
}

export const DropdownMenuContent: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, ...props }) => {
  const ctx = React.useContext(DropdownContext)!
  if (!ctx.open) return null
  return (
    <div className={[
      'absolute z-50 mt-2 min-w-[12rem] rounded-md border border-slate-200 bg-white p-1 shadow-md',
      className,
    ].filter(Boolean).join(' ')} {...props} />
  )
}

export const DropdownMenuLabel: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, ...props }) => (
  <div className={[ 'px-2 py-1.5 text-xs text-slate-500', className ].filter(Boolean).join(' ')} {...props} />
)
export const DropdownMenuSeparator: React.FC = () => (
  <div className="my-1 h-px bg-slate-200" />
)
export const DropdownMenuItem: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, ...props }) => (
  <div className={[ 'cursor-pointer select-none rounded-sm px-2 py-1.5 text-sm hover:bg-slate-100', className ].filter(Boolean).join(' ')} {...props} />
)


