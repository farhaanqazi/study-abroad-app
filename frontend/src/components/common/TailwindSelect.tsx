import React, { forwardRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { AlertCircle, ChevronDown } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export interface SelectOption {
  value: string | number;
  label: string;
}

export interface TailwindSelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  label?: string;
  error?: string;
  helperText?: string;
  options: SelectOption[];
  placeholder?: string;
}

const TailwindSelect = forwardRef<HTMLSelectElement, TailwindSelectProps>(
  ({ className, label, error, helperText, options, placeholder = 'Select an option', disabled, id, value, defaultValue, onChange, onFocus, onBlur, ...props }, ref) => {
    const defaultId = React.useId();
    const selectId = id || defaultId;

    const [isFocused, setIsFocused] = React.useState(false);
    const [hasValue, setHasValue] = React.useState(!!value || !!defaultValue);

    const handleFocus = (e: React.FocusEvent<HTMLSelectElement>) => {
      setIsFocused(true);
      if (onFocus) onFocus(e);
    };

    const handleBlur = (e: React.FocusEvent<HTMLSelectElement>) => {
      setIsFocused(false);
      setHasValue(!!e.target.value);
      if (onBlur) onBlur(e);
    };

    const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
      setHasValue(!!e.target.value);
      if (onChange) onChange(e);
    };

    const isFloating = isFocused || hasValue;
    const borderColor = error ? 'border-red-300' : 'border-neutral-300';
    const focusColor = error ? 'focus:border-red-500' : 'focus:border-blue-500';

    return (
      <div className={cn('relative flex flex-col gap-1.5 w-full', className)}>
        <div className="relative">
          <select
            id={selectId}
            ref={ref}
            disabled={disabled}
            value={value}
            defaultValue={defaultValue}
            onChange={handleChange}
            onFocus={handleFocus}
            onBlur={handleBlur}
            className={cn(
              'peer relative w-full bg-white px-4 py-2.5 pr-10 text-base text-neutral-900 transition-all rounded-lg border appearance-none',
              borderColor,
              focusColor,
              'focus:outline-none disabled:bg-neutral-100 disabled:text-neutral-500 disabled:cursor-not-allowed',
            )}
            {...props}
          >
            {placeholder && !value && !defaultValue && (
              <option value="">{placeholder}</option>
            )}
            {options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>

          {/* Chevron Icon */}
          <ChevronDown
            size={18}
            className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-neutral-500 transition-colors peer-focus:text-neutral-700"
          />

          {label && (
            <label
              htmlFor={selectId}
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

TailwindSelect.displayName = 'TailwindSelect';

export default TailwindSelect;
