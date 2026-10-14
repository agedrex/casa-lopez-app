import { createAccessControl } from "better-auth/plugins/access";

const statements = {
  application: ["admin"],
} as const;

export const adminAccessControl = createAccessControl(statements);

export const adminRole = adminAccessControl.newRole({
  application: ["admin"],
});

export const userRole = adminAccessControl.newRole({
  application: [],
});
