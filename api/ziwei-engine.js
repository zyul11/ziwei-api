#!/usr/bin/env node
/**
 * 紫微斗数 排盘引擎 CLI
 * stdin: { "year": 1998, "month": 6, "day": 15, "hour": 12, "gender": "male"|"female" }
 * stdout: 完整命盘 JSON
 */
const { paiPan } = require('./ziwei-core');

let input = '';
process.stdin.setEncoding('utf-8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  try {
    const params = JSON.parse(input);
    const { year, month, day, hour, gender, city, language, style } = params;
    if (!year || !month || !day || hour === undefined || !gender) {
      console.error(JSON.stringify({ error: 'Missing required: year, month, day, hour, gender' }));
      process.exit(1);
    }
    const result = paiPan(year, month, day, hour, gender);
    console.log(JSON.stringify(result));
  } catch (e) {
    console.error(JSON.stringify({ error: e.message }));
    process.exit(1);
  }
});
