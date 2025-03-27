import type React from "react"
import Link from "next/link"
import { cn } from "@/lib/utils"

interface NavItemProps {
  icon: React.ReactNode
  href: string
  active?: boolean
}

export function NavItem({ icon, href, active }: NavItemProps) {
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center justify-center h-10 w-10 rounded-md transition-colors",
        active
          ? "bg-primary text-primary-foreground"
          : "text-muted-foreground hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-foreground",
      )}
    >
      {icon}
    </Link>
  )
}

