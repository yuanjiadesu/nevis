import { Dialog as Base } from "@base-ui/react/dialog";
import { useId, type FormEvent, type ReactNode, type RefObject } from "react";

import { CloseIcon } from "./icons";
import { Button } from "./primitives";

type Focusable = RefObject<HTMLElement | null>;

type ShellProps = {
  open: boolean;
  onClose: () => void;
  label?: string;
  heading: string;
  size?: "sm" | "md" | "lg";
  align?: "center" | "top";
  className?: string;
  initialFocus?: Focusable;
  finalFocus?: Focusable;
  children: ReactNode;
};

function DialogShell({
  open,
  onClose,
  label,
  heading,
  size = "md",
  align = "center",
  className,
  initialFocus,
  finalFocus,
  body,
  footer,
}: Omit<ShellProps, "children"> & { body: ReactNode; footer: ReactNode }) {
  return (
    <Base.Root open={open} onOpenChange={(next) => { if (!next) onClose(); }}>
      <Base.Portal>
        <Base.Backdrop className="dialog__backdrop" />
        <Base.Popup
          className={["dialog", `dialog--${size}`, `dialog--${align}`, className].filter(Boolean).join(" ")}
          initialFocus={initialFocus}
          finalFocus={finalFocus}
        >
          <header className="dialog__header">
            <div className="dialog__headings">
              {label ? <p className="product-label">{label}</p> : null}
              <Base.Title className="dialog__title">{heading}</Base.Title>
            </div>
            <Base.Close render={<button type="button" className="dialog__dismiss" aria-label="Close dialog" />}>
              <CloseIcon size={18} />
            </Base.Close>
          </header>
          {body}
          <footer className="dialog__footer">{footer}</footer>
        </Base.Popup>
      </Base.Portal>
    </Base.Root>
  );
}

export function Dialog({ children, closeLabel = "Close", ...shell }: ShellProps & { closeLabel?: string }) {
  return (
    <DialogShell
      {...shell}
      body={<div className="dialog__body">{children}</div>}
      footer={<Button kind="secondary" size="sm" onClick={shell.onClose}>{closeLabel}</Button>}
    />
  );
}

export function FormDialog({
  children,
  submitLabel,
  cancelLabel = "Cancel",
  busy = false,
  onSubmit,
  ...shell
}: ShellProps & {
  submitLabel: string;
  cancelLabel?: string;
  busy?: boolean;
  onSubmit: () => void;
}) {
  const formId = useId();
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit();
  };
  return (
    <DialogShell
      {...shell}
      body={<form id={formId} className="dialog__body" onSubmit={submit}>{children}</form>}
      footer={
        <>
          <Button kind="secondary" size="md" onClick={shell.onClose}>{cancelLabel}</Button>
          <Button type="submit" form={formId} size="md" disabled={busy}>{submitLabel}</Button>
        </>
      }
    />
  );
}
