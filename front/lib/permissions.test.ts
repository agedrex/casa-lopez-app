import assert from "node:assert/strict";
import { test } from "node:test";
import {
  armarLineas,
  filasDeHoja,
  modoDeHoja,
  puedeSubirFoto,
} from "./formularios";
import { desktopNavForRole, mobileTabs, navForRole } from "./nav";
import {
  canAccessPath,
  canFillFormularios,
  homePath,
  isTallerOnly,
} from "./permissions";

test("gerente opens nothing under /admin, not even the Panel (S8)", () => {
  for (const path of [
    "/admin",
    "/admin/panel",
    "/admin/usuarios",
    "/admin/impuestos",
    "/admin/negocio",
    "/admin/sync",
    "/admin/panel/otro",
  ]) {
    assert.equal(canAccessPath("gerente", path), false, path);
  }
});

test("taller and users without a role are refused the Panel", () => {
  assert.equal(canAccessPath("taller", "/admin/panel"), false);
  assert.equal(canAccessPath(null, "/admin/panel"), false);
});

test("admin opens the whole admin area", () => {
  assert.equal(canAccessPath("admin", "/admin/panel"), true);
  assert.equal(canAccessPath("admin", "/admin/usuarios"), true);
});

test("gerente opens Productos, Modelos and the scenario simulator", () => {
  for (const path of [
    "/productos",
    "/productos/PRD-1",
    "/productos/modelos",
    "/productos/modelos/MOD-1",
    "/escenarios",
  ]) {
    assert.equal(canAccessPath("gerente", path), true, path);
  }
});

test("gerente is refused Lotes, Cueros, Proveedores, Talleres and every write form", () => {
  for (const path of [
    "/fabricacion",
    "/fabricacion/LOT-1",
    "/cueros",
    "/cueros/PZC-1",
    "/proveedores",
    "/proveedores/PRV-1",
    "/talleres",
    "/talleres/TAL-1",
    "/fabricacion/nuevo",
    "/talleres/nuevo",
    "/productos/nuevo",
    "/productos/modelos/nuevo",
    "/materiales",
    "/costos-fijos",
    "/corte",
    "/voz",
  ]) {
    assert.equal(canAccessPath("gerente", path), false, path);
  }
});

test("gerente lands on /productos", () => {
  assert.equal(homePath("gerente"), "/productos");
  assert.equal(homePath("consulta"), "/productos");
});

test("taller and users without a role are refused the scenario simulator; admin opens it", () => {
  assert.equal(canAccessPath("taller", "/escenarios"), false);
  assert.equal(canAccessPath(null, "/escenarios"), false);
  assert.equal(canAccessPath("admin", "/escenarios"), true);
});

test("taller opens lots, Voz, the product sheet and the two model sheet screens only", () => {
  for (const path of [
    "/fabricacion",
    "/fabricacion/LOT-1",
    "/voz",
    "/productos/PRD-1",
    "/taller/modelos",
    "/taller/modelos/FCO-0001",
  ]) {
    assert.equal(canAccessPath("taller", path), true, path);
  }
  for (const path of [
    "/productos",
    "/productos/modelos",
    "/productos/modelos/MOD-1",
    "/productos/nuevo",
    "/productos/modelos/nuevo",
    "/fabricacion/nuevo",
    "/formularios",
    "/formularios/FCO-1",
    "/taller",
    "/tallerx/modelos",
    "/corte",
    "/cueros",
    "/cueros/PZC-1",
    "/materiales",
    "/talleres",
    "/proveedores",
    "/costos-fijos",
    "/escenarios",
    "/admin/panel",
  ]) {
    assert.equal(canAccessPath("taller", path), false, path);
  }
});

test("the model photo route (an <img> source) is open to the three roles and closed without a role", () => {
  for (const role of ["admin", "gerente", "taller", "consulta", "corte"]) {
    assert.equal(canAccessPath(role, "/api/modelos/MOD-0001/foto"), true, role);
  }
  assert.equal(canAccessPath(null, "/api/modelos/MOD-0001/foto"), false);
  assert.equal(canAccessPath("otro", "/api/modelos/MOD-0001/foto"), false);
});

test("opening the photo route does not open any other /api path to gerente or taller", () => {
  for (const role of ["gerente", "taller"]) {
    for (const path of [
      "/api",
      "/api/otro",
      "/api/modelo",
      "/api/proveedores/PRV-1",
    ]) {
      assert.equal(canAccessPath(role, path), false, `${role} ${path}`);
    }
  }
});

test("taller lands on the lots list", () => {
  assert.equal(homePath("taller"), "/fabricacion");
  assert.equal(homePath("corte"), "/fabricacion");
});

test("a user with admin and taller keeps the admin access (the taller holes do not apply)", () => {
  for (const path of [
    "/productos",
    "/productos/modelos",
    "/corte",
    "/fabricacion/nuevo",
  ]) {
    assert.equal(canAccessPath("taller,admin", path), true, path);
  }
});

test("the gerente menu lists only Productos, Modelos and Escenarios, and each entry is a path it can open", () => {
  const hrefs = (groups: { items: { href: string }[] }[]) =>
    groups.flatMap((group) => group.items.map((item) => item.href));
  for (const groups of [
    desktopNavForRole(["gerente"]),
    navForRole(["gerente"]),
  ]) {
    assert.deepEqual(hrefs(groups), [
      "/productos",
      "/productos/modelos",
      "/escenarios",
    ]);
    for (const href of hrefs(groups)) {
      assert.equal(canAccessPath("gerente", href), true, href);
    }
  }
  const tabs = mobileTabs(navForRole(["gerente"]), ["gerente"]);
  assert.deepEqual(
    tabs.map((tab) => tab.href),
    ["/productos", "/escenarios"],
  );
});

test("the gerente and users without a role are refused the new model screens; admin opens them", () => {
  for (const path of ["/taller/modelos", "/taller/modelos/FCO-0001"]) {
    assert.equal(canAccessPath("gerente", path), false, path);
    assert.equal(canAccessPath("consulta", path), false, path);
    assert.equal(canAccessPath(null, path), false, path);
    assert.equal(canAccessPath("admin", path), true, path);
    assert.equal(canAccessPath("taller", path), true, path);
  }
});

test("only admin and taller may fill sheets", () => {
  assert.equal(canFillFormularios("admin"), true);
  assert.equal(canFillFormularios("taller"), true);
  assert.equal(canFillFormularios("corte"), true);
  assert.equal(canFillFormularios("cotizador"), true);
  assert.equal(canFillFormularios("gerente"), false);
  assert.equal(canFillFormularios("consulta"), false);
  assert.equal(canFillFormularios(null), false);
});

test("the admin menu has no Hojas de consumos entry and the taller menu is the single Lotes y modelos entry", () => {
  const hrefs = (groups: { items: { href: string }[] }[]) =>
    groups.flatMap((group) => group.items.map((item) => item.href));
  assert.ok(!hrefs(desktopNavForRole(["admin"])).includes("/taller/modelos"));
  assert.ok(!hrefs(navForRole(["admin"])).includes("/taller/modelos"));
  assert.equal(canAccessPath("admin", "/taller/modelos"), true);
  assert.equal(canAccessPath("admin", "/taller/modelos/FCO-0001"), true);
  for (const groups of [
    desktopNavForRole(["taller"]),
    navForRole(["taller"]),
  ]) {
    assert.deepEqual(hrefs(groups), ["/fabricacion"]);
  }
  for (const groups of [
    desktopNavForRole(["gerente"]),
    navForRole(["gerente"]),
  ]) {
    assert.ok(!hrefs(groups).some((href) => href.startsWith("/taller")));
  }
});

test("the taller menu is one ungrouped entry, Lotes y modelos, active on both /fabricacion and /taller/modelos", () => {
  for (const groups of [
    desktopNavForRole(["taller"]),
    navForRole(["taller"]),
  ]) {
    assert.equal(groups.length, 1);
    assert.equal(groups[0].title, "");
    assert.equal(groups[0].items.length, 1);
    const [item] = groups[0].items;
    assert.equal(item.href, "/fabricacion");
    assert.equal(item.label, "Lotes y modelos");
    assert.deepEqual(item.alsoActiveOn, ["/taller/modelos"]);
    for (const path of [item.href, ...(item.alsoActiveOn ?? [])]) {
      assert.equal(canAccessPath("taller", path), true, path);
    }
  }
  const tabs = mobileTabs(navForRole(["taller"]), ["taller"]);
  assert.deepEqual(
    tabs.map((tab) => tab.href),
    ["/fabricacion"],
  );
});

test("Impuestos is an admin entry of Costos variables, not of the admin tabs", () => {
  const costosVariables = desktopNavForRole(["admin"]).find(
    (group) => group.title === "Costos variables",
  );
  assert.ok(costosVariables, "the Costos variables group is missing");
  const impuestos = costosVariables.items.find(
    (item) => item.label === "Impuestos",
  );
  assert.equal(impuestos?.href, "/costos-fijos/impuestos");
  assert.equal(canAccessPath("admin", "/costos-fijos/impuestos"), true);
  for (const role of ["gerente", "taller", null]) {
    assert.equal(
      canAccessPath(role, "/costos-fijos/impuestos"),
      false,
      `${role}`,
    );
    assert.equal(
      desktopNavForRole(role ? [role as "gerente" | "taller"] : []).some(
        (group) => group.items.some((item) => item.label === "Impuestos"),
      ),
      false,
      `${role}`,
    );
  }
});

test("taller is a taller-only user; admin is not", () => {
  assert.equal(isTallerOnly("taller"), true);
  assert.equal(isTallerOnly("corte"), true);
  assert.equal(isTallerOnly("taller,admin"), false);
  assert.equal(isTallerOnly("gerente"), false);
});

test("admin and gerente matrices hold; taller cannot reach admin-only product paths", () => {
  for (const p of [
    "/productos",
    "/productos/modelos",
    "/escenarios",
    "/productos/PRD-1",
  ]) {
    assert.equal(canAccessPath("gerente", p), true, p);
  }
  for (const p of [
    "/fabricacion",
    "/corte",
    "/cueros",
    "/materiales",
    "/proveedores",
    "/admin/panel",
  ]) {
    assert.equal(canAccessPath("gerente", p), false, p);
  }
  for (const p of [
    "/productos/modelos",
    "/productos/nuevo",
    "/fabricacion/nuevo",
    "/materiales",
    "/talleres",
  ]) {
    assert.equal(canAccessPath("taller", p), false, p);
  }
  assert.equal(homePath("gerente,taller"), "/productos");
});

// --- The sheet screens (lib/formularios.ts) ---------------------------------------------------------------------------

test("the taller edits a sheet only while it is ENVIADO; the admin reviews a COMPLETADO one; everything else is read only", () => {
  const estados = ["BORRADOR", "ENVIADO", "COMPLETADO", "VALIDADO"] as const;
  assert.deepEqual(
    estados.map((estado) => modoDeHoja("taller", estado)),
    ["leer", "editar", "leer", "leer"],
  );
  assert.deepEqual(
    estados.map((estado) => modoDeHoja("admin", estado)),
    ["leer", "leer", "revisar", "leer"],
  );
  // Admin wins when a user holds both roles; a gerente never edits.
  assert.equal(modoDeHoja("taller,admin", "ENVIADO"), "leer");
  assert.equal(modoDeHoja("gerente", "ENVIADO"), "leer");
});

test("a taller may add a photo while the sheet is ENVIADO or when it created it; admin always; gerente never", () => {
  assert.equal(puedeSubirFoto("taller", "ENVIADO", "otro", "yo"), true);
  assert.equal(puedeSubirFoto("taller", "VALIDADO", "yo", "yo"), true);
  assert.equal(puedeSubirFoto("taller", "COMPLETADO", "otro", "yo"), false);
  assert.equal(puedeSubirFoto("admin", "VALIDADO", "otro", "yo"), true);
  assert.equal(puedeSubirFoto("gerente", "ENVIADO", "yo", "yo"), false);
});

test("the rows go to the API as typed: empty is null, comma and dot are the same, a bad number is refused with its row", () => {
  const fila = (cantidad: string, extra = {}) => ({
    seccion: "CONSUMO" as const,
    nombre: "CUERO",
    cantidad,
    comentario: "",
    ...extra,
  });
  assert.deepEqual(
    armarLineas([
      fila(""),
      fila("0,25"),
      fila("0.5", { comentario: " dos tapas " }),
    ]),
    {
      ok: true,
      lineas: [
        {
          seccion: "CONSUMO",
          nombre: "CUERO",
          cantidad: null,
          comentario: null,
        },
        {
          seccion: "CONSUMO",
          nombre: "CUERO",
          cantidad: "0.25",
          comentario: null,
        },
        {
          seccion: "CONSUMO",
          nombre: "CUERO",
          cantidad: "0.5",
          comentario: "dos tapas",
        },
      ],
    },
  );
  const mala = armarLineas([fila("1.234,5")]);
  assert.equal(mala.ok, false);
  assert.match(
    mala.ok ? "" : mala.message,
    /CUERO: la cantidad no es un número válido/,
  );
  const sinNombre = armarLineas([fila("1", { nombre: "   " })]);
  assert.equal(sinNombre.ok, false);
});

test("the API quantities come back to the editor as a person types them", () => {
  const [fila] = filasDeHoja([
    {
      seccion: "HERRAJE",
      orden: 1,
      nombre: "CIERRE N5",
      cantidad: "2.000000",
      comentario: null,
    },
  ]);
  assert.deepEqual(fila, {
    seccion: "HERRAJE",
    nombre: "CIERRE N5",
    cantidad: "2",
    comentario: "",
  });
  assert.equal(
    filasDeHoja([
      {
        seccion: "CONSUMO",
        orden: 1,
        nombre: "CUERO",
        cantidad: "0.250000",
        comentario: "x",
      },
    ])[0].cantidad,
    "0,25",
  );
});

test("the mobile menu uses the same groups and order as the desktop sidebar", () => {
  for (const roles of [["admin"], ["gerente"], ["taller"]] as const) {
    assert.deepEqual(navForRole([...roles]), desktopNavForRole([...roles]));
  }
  const titles = navForRole(["admin"]).map((group) => group.title);
  assert.deepEqual(titles, [
    "",
    "Producción",
    "Abastecimiento",
    "Costos fijos",
    "Costos variables",
    "Simulador",
  ]);
  const tabs = mobileTabs(navForRole(["admin"]), ["admin"]);
  assert.deepEqual(
    tabs.map((tab) => tab.href),
    ["/admin/panel", "/productos", "/fabricacion"],
  );
});
