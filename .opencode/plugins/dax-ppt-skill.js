/**
 * DAX_PPT_SKILL - opencode plugin.
 *
 * Adds this repo's skills/ directory to opencode's skill search paths, so the
 * `dax-ppt` skill (skills/dax-ppt/SKILL.md) is discovered like any other skill.
 * The skill itself is plain files; nothing here duplicates its content.
 *
 * Only the plugin function is exported: opencode may treat every export as a
 * plugin, so stray non-function exports can break loading.
 */

import path from "node:path";
import { fileURLToPath } from "node:url";

const skillsDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../skills");

export const DaxPptPlugin = async () => ({
  config: async (config) => {
    if (Array.isArray(config.skills)) return; // newer array-shaped config; leave untouched
    config.skills ??= {};
    config.skills.paths ??= [];
    if (!config.skills.paths.includes(skillsDir)) config.skills.paths.push(skillsDir);
  },
});

export default { id: "dax-ppt-skill", server: DaxPptPlugin };
