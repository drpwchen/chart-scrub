// Reads a JSON array of strings on stdin, writes a JSON array of masked
// strings on stdout. Used by tests/test_js_parity.py to prove the browser
// demo and the Python library agree.
//
//   echo "[\"電話 0912-345-678\"]" | node tools/js_deid_runner.mjs
// An object input exercises the other exported mirrors as well:
//   {"cases": [...], "tokens": [...], "audits": [...]}
// -> {"masked": [...], "classified": [...], "audited": [...]}
import { auditNumbers, classifyNumber, deidentify } from '../docs/rules.generated.js';

let raw = '';
for await (const chunk of process.stdin) raw += chunk;
const input = JSON.parse(raw || '[]');
if (Array.isArray(input)) {
  process.stdout.write(JSON.stringify(input.map((t) => deidentify(t).text)));
} else {
  process.stdout.write(JSON.stringify({
    masked: (input.cases || []).map((t) => deidentify(t).text),
    classified: (input.tokens || []).map(classifyNumber),
    audited: (input.audits || []).map(auditNumbers),
  }));
}
