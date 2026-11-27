/**
 * Railway Infrastructure as Code for the casa-lopez project.
 *
 * This replaces `backend/railway.toml` (Config as Code), which Railway stops reading on
 * 2027-01-01. Generated with `railway config pull` and then edited by hand, because the
 * two environments are NOT symmetric: the same resources carry different names, and the
 * backend and frontend deploy differently. Every difference below is deliberate and was
 * read from the live config of each environment on 2026-11-27, not invented.
 *
 * | What                   | staging                      | production                   |
 * |------------------------|------------------------------|------------------------------|
 * | Postgres service       | `Postgres`                   | `Postgres-rZDV`              |
 * | Private endpoint       | `postgres`                   | `postgres-rzdv`              |
 * | Volume                 | `postgres-volume`            | `postgres-volume-2bd2`       |
 * | backend/frontend source| branch main, CI-gated        | no branch: deploys by hand   |
 * | Dollar cron service    | `dolar-cron`                 | `dolar-cron-production`      |
 *
 * Two things that look like mistakes and are kept on purpose, so that migrating changes
 * nothing. Both deserve their own decision, separately from this migration:
 *
 *  1. The production dollar cron carries `healthcheck`, `healthcheckTimeout` and
 *     `preDeploy`. It inherited them from `backend/railway.toml`, which Railway reads for
 *     every service whose root directory is `/backend`. A cron serves no HTTP, so the
 *     healthcheck makes little sense, and running `alembic upgrade head` from the cron is
 *     a second path that migrates the database. Staging does not have any of it.
 *  2. `postgres-volume-tOuD` exists in production and is mounted nowhere. It is most
 *     likely left over from a backup restore, which leaves the previous volume unmounted.
 *     It is declared here ONLY so that `railway config apply` does not delete it. Confirm
 *     what it is before removing it: `apply` deletes any volume this file omits.
 *
 * `variables: { managed: false }` keeps every variable on Railway. IaC never reads or
 * writes them, so no secret (DATABASE_URL, BETTER_AUTH_SECRET, ANTHROPIC_API_KEY) can end
 * up in this repository or be deleted by an apply.
 *
 * Railway does NOT read this file during a deploy. It is applied explicitly, per
 * environment, with `railway config plan` and `railway config apply`.
 */
import { defineRailway, github, postgres, project, service, volume } from "railway/iac";

export default defineRailway((ctx) => {
  const prod = ctx.environment === "production";

  // The database and its volume: same shape, different names per environment.
  const db = postgres(prod ? "Postgres-rZDV" : "Postgres", {
    region: "us-east4-eqdc4a",
  });
  db.deploy = { multiRegionConfig: { "us-east4-eqdc4a": { numReplicas: 1 } } };
  db.networking = {
    privateNetworkEndpoint: prod ? "postgres-rzdv" : "postgres",
  };

  const volumeAlerts = { usage: { "100": {}, "80": {}, "95": {} } };
  const dbVolume = volume(prod ? "postgres-volume-2bd2" : "postgres-volume", {
    alerts: volumeAlerts,
    allowOnlineResize: true,
    region: "us-east4-eqdc4a",
    sizeMB: 50000,
  });

  // Production only: unmounted leftover, declared so apply does not delete it (note 2).
  const orphanVolume = prod
    ? volume("postgres-volume-tOuD", {
        alerts: volumeAlerts,
        allowOnlineResize: true,
        region: "us-east4-eqdc4a",
        sizeMB: 50000,
      })
    : null;

  // Staging follows main and waits for the GitHub checks; production has no branch, which
  // is what keeps its auto-deploy off: it is promoted by hand with `railway redeploy`.
  const appSource = (rootDirectory: string) =>
    prod
      ? github("agedrex/casa-lopez-app", { rootDirectory })
      : github("agedrex/casa-lopez-app", {
          branch: "main",
          checkSuites: true,
          rootDirectory,
        });

  const build = { buildEnvironment: "V3", builder: "RAILPACK" } as const;
  const replicas = { "us-east4-eqdc4a": 1 } as const;

  const frontend = service("frontend", {
    source: appSource("/front"),
    build,
    replicas,
  });

  const backend = service("backend", {
    source: appSource("/backend"),
    build,
    start:
      "uv run fastapi run src/backend/main.py --host 0.0.0.0 --port $PORT",
    healthcheck: "/api/health",
    healthcheckTimeout: 120,
    // The pre-deploy migration: it runs after the build and before the new deployment
    // starts, and a non-zero exit stops the deploy. This is the setting that most needed
    // to survive the move off railway.toml.
    preDeploy: "uv run alembic upgrade head",
    replicas,
  });

  const dolarCron = service(prod ? "dolar-cron-production" : "dolar-cron", {
    source: github("agedrex/casa-lopez-app", {
      branch: "main",
      checkSuites: false,
      rootDirectory: "/backend",
    }),
    build,
    start: "uv run python -m backend.actualizar_dolar",
    replicas,
    deploy: { cronSchedule: "0 12 * * 1-5", restartPolicyType: "NEVER" },
    // Inherited from backend/railway.toml in production only (note 1). Kept so that the
    // migration changes nothing; revisit it as its own decision.
    ...(prod
      ? {
          healthcheck: "/api/health",
          healthcheckTimeout: 120,
          preDeploy: "uv run alembic upgrade head",
        }
      : {}),
  });

  return project("casa-lopez", {
    variables: { managed: false },
    resources: [
      frontend,
      db,
      backend,
      dolarCron,
      dbVolume,
      ...(orphanVolume ? [orphanVolume] : []),
    ],
  });
});
