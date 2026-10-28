"use client";

import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
  SecondaryButton,
} from "@/components/form";
import { ROLE_LABELS, ROLES, type Role } from "@/lib/permissions";
import { useActionForm } from "@/lib/use-action-form";
import { changeRole, createUser, setBanned, setPassword } from "./actions";

function RoleOptions() {
  return ROLES.map((role) => (
    <option key={role} value={role}>
      {ROLE_LABELS[role]}
    </option>
  ));
}

export function CreateUserForm() {
  const { state, pending, formKey, onSubmit } = useActionForm(createUser);
  return (
    <form key={formKey} onSubmit={onSubmit} className="space-y-5">
      <p className="text-sm text-muted">
        La contraseña inicial la escribe usted y se la pasa a la persona. Nadie
        puede registrarse solo.
      </p>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="usuario-nombre" label="Nombre">
          <input
            id="usuario-nombre"
            name="name"
            required
            maxLength={120}
            autoComplete="off"
            className={inputClass}
          />
        </Field>
        <Field id="usuario-email" label="Correo">
          <input
            id="usuario-email"
            name="email"
            type="email"
            required
            autoComplete="off"
            className={inputClass}
          />
        </Field>
        <Field
          id="usuario-rol"
          label="Rol"
          hint="Consulta solo mira; cotizador carga datos; administrador además gestiona esta sección."
        >
          <select
            id="usuario-rol"
            name="role"
            required
            defaultValue="consulta"
            aria-describedby="usuario-rol-hint"
            className={inputClass}
          >
            <RoleOptions />
          </select>
        </Field>
        <div />
        <Field
          id="usuario-password"
          label="Contraseña inicial"
          hint="Al menos 12 caracteres, combinando tres de: minúsculas, mayúsculas, números y símbolos."
        >
          <input
            id="usuario-password"
            name="password"
            type="password"
            required
            minLength={12}
            autoComplete="new-password"
            aria-describedby="usuario-password-hint"
            className={inputClass}
          />
        </Field>
        <Field id="usuario-confirm" label="Repetir contraseña">
          <input
            id="usuario-confirm"
            name="confirm"
            type="password"
            required
            minLength={12}
            autoComplete="new-password"
            className={inputClass}
          />
        </Field>
      </div>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Creando…" : "Crear usuario"}
      </PrimaryButton>
    </form>
  );
}

export function RoleForm({
  userId,
  role,
  disabledReason,
}: {
  userId: string;
  role: Role | null;
  disabledReason: string | null;
}) {
  const { state, pending, onSubmit } = useActionForm(
    changeRole.bind(null, userId),
  );
  return (
    <form onSubmit={onSubmit} className="space-y-2">
      <Field id={`rol-${userId}`} label="Rol">
        <select
          id={`rol-${userId}`}
          name="role"
          defaultValue={role ?? "consulta"}
          disabled={disabledReason !== null}
          aria-describedby={disabledReason ? `rol-${userId}-hint` : undefined}
          className={inputClass}
        >
          <RoleOptions />
        </select>
      </Field>
      {disabledReason ? (
        <p id={`rol-${userId}-hint`} className="text-xs text-muted">
          {disabledReason}
        </p>
      ) : null}
      <FormFeedback state={state} />
      {disabledReason ? null : (
        <SecondaryButton pending={pending}>
          {pending ? "Guardando…" : "Cambiar rol"}
        </SecondaryButton>
      )}
    </form>
  );
}

export function BanForm({
  userId,
  banned,
  disabledReason,
}: {
  userId: string;
  banned: boolean;
  disabledReason: string | null;
}) {
  const { state, pending, onSubmit } = useActionForm(
    setBanned.bind(null, userId, !banned),
  );
  return (
    <form onSubmit={onSubmit} className="space-y-2">
      <p className="text-sm text-muted">
        {banned
          ? "Este usuario está desactivado y no puede iniciar sesión. Activarlo le devuelve el acceso."
          : "Desactivar cierra sus sesiones y le impide iniciar sesión. No se borra nada: se puede volver a activar."}
      </p>
      {disabledReason ? (
        <p className="text-xs text-muted">{disabledReason}</p>
      ) : null}
      <FormFeedback state={state} />
      {disabledReason ? null : (
        <SecondaryButton pending={pending}>
          {pending
            ? "Guardando…"
            : banned
              ? "Activar usuario"
              : "Desactivar usuario"}
        </SecondaryButton>
      )}
    </form>
  );
}

export function PasswordForm({ userId }: { userId: string }) {
  const { state, pending, formKey, onSubmit } = useActionForm(
    setPassword.bind(null, userId),
  );
  return (
    <form key={formKey} onSubmit={onSubmit} className="space-y-2">
      <Field
        id={`pass-${userId}`}
        label="Nueva contraseña"
        hint="Se cierran todas las sesiones abiertas de este usuario."
      >
        <input
          id={`pass-${userId}`}
          name="password"
          type="password"
          required
          minLength={12}
          autoComplete="new-password"
          aria-describedby={`pass-${userId}-hint`}
          className={inputClass}
        />
      </Field>
      <Field id={`confirm-${userId}`} label="Repetir contraseña">
        <input
          id={`confirm-${userId}`}
          name="confirm"
          type="password"
          required
          minLength={12}
          autoComplete="new-password"
          className={inputClass}
        />
      </Field>
      <FormFeedback state={state} />
      <SecondaryButton pending={pending}>
        {pending ? "Guardando…" : "Cambiar contraseña"}
      </SecondaryButton>
    </form>
  );
}
