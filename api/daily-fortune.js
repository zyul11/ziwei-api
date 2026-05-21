#!/usr/bin/env node
/**
 * 每日运势计算 CLI
 *
 * stdin: {
 *   "birth": { "year": 1998, "month": 6, "day": 15, "hour": 12, "gender": "male" },
 *   "chart": { ... },       // 可选：预计算命盘，不传则自动排
 *   "targetDate": "2026-05-18"  // 可选：目标日期，默认今天
 * }
 * stdout: { "chart": {...}, "daily": {...}, "text": {...} }
 */
const { paiPan, calcDailyFortune, generateFortuneText } = require('./ziwei-core');

let input = '';
process.stdin.setEncoding('utf-8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  try {
    const params = JSON.parse(input);
    const { birth, chart: existingChart, targetDate } = params;

    if (!birth || !birth.year || !birth.month || !birth.day || birth.hour === undefined || !birth.gender) {
      console.error(JSON.stringify({ error: 'Missing required: birth { year, month, day, hour, gender }' }));
      process.exit(1);
    }

    // 排盘或复用已有命盘
    const chart = existingChart || paiPan(birth.year, birth.month, birth.day, birth.hour, birth.gender);
    if (!chart.success) {
      console.error(JSON.stringify({ error: 'Chart calculation failed' }));
      process.exit(1);
    }

    // 目标日期（默认今天）
    const dateStr = targetDate || (() => {
      const d = new Date();
      const tzOffset = d.getTimezoneOffset();
      const local = new Date(d.getTime() - tzOffset * 60000);
      return local.toISOString().slice(0, 10);
    })();

    const daily = calcDailyFortune(chart, dateStr);
    const text = generateFortuneText(chart, daily);

    const result = {
      chart: chart,
      daily: daily,
      text: text,
    };

    console.log(JSON.stringify(result));
  } catch (e) {
    console.error(JSON.stringify({ error: e.message, stack: e.stack }));
    process.exit(1);
  }
});
