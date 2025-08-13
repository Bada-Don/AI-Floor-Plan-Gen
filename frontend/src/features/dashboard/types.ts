export type Priority = 'low' | 'medium' | 'high'

export interface ElementConstraint {
  id: string
  type: string
  width?: number
  height?: number
  position?: string
  priority?: Priority
  locked?: boolean
}

export interface StructuredConstraints {
  lot: { width: number; height: number }
  elements: ElementConstraint[]
  notes?: string
}

export interface ChangeEvent {
  action: 'modify' | 'delete' | 'add' | 'lock' | 'unlock' | 'accept_suggestion'
  target?: string
  changes?: Record<string, any>
  suggestion?: string
}

export interface LayoutFeature {
  type: string
  x: number
  y: number
  width: number
  height: number
  id?: string
}

export interface LayoutResponse {
  lot: { width: number; height: number }
  features: LayoutFeature[]
}

export interface ConflictResponse {
  error: string
  conflicts: string[]
  suggestions: string[]
}


