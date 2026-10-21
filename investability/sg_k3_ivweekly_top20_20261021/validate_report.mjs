import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
const html=fs.readFileSync(path.join(here,'report/K3_INVESTABILITY_ZH.html'),'utf8');
const images=[...html.matchAll(/src="data:image\/png;base64,([^"]+)"/g)];
assert.equal(images.length,8);
for(const match of images)assert.equal(Buffer.from(match[1],'base64').subarray(0,8).toString('hex'),'89504e470d0a1a0a');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const controls={scope:{value:'EVAL'},family:{value:'all'},cases:{innerHTML:''}};
// Pure JavaScript callback check; no browser, network, or real UI is used.
vm.runInNewContext(script,{document:{getElementById:id=>controls[id]}});
const count=()=>[...controls.cases.innerHTML.matchAll(/<tr>/g)].length;
assert.equal(count(),40);
controls.scope.value='OCTOBER_CASH';controls.family.value='fresh_capital';controls.scope.onchange();assert.equal(count(),6);
controls.family.value='tick_diagnostic';controls.family.onchange();assert.equal(count(),2);
console.log(JSON.stringify({embedded_figures:8,EVAL_rows:40,fresh_cash_rows:6,tick_rows:2,filter_logic_verified:true}));
