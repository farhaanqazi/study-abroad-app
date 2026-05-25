import React, { forwardRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { AlertCircle } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export interface TailwindInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label?: string;
  error?: string;
  helperText?: string;
  multiline?: boolean;
  rows?: number;
}

const TailwindInput = forwardRef<HTMLInputElement | HTMLTextAreaElement, TailwindInputProps>(
  ({ className, label, error, helperText, disabled, id, value, defaultValue, onChange, onFocus, onBlur, multiline, rows, ...props }, ref) => {
    const defaultId = React.useId();
    const inputId = id || defaultId;

    const [isFocused, setIsFocused] = React.useState(false);
    const [hasValue, setHasValue] = React.useState(!!value || !!defaultValue);

    const handleFocus = (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      setIsFocused(true);
      if (onFocus) onFocus(e as React.FocusEvent<HTMLInputElement>);
    };

    const handleBlur = (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      setIsFocused(false);
      setHasValue(!!e.currentTarget.value);
      if (onBlur) onBlur(e as React.FocusEvent<HTMLInputElement>);
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      setHasValue(!!e.currentTarget.value);
      if (onChange) onChange(e as React.ChangeEvent<HTMLInputElement>);
    };

    const isFloating = isFocused || hasValue;
    const borderColor = error ? 'border-red-300' : 'border-neutral-300';
    const focusColor = error ? 'focus:border-red-500' : 'focus:border-blue-500';

    // Render textarea if multiline
    if (multiline) {
      return (
        <div className={cn('relative flex flex-col gap-1.5 w-full', className)}>
          <div className="relative">
            <textarea
              id={inputId}
              ref={ref as React.Ref<HTMLTextAreaElement>}
              disabled={disabled}
              value={value}
              defaultValue={defaultValue}
              onChange={handleChange}
              onFocus={handleFocus}
              onBlur={handleBlur}
              rows={rows || 4}
              className={cn(
                'peer relative w-full bg-white px-4 py-2.5 text-base text-neutral-900 transition-all rounded-lg border',
                borderColor,
                focusColor,
                'placeholder-transparent focus:outline-none disabled:bg-neutral-100 disabled:text-neutral-500 disabled:cursor-not-allowed resize-none',
              )}
              {...(props as React.TextareaHTMLAttributes<HTMLTextAreaElement>)}
            />
            {label && (
              <label
                htmlFor={inputId}
                className={cn(
                  'absolute left-3 flex items-center transition-all pointer-events-none select-none',
                  isFloating
                    ? 'top-1 text-xs text-neutral-600'
                    : 'top-2.5 text-sm text-neutral-500 peer-focus:top-1 peer-focus:text-xs peer-focus:text-neutral-600',
                )}
              >
                {label}
              </label>
            )}
          </div>

          {/* Error message */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.15 }}
                className="flex items-center gap-1.5 text-xs text-red-600"
              >
                <AlertCircle size={14} className="flex-shrink-0" />
                <span>{error}</span>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Helper text */}
          {helperText && !error && (
            <p className="text-xs text-neutral-500">{helperText}</p>
          )}
        </div>
      );
    }

    // Render input
    return (
      <div className={cn('relative flex flex-col gap-1.5 w-full', className)}>
        <div className="relative">
          <input
            id={inputId}
            ref={ref as React.Ref<HTMLInputElement>}
            disabled={disabled}
            value={value}
            defaultValue={defaultValue}
            onChange={handleChange}
            onFocus={handleFocus}
            onBlur={handleBlur}
            className={cn(
              'peer relative w-full bg-white px-4 py-2.5 text-base text-neutral-900 transition-all rounded-lg border',
              borderColor,
              focusColor,
              'placeholder-transparent focus:outline-none disabled:bg-neutral-100 disabled:text-neutral-500 disabled:cursor-not-allowed',
            )}
            {...(props as React.InputHTMLAttributes<HTMLInputElement>)}
          />
          {label && (
            <label
              htmlFor={inputId}
              className={cn(
                'absolute left-3 flex items-center transition-all pointer-events-none select-none',
                isFloating
                  ? 'top-1 text-xs text-neutral-600'
                  : 'top-2.5 text-sm text-neutral-500 peer-focus:top-1 peer-focus:text-xs peer-focus:text-neutral-600',
              )}
            >
              {label}
            </label>
          )}
        </div>

        {/* Error message */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.15 }}
              className="flex items-center gap-1.5 text-xs text-red-600"
            >
              <AlertCircle size={14} className="flex-shrink-0" />
              <span>{error}</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Helper text */}
        {helperText && !error && (
          <p className="text-xs text-neutral-500">{helperText}</p>
        )}
      </div>
    );
  },
);

TailwindInput.displayName = 'TailwindInput';

export default TailwindInput;
