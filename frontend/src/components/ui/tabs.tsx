import React, { useState } from 'react'

type TabsContextValue = {
  value: string
  setValue: (v: string) => void
}

const TabsContext = React.createContext<TabsContextValue | null>(null)

export const Tabs: React.FC<React.HTMLAttributes<HTMLDivElement> & { defaultValue?: string, value?: string, onValueChange?: (v: string) => void }>
  = ({ children, defaultValue, value, onValueChange, ...props }) => {
  const [internal, setInternal] = useState(defaultValue || '')
  const current = value !== undefined ? value : internal
  const set = (v: string) => {
    if (onValueChange) onValueChange(v)
    else setInternal(v)
  }
  return (
    <TabsContext.Provider value={{ value: current, setValue: set }}>
      <div {...props}>{children}</div>
    </TabsContext.Provider>
  )
}

export const TabsList: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, ...props }) => (
  <div className={['inline-flex rounded-lg border border-slate-300 p-1', className].filter(Boolean).join(' ')} {...props} />
)

export const TabsTrigger: React.FC<React.ButtonHTMLAttributes<HTMLButtonElement> & { value: string }>
  = ({ value, className, ...props }) => {
  const ctx = React.useContext(TabsContext)
  const active = ctx?.value === value
  return (
    <button
      className={[
        'px-3 py-1.5 text-sm rounded-md',
        active ? 'bg-black text-white' : 'text-slate-700 hover:bg-slate-100',
        className,
      ].filter(Boolean).join(' ')}
      onClick={() => ctx?.setValue(value)}
      {...props}
    />
  )
}

export const TabsContent: React.FC<React.HTMLAttributes<HTMLDivElement> & { value: string }>
  = ({ value, className, ...props }) => {
  const ctx = React.useContext(TabsContext)
  if (ctx?.value !== value) return null
  return <div className={className} {...props} />
}


