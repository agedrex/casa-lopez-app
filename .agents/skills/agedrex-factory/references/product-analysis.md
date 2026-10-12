# Product analysis as enrichment, not a parallel model

La Fábrica is authoritative for identity and lifecycle: Etapa → FRD (`documents` with
`kind=requirement`, `doc_type=feature`) → Feature Blueprint (`kind=blueprint`) → linked WO.
Do not create separate epic, story or feature entities to mirror these records.

When useful, incorporate product-analysis practices into the existing artifacts:

| Practice | Place in La Fábrica |
|---|---|
| JTBD and user needs | FRD problem/context and observable REQ/AC |
| BDD scenarios | WO acceptance criteria, traced to FRD AC |
| Technical project brief | Blueprint contracts and ADRs |
| Roadmap and capacity | Etapa planning when actual data exists |

Before finalizing a FRD, check strategic alignment, missing validation/permission/recovery AC,
traceability (each AC belongs to one REQ), and stable IDs. Epic coverage can inform a
requirement boundary but never becomes a separate database entity. Prefer a vertical WO slice
when one delivery owner spans the stack; use layered WOs only when ownership really differs.
Mark missing product decisions explicitly rather than inventing behavior.

Keep source attribution when adapting third-party material. Do not copy confidential or
restricted templates into the skill. See `guides/flujo-de-trabajo.md` for the authoritative path.
