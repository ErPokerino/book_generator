import React from 'react'
import { BookOpen, PenLine, RefreshCw, Zap, Star, Rocket, Library } from 'lucide-react'

interface IconProps {
  className?: string
  size?: number
}

export const WelcomeIcon: React.FC<IconProps> = ({ className = '', size = 80 }) => {
  return (
    <BookOpen 
      className={className}
      size={size}
      strokeWidth={1.5}
    />
  )
}

export const CustomizeIcon: React.FC<IconProps> = ({ className = '', size = 80 }) => {
  return (
    <PenLine 
      className={className}
      size={size}
      strokeWidth={1.5}
    />
  )
}

export const EditIcon: React.FC<IconProps> = ({ className = '', size = 80 }) => {
  return (
    <RefreshCw 
      className={className}
      size={size}
      strokeWidth={1.5}
    />
  )
}

export const ModesIcon: React.FC<IconProps> = ({ className = '', size = 80 }) => {
  return (
    <Rocket 
      className={className}
      size={size}
      strokeWidth={1.5}
    />
  )
}

export const LibraryIcon: React.FC<IconProps> = ({ className = '', size = 80 }) => {
  return (
    <Library 
      className={className}
      size={size}
      strokeWidth={1.5}
    />
  )
}
