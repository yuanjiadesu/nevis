import type { ComponentPropsWithRef, ReactNode } from "react";

import { FilterIcon, SearchIcon } from "./icons";

type ButtonProps = ComponentPropsWithRef<"button"> & {
  kind?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
  icon?: ReactNode;
};

export function Button({ kind = "primary", size = "md", icon, className, children, type = "button", ...rest }: ButtonProps) {
  const classes = ["btn", `btn--${kind}`, `btn--${size}`, children == null ? "btn--icon-only" : "", className]
    .filter(Boolean)
    .join(" ");
  return (
    <button type={type} className={classes} {...rest}>
      {icon}
      {children == null ? null : <span>{children}</span>}
    </button>
  );
}

export function Tag({ tone = "neutral", children }: { tone?: "neutral" | "positive" | "negative" | "info" | "accent"; children: ReactNode }) {
  return <span className={`tag tag--${tone}`}>{children}</span>;
}

export function Spinner({ label }: { label: string }) {
  return (
    <p className="spinner">
      <span className="spinner__ring" aria-hidden="true" />
      {label}
    </p>
  );
}

export function Skeleton({ heading = false, lines = 3 }: { heading?: boolean; lines?: number }) {
  return (
    <div className="skeleton" aria-hidden="true">
      {heading ? <span className="skeleton__bar skeleton__bar--heading" /> : null}
      {Array.from({ length: lines }, (_, index) => (
        <span key={index} className="skeleton__bar" />
      ))}
    </div>
  );
}

type FieldProps = { id: string; label: string; error?: string };

function Field({ id, label, error, children }: FieldProps & { children: ReactNode }) {
  return (
    <div className={error ? "field field--invalid" : "field"}>
      <label className="field__label" htmlFor={id}>{label}</label>
      {children}
      {error ? <p className="field__error" id={`${id}-error`} role="alert">{error}</p> : null}
    </div>
  );
}

export function TextField({ id, label, error, ...rest }: FieldProps & ComponentPropsWithRef<"input">) {
  return (
    <Field id={id} label={label} error={error}>
      <input
        id={id}
        className="field__input"
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        {...rest}
      />
    </Field>
  );
}

export function TextAreaField({ id, label, error, ...rest }: FieldProps & ComponentPropsWithRef<"textarea">) {
  return (
    <Field id={id} label={label} error={error}>
      <textarea
        id={id}
        className="field__input field__input--area"
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        {...rest}
      />
    </Field>
  );
}

export function SearchField({ label, glyph = "search", className, ...rest }: {
  label: string;
  glyph?: "search" | "filter";
} & ComponentPropsWithRef<"input">) {
  const Glyph = glyph === "filter" ? FilterIcon : SearchIcon;
  return (
    <div className={["search-field", className].filter(Boolean).join(" ")}>
      <Glyph className="search-field__glyph" size={16} aria-hidden="true" />
      <input type="search" aria-label={label} {...rest} />
    </div>
  );
}
