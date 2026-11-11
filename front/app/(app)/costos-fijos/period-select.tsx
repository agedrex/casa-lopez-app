"use client";

import type { ReactNode } from "react";

/** Month picker that submits its GET form as soon as a month is chosen (no extra button). */
export function PeriodSelect({
  id,
  name,
  defaultValue,
  className,
  children,
}: {
  id: string;
  name: string;
  defaultValue: string;
  className: string;
  children: ReactNode;
}) {
  return (
    <select
      id={id}
      name={name}
      defaultValue={defaultValue}
      className={className}
      onChange={(event) => event.currentTarget.form?.requestSubmit()}
    >
      {children}
    </select>
  );
}
