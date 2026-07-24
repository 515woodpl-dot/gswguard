import { existsSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const requiredFiles = [
  'README.md',
  'SECURITY.md',
  'CONTRIBUTING.md',
  'LICENSE-DECISION.md',
  'docs/adr/0000-adr-index.md',
  'docs/implementation-plan.md',
  'docs/security/baseline-threat-model.md',
];

for (const relativePath of requiredFiles) {
  const path = join(root, relativePath);
  if (!existsSync(path) || !statSync(path).isFile() || readFileSync(path, 'utf8').trim() === '') {
    throw new Error(`Missing or empty required file: ${relativePath}`);
  }
}

const indexPath = join(root, 'docs/adr/0000-adr-index.md');
const index = readFileSync(indexPath, 'utf8');
for (const match of index.matchAll(/\]\(([^)]+\.md)\)/g)) {
  const target = join(dirname(indexPath), match[1]);
  if (!existsSync(target)) throw new Error(`Broken ADR link: ${match[1]}`);
}

console.log('GSWGuard documentation validation passed.');
