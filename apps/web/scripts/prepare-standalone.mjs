import { cpSync, existsSync } from "node:fs";

const staticSource = ".next/static";
const staticTarget = ".next/standalone/.next/static";

if (!existsSync(staticSource)) {
  throw new Error(`Next static output is missing: ${staticSource}`);
}

cpSync(staticSource, staticTarget, {
  recursive: true,
  force: true,
});

const publicSource = "public";
const publicTarget = ".next/standalone/public";

if (existsSync(publicSource)) {
  cpSync(publicSource, publicTarget, {
    recursive: true,
    force: true,
  });
}
