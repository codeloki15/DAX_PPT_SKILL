/**
 * DAX_PPT_SKILL - opencode plugin entry.
 *
 * Registers the Data Axle presentation skill so opencode surfaces it the way
 * other hosts do. The skill itself is plain files: skills/dax-ppt/SKILL.md plus
 * the dax.py CLI, so nothing here duplicates its content.
 */

import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

export const SKILL_ROOT = join(ROOT, "skills", "dax-ppt");
export const SKILL_MD = join(SKILL_ROOT, "SKILL.md");
export const CLI = join(SKILL_ROOT, "scripts", "dax.py");

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
      triggers: [
        "deck", "slides", "slide deck", "presentation",
        "powerpoint", "pptx", "board deck", "QBR", "client deck",
      ],
    },
  ],
};
