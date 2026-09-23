/**
 * DAX_PPT_SKILL - Pi extension entry.
 *
 * Points Pi at the shared skill core. The skill is plain files
 * (skills/dax-ppt/SKILL.md + the dax.py CLI), so this file only locates them.
 */

import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

export const SKILL_ROOT: string = join(ROOT, "skills", "dax-ppt");
export const SKILL_MD: string = join(SKILL_ROOT, "SKILL.md");
export const CLI: string = join(SKILL_ROOT, "scripts", "dax.py");

export default {
  name: "dax-ppt-skill",
  description:
    "Build Data Axle presentations: consulting-grade HTML slides that export to " +
    "PowerPoint with editable text, native charts and native tables.",
  skills: [
    {
      id: "dax-ppt",
      path: SKILL_MD,
      root: SKILL_ROOT,
    },
  ],
};
