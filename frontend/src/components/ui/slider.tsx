import React from 'react'

type SliderProps = {
  value: [number]
  min?: number
  max?: number
  step?: number
  onValueChange?: (v: [number]) => void
}

export const Slider: React.FC<SliderProps> = ({ value, min = 0, max = 100, step = 1, onValueChange }) => {
  const [internal, setInternal] = React.useState(value[0])
  React.useEffect(() => setInternal(value[0]), [value])
  return (
    <input
      type="range"
      min={min}
      max={max}
      step={step}
      value={internal}
      onChange={(e) => {
        const v = Number(e.target.value)
        setInternal(v)
        onValueChange?.([v])
      }}
      className="w-full accent-black"
    />
  )
}

export default Slider


