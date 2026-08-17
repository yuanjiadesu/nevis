import type { ReactNode } from "react";

export function TableCard({ toolbar, children }: { toolbar?: ReactNode; children: ReactNode }) {
  return (
    <section className="table-card">
      {toolbar ? <div className="table-card__toolbar">{toolbar}</div> : null}
      <div className="table-card__scroll">{children}</div>
    </section>
  );
}

export function SectionHeading({ title, meta }: { title: string; meta?: string }) {
  return (
    <header className="section-heading">
      <h2>{title}</h2>
      {meta ? <p>{meta}</p> : null}
    </header>
  );
}

export function TableEmpty({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="table-empty">
      {icon}
      <p>{title}</p>
      {children}
    </div>
  );
}
