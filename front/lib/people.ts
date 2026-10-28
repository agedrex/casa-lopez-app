// Closed lists of the `persona` table (CHECK constraints of the DER). Labels only; the API validates the codes.
export const PERSON_ROLES = [
  { value: "CONSUMO_MOLDES", label: "Consumo y moldes" },
  { value: "CORTE", label: "Corte" },
  { value: "CONFECCION", label: "Confección" },
  { value: "VENTAS", label: "Ventas" },
  { value: "ENCARGADO", label: "Encargado" },
  { value: "ADMINISTRACION", label: "Administración" },
  { value: "OTRO", label: "Otro" },
] as const;

export const PERSON_LINKS = [
  { value: "SUELDO_FIJO", label: "Sueldo fijo" },
  { value: "OTRO", label: "Otro" },
] as const;

export function personRoleLabel(code: string): string {
  return PERSON_ROLES.find((item) => item.value === code)?.label ?? code;
}
