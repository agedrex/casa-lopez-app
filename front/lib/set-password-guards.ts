// Guards for scripts/set-password.ts. Pure text and environment checks, kept apart from
// the script so they can be tested: the script itself runs main() as soon as it is imported.
// No server-only import, no database, no Better Auth.

export const ENTORNOS = ["staging", "production"] as const;
export type Entorno = (typeof ENTORNOS)[number];

export type Options = {
  email: string | null;
  entorno: string | null;
  confirmar: boolean;
};

/**
 * Reads `--email <v>`, `--entorno <v>` and `--confirmar`. Anything unexpected is ignored,
 * which always lands on the safe side: without a valid `--entorno` and `--confirmar` the
 * script stays a dry-run. A flag used as a value (`--email --confirmar`) is not consumed,
 * so the option stays null and the caller rejects it.
 */
export function parseArgs(argv: string[]): Options {
  const options: Options = { email: null, entorno: null, confirmar: false };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--confirmar") {
      options.confirmar = true;
      continue;
    }
    if (arg !== "--email" && arg !== "--entorno") continue;
    const value = argv[index + 1];
    if (value === undefined || value.startsWith("--")) continue;
    if (arg === "--email") options.email = value;
    else options.entorno = value;
    index += 1;
  }
  return options;
}

export function isEntorno(value: string | null): value is Entorno {
  return ENTORNOS.includes(value as Entorno);
}

/**
 * Whether the requested environment matches where this is running. The Railway value is
 * compared but never returned in the message.
 *
 * This is a guard against mistakes, not a security control: whoever can set
 * RAILWAY_ENVIRONMENT_NAME already has the production DATABASE_URL and secret.
 * Same reasoning as backend/scripts/importar_productos.py.
 */
export function environmentProblem(
  entorno: Entorno,
  railway: string | undefined,
): string | null {
  if (railway === undefined || railway === "") {
    // SUPUESTO: production solo se escribe desde dentro de su contenedor (o con las
    // variables de production inyectadas), como en importar_productos.py.
    if (entorno === "production") {
      return "No se cambió nada: production solo se escribe con el entorno de production inyectado (RAILWAY_ENVIRONMENT_NAME no está definida).";
    }
    return null;
  }
  if (railway !== entorno) {
    return `No se cambió nada: el entorno de Railway no coincide con --entorno ${entorno}.`;
  }
  return null;
}
