import type { HTMLAttributes } from 'react'
export function Card({ className = '', ...props }: HTMLAttributes<HTMLDivElement>) { return <div className={`rounded-xl border border-zinc-200 bg-white text-zinc-950 shadow-sm ${className}`} {...props} /> }
export function CardHeader({ className = '', ...props }: HTMLAttributes<HTMLDivElement>) { return <div className={`flex flex-col space-y-1.5 p-6 ${className}`} {...props} /> }
export function CardContent({ className = '', ...props }: HTMLAttributes<HTMLDivElement>) { return <div className={`p-6 pt-0 ${className}`} {...props} /> }
