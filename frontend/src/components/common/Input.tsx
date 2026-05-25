/*
 * DESIGN DECISIONS
 * Layout: Floating label pattern to avoid placeholders acting as labels (WCAG strict).
 * Colors: Glow on focus matches the Dark Craft accent token. Background is surface-overlay.
 * Motion: Height animation for error messages. Label scales and translates on focus/fill.
 * Unusual choices: Uses AnimatePresence for the error text to prevent jumping.
 */
import React, { forwardRef, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { AlertCircle, CheckCircle2 } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  isSuccess?: boolean;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, isSuccess, disabled, id, value, defaultValue, onChange, onFocus, onBlur, ...props }, ref) => {
    const defaultId = React.useId();
    const inputId = id || defaultId;
    
    const [isFocused, setIsFocused] = useState(false);
    // Determine if input has value (controlled or uncontrolled)
    const [hasValue, setHasValue] = useState(!!value || !!defaultValue);

    const handleFocus = (e: React.FocusEvent<HTMLInputElement>) => {
      setIsFocused(true);
      if (onFocus) onFocus(e);
    };

    const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
      setIsFocused(false);
      setHasValue(!!e.target.value);
      if (onBlur) onBlur(e);
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      setHasValue(!!e.target.value);
      if (onChange) onChange(e);
    };

    const isFloating = isFocused || hasValue || props.type === "date";
    const showSuccess = isSuccess && !error && hasValue;

    return (
      <div className={cn("relative flex flex-col gap-1.5 w-full", className)}>
        <div className="relative">
          <input
            id={inputId}
            ref={ref}
            disabled={disabled}
            value={value}
            defaultValue={defaultValue}
            onFocus={handleFocus}
            onBlur={handleBlur}
            onChange={handleChange}
            className={cn(
              "peer w-full h-[52px] px-4 pt-4 pb-1 rounded-[var(--radius-md)]",
              "bg-[var(--color-surface-overlay)] text-white border transition-all duration-[var(--duration-normal)] outline-none",
              error
                ? "border-[color:var(--color-danger)] focus:border-[color:var(--color-danger)] focus:shadow-[0_0_0_2px_rgba(239,68,68,0.2)]"
                : showSuccess
                ? "border-[color:var(--color-success)]"
                : "border-[color:var(--color-neutral-800)] focus:border-[color:var(--color-accent)] focus:shadow-[var(--shadow-glow)]",
              disabled && "opacity-50 cursor-not-allowed",
              error && "animate-[shake_0.3s_ease-in-out]"
            )}
            placeholder=" " // Required for peer-placeholder-shown trick if wanted, but we use React state for better control
            {...props}
          />
          
          <label
            htmlFor={inputId}
            className={cn(
              "absolute left-4 transition-all duration-[var(--duration-fast)] pointer-events-none origin-left",
              isFloating 
                ? "text-xs top-2 text-[var(--color-neutral-400)]" 
                : "text-base top-3.5 text-[var(--color-neutral-500)]",
              error && isFloating && "text-[color:var(--color-danger)]",
              isFocused && !error && "text-[color:var(--color-accent)]"
            )}
          >
            {label}
          </label>

          <AnimatePresence>
            {showSuccess && (
              <motion.div
                initial={{ opacity: 0, scale: 0.5 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.5 }}
                className="absolute right-4 top-3.5 text-[color:var(--color-success)] pointer-events-none"
              >
                <CheckCircle2 className="w-5 h-5" />
              </motion.div>
            )}
            
            {error && !showSuccess && (
              <motion.div
                initial={{ opacity: 0, scale: 0.5 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.5 }}
                className="absolute right-4 top-3.5 text-[color:var(--color-danger)] pointer-events-none"
              >
                <AlertCircle className="w-5 h-5" />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="flex items-start gap-1.5 text-xs text-[color:var(--color-danger)] font-mono mt-0.5">
                <span>{error}</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    );
  }
);

Input.displayName = "Input";
export default Input;
