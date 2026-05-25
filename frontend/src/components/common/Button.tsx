/*
 * DESIGN DECISIONS
 * Font: Inherits from body (Outfit Variable) with Medium weight.
 * Color: Primary variant uses Dark Craft's accented near-black approach.
 * Motion: Uses Spring scaling on active (0.97), and fast transition for hovers.
 * Unusual choices: Width-locking mechanism using a ref and state to prevent layout shift when changing from text to a loading spinner.
 */
import React, { forwardRef, useState, useRef, useEffect, type ReactNode } from 'react';
import { Loader2, Check } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { motion, AnimatePresence } from 'motion/react';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export interface ButtonProps extends React.ComponentProps<typeof motion.button> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'destructive' | 'icon-only';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  isSuccess?: boolean;
  icon?: React.ReactNode;
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', isLoading, isSuccess, icon, children, disabled, ...props }, ref) => {
    const defaultRef = useRef<HTMLButtonElement>(null);
    const resolvedRef = (ref as React.RefObject<HTMLButtonElement>) || defaultRef;
    
    // Width locking for layout shift prevention during loading/success
    const [lockedWidth, setLockedWidth] = useState<number | undefined>(undefined);
    
    useEffect(() => {
      if ((isLoading || isSuccess) && resolvedRef.current && !lockedWidth) {
        setLockedWidth(resolvedRef.current.offsetWidth);
      } else if (!isLoading && !isSuccess) {
        setLockedWidth(undefined);
      }
    }, [isLoading, isSuccess, resolvedRef, lockedWidth]);

    const baseStyles = "relative inline-flex items-center justify-center whitespace-nowrap rounded-[var(--radius-md)] text-sm font-medium transition-all duration-[var(--duration-fast)] focus-ring disabled:pointer-events-none disabled:opacity-40 active:scale-[0.97] hover:-translate-y-px overflow-hidden";
    
    const variants = {
      primary: "bg-[var(--color-primary-100)] text-[var(--color-surface-base)] hover:bg-white shadow-[var(--shadow-sm)] hover:shadow-[var(--shadow-md)]",
      secondary: "bg-[var(--color-surface-overlay)] text-[var(--color-primary-100)] border border-[color:var(--color-neutral-800)] hover:bg-[var(--color-surface-floating)] shadow-[var(--shadow-xs)]",
      ghost: "hover:bg-[var(--color-surface-overlay)] text-[var(--color-primary-200)] hover:text-white",
      destructive: "bg-[color:var(--color-danger)]/10 text-[color:var(--color-danger)] hover:bg-[color:var(--color-danger)] hover:text-white border border-[color:var(--color-danger)]/20",
      "icon-only": "bg-[var(--color-surface-overlay)] text-[var(--color-primary-100)] hover:bg-[var(--color-surface-floating)] border border-[color:var(--color-neutral-800)] p-0",
    };

    const sizes = {
      sm: "h-8 px-3 text-xs",
      md: "h-10 px-4",
      lg: "h-12 px-6 text-base",
    };

    const sizeClass = variant === 'icon-only' 
      ? (size === 'sm' ? 'h-8 w-8' : size === 'lg' ? 'h-12 w-12' : 'h-10 w-10')
      : sizes[size];

    return (
      <motion.button
        ref={resolvedRef}
        className={cn(baseStyles, variants[variant], sizeClass, className)}
        disabled={disabled || isLoading || isSuccess}
        style={{ width: lockedWidth ? `${lockedWidth}px` : undefined }}
        whileTap={{ scale: 0.97 }}
        {...props}
      >
        <AnimatePresence mode="wait">
          {isLoading ? (
            <motion.div
              key="loading"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              className="absolute inset-0 flex items-center justify-center"
            >
              <Loader2 className="h-4 w-4 animate-spin" />
            </motion.div>
          ) : isSuccess ? (
            <motion.div
              key="success"
              initial={{ opacity: 0, scale: 0.5 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              className="absolute inset-0 flex items-center justify-center text-[color:var(--color-success)]"
            >
              <Check className="h-4 w-4" />
            </motion.div>
          ) : (
            <motion.div
              key="content"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex items-center gap-2"
            >
              {icon && <span className="shrink-0">{icon}</span>}
              {variant !== 'icon-only' && (children as ReactNode)}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.button>
    );
  }
);

Button.displayName = "Button";
export default Button;
