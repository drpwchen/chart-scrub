// Reads a JSON array of strings on stdin, writes a JSON array of masked
// strings on stdout. Used by tests/test_js_parity.py to prove the browser
// demo and the Python library agree.
//
//   echo "[\"電話 0912-345-678\"]" | node tools/js_deid_runner.mjs
import { deidentify } from '../docs/rules.generated.js';

let raw = '';
for await (const chunk of process.stdin) raw += chunk;
const cases = JSON.parse(raw || '[]');
process.stdout.write(JSON.stringify(cases.map((t) => deidentify(t).text)));
