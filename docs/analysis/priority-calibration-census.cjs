// Read-only support for the priority-calibration diagnosis; not a CCR command.
// Usage: node docs/analysis/priority-calibration-census.cjs [archive-root]
// Writes aggregate JSON to stdout. Does not emit repository names or local paths.
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const root = path.resolve(process.argv[2] || process.env.CCR_ARTIFACTS_DIR ||
  path.join(process.env.USERPROFILE || process.env.HOME, '.comprehensive-code-review', 'reviews'));
const levels = ['P0', 'P1', 'P2', 'P3'];
const records = [];
const inventory = [];
const diagnostics = {withoutAdjacentClosure: 0, parseErrors: 0, skippedLinks: 0};
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const json = bytes => JSON.parse(bytes.toString('utf8').replace(/^\uFEFF/, ''));
const tally = values => Object.fromEntries([...new Set(values)].sort()
  .map(value => [value, values.filter(item => item === value).length]));

function scan(directory) {
  for (const entry of fs.readdirSync(directory, {withFileTypes: true}).sort((a, b) =>
    a.name < b.name ? -1 : a.name > b.name ? 1 : 0)) {
    if (entry.name === '.publications') continue;
    if (entry.isSymbolicLink()) { diagnostics.skippedLinks++; continue; }
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) { scan(file); continue; }
    if (entry.name !== 'review.json') continue;
    const bytes = fs.readFileSync(file);
    const closurePath = path.join(directory, 'cierre.json');
    const closureBytes = fs.existsSync(closurePath) ? fs.readFileSync(closurePath) : null;
    const reportPath = path.join(directory, 'informe.md');
    const reportBytes = fs.existsSync(reportPath) ? fs.readFileSync(reportPath) : null;
    inventory.push({review: digest(bytes), closure: closureBytes && digest(closureBytes),
      report: reportBytes && digest(reportBytes)});
    if (!closureBytes) { diagnostics.withoutAdjacentClosure++; continue; }
    try {
      const result = json(bytes), closure = json(closureBytes);
      if (!Array.isArray(result.findings) || !result.scope) throw new Error('Invalid record');
      records.push({result, closure, reviewHash: digest(bytes),
        reviewHashMatches: closure.hashes?.['review.json'] === digest(bytes),
        reportHashMatches: !!reportBytes && closure.hashes?.['informe.md'] === digest(reportBytes)});
    } catch { diagnostics.parseErrors++; }
  }
}

function summarize(rows) {
  const findings = rows.flatMap(row => row.result.findings);
  const confirmed = findings.filter(finding => finding.status === 'confirmed');
  return {
    runs: rows.length,
    runsWithConfirmedFindings: rows.filter(row => row.result.findings.some(finding =>
      finding.status === 'confirmed')).length,
    confirmedAppearances: confirmed.length,
    priorities: Object.fromEntries(levels.map(level => [level,
      confirmed.filter(finding => finding.priority === level).length])),
    statuses: tally(findings.map(finding => finding.status)),
    blocking: Object.fromEntries(levels.map(level => [level, {
      yes: confirmed.filter(finding => finding.priority === level && finding.blocking === true).length,
      no: confirmed.filter(finding => finding.priority === level && finding.blocking === false).length,
    }])),
  };
}

function groupBy(rows, key) {
  const groups = new Map();
  for (const row of rows) {
    const identity = JSON.stringify(key(row.result.scope));
    if (!groups.has(identity)) groups.set(identity, []);
    groups.get(identity).push(row);
  }
  return [...groups.values()];
}

scan(root);
const complete = records.filter(row => row.closure.state === 'complete');
const scopes = groupBy(complete, scope => [scope.repository, scope.mode, scope.target,
  scope.reference || [scope.base, scope.head, scope.snapshot]]);
const inputs = groupBy(complete, scope => [scope.repository, scope.mode, scope.reference,
  scope.base, scope.head, scope.snapshot, scope.target]);
const first = [], last = [];
const chronology = {invalidTimestampGroups: 0, firstTimestampTies: 0, lastTimestampTies: 0};
for (const group of scopes) {
  if (group.some(row => !Number.isFinite(Date.parse(row.closure.created_at)))) {
    chronology.invalidTimestampGroups++; continue;
  }
  const sorted = [...group].sort((a, b) => Date.parse(a.closure.created_at) - Date.parse(b.closure.created_at));
  const firstTied = sorted.length > 1 && Date.parse(sorted[0].closure.created_at) === Date.parse(sorted[1].closure.created_at);
  const lastTied = sorted.length > 1 && Date.parse(sorted.at(-1).closure.created_at) === Date.parse(sorted.at(-2).closure.created_at);
  if (firstTied) chronology.firstTimestampTies++; else first.push(sorted[0]);
  if (lastTied) chronology.lastTimestampTies++; else last.push(sorted.at(-1));
}

const dates = complete.map(row => row.closure.created_at).filter(value => Number.isFinite(Date.parse(value)))
  .sort((a, b) => Date.parse(a) - Date.parse(b));
const versions = [...new Set(complete.map(row => row.closure.skill_version || 'unknown'))].sort();
const caseIds = ['CR-049d6d2daa954740834f', 'CR-83f0422a6be6486aa147',
  'CR-24f3526a12c74347bfe9', 'CR-646b7d7accdd438ca36e', 'CR-6c6e27ae88284511a9fb',
  'CR-dd305a6e426c46e3862f', 'CR-d857fbf306f947098456', 'CR-2d2ef29e245840f683af'];
const output = {
  purpose: 'Historical descriptive census, not archive validation or current-scope selection',
  baseCommit: '559fc5c0f8eb2e9677ff738ed86c703017b4bf17',
  sourceSetSha256: digest(JSON.stringify(inventory.map(item => JSON.stringify(item)).sort())),
  filesOutsidePublicationCopies: inventory.length,
  diagnostics,
  closureStates: tally(records.map(row => row.closure.state || 'unknown')),
  complete: summarize(complete),
  integrity: {reviewHashMatches: complete.filter(row => row.reviewHashMatches).length,
    reportHashMatches: complete.filter(row => row.reportHashMatches).length,
    note: 'Compared only review.json and informe.md against adjacent cierre.json hashes; no signature or full lifecycle validation'},
  repositoryCount: new Set(complete.map(row => row.result.scope.repository)).size,
  logicalScopeCount: scopes.length,
  exactGitScopeGroups: inputs.length,
  repeatedExactGitScopeGroups: inputs.filter(group => group.length > 1).length,
  chronology,
  firstChronologicalRecordPerScope: summarize(first),
  lastChronologicalRecordPerScope: summarize(last),
  byDeclaredSkillVersion: Object.fromEntries(versions.map(version => [version,
    summarize(complete.filter(row => (row.closure.skill_version || 'unknown') === version))])),
  creationRangeUtc: dates.length ? [new Date(dates[0]).toISOString(), new Date(dates.at(-1)).toISOString()] : [],
  selectedCaseSources: caseIds.map(id => {
    const row = complete.find(item => item.result.review_id === id);
    return row ? {reviewId: id, reviewSha256: row.reviewHash, skillVersion: row.closure.skill_version} : {reviewId: id, missing: true};
  }),
};
process.stdout.write(JSON.stringify(output, null, 2) + '\n');
