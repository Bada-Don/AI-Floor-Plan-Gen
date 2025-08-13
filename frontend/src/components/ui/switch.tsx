import React from 'react'

type SwitchProps = React.InputHTMLAttributes<HTMLInputElement>

export const Switch: React.FC<SwitchProps> = ({ className, ...props }) => {
  return (
    <label className={"inline-flex items-center cursor-pointer"}>
      <input type="checkbox" className="sr-only peer" {...props} />
      <div className="w-10 h-6 bg-slate-300 rounded-full peer-checked:bg-black relative transition-colors">
        <div className="absolute left-0.5 top-0.5 h-5 w-5 bg-white rounded-full transition-transform peer-checked:translate-x-4" />
      </div>
    </label>
  )
}

export default Switch


