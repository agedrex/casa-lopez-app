export type AdminSection = {
  href: string;
  title: string;
  text: string;
  /** Key in ICONS (components/nav-icons.tsx). */
  icon: string;
};

export type AdminGroup = { title: string; sections: AdminSection[] };

/** The areas of the admin hub and the tabs of its sub-navigation, in one place so they never drift apart. */
export const ADMIN_GROUPS: AdminGroup[] = [
  {
    title: "Personas y accesos",
    sections: [
      {
        href: "/admin/usuarios",
        title: "Usuarios",
        text: "Quién entra a la aplicación, con qué rol, y desactivar o cambiar contraseñas.",
        icon: "/admin/usuarios",
      },
      {
        href: "/admin/personas",
        title: "Personas",
        text: "Quién cobra un sueldo o hace una tarea en la fábrica.",
        icon: "/admin/personas",
      },
    ],
  },
  {
    title: "Reglas del negocio",
    sections: [
      {
        href: "/admin/parametros",
        title: "Parámetros",
        text: "Tolerancias, arreglos y mes de costos fijos que lee el sistema al calcular.",
        icon: "/admin/parametros",
      },
      {
        href: "/admin/impuestos",
        title: "Impuestos",
        text: "Solo lectura: cómo se tratan el IVA, Ingresos Brutos y Ganancias.",
        icon: "/admin/impuestos",
      },
    ],
  },
  {
    title: "Catálogo",
    sections: [
      {
        href: "/admin/modelos",
        title: "Modelos",
        text: "Consumos de cada modelo, validación y alta de modelos nuevos.",
        icon: "/admin/modelos",
      },
      {
        href: "/admin/catalogos",
        title: "Catálogos",
        text: "Colores y categorías que se eligen al cargar productos y modelos.",
        icon: "/admin/catalogos",
      },
    ],
  },
  {
    title: "Integraciones",
    sections: [
      {
        href: "/admin/sync",
        title: "Google Sheets",
        text: "Copia para ver y consultar: simular o sincronizar las pestañas con el Sheet. Nada vuelve del Sheet a la app.",
        icon: "/admin/sync",
      },
    ],
  },
];
