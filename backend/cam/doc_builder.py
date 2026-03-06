"""
cam/doc_builder.py
─────────────────────────────────────────────────────────────────────────────
Word Document (DOCX) builder for Credit Appraisal Memos.

Architecture:
  1. Python assembles the full data payload and writes it to a temp JSON file
  2. Python writes the static Node.js builder script to a temp .js file
  3. Python calls `node builder.js payload.json output.docx`
  4. Falls back to a plain .txt if Node/docx unavailable

This approach avoids ALL f-string / brace-escaping issues — the JS script
is a plain string constant, and data is passed via a JSON file on disk.

CAM Structure (10 sections):
  1. Cover Page          — case metadata
  2. Executive Summary   — LLM narrative
  3. Company Profile     — promoters table
  4. Proposed Facility   — loan terms + security tables
  5. Financial Summary   — 3-yr P&L + BS + WC ratios tables
  6. GST Reconciliation  — flag table
  7. Research Findings   — litigation + news risk table
  8. Five Cs Scorecard   — pillar scores + feature contribution table
  9. Risk Factors        — numbered risk register (LLM narrative)
 10. Recommendation + Audit Trail
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

from config import OUTPUT_DIR


# ── Node.js builder script (pure JS constant — no f-string) ──────────────────
# Data is injected via a JSON file read at runtime, not embedded in the script.

_NODE_SCRIPT = r"""
'use strict';
const fs   = require('fs');
const path = require('path');

// Load docx from global npm
let docxLib;
try {
  docxLib = require('docx');
} catch(e) {
  const gp = require('child_process').execSync('npm root -g').toString().trim();
  docxLib = require(path.join(gp, 'docx'));
}

const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle,
  WidthType, ShadingType, VerticalAlign, PageNumber, PageBreak,
} = docxLib;

// Args: node builder.js <payload.json> <output.docx>
const payloadPath = process.argv[2];
const outPath     = process.argv[3];
const data = JSON.parse(fs.readFileSync(payloadPath, 'utf8'));

// ── Style constants ──────────────────────────────────────────────────────────
const NAVY  = '1F3864', BLUE  = '2E75B6', LBLUE = 'D6E4F0';
const AMBER = 'C65911', RED   = 'C00000', GREEN = '375623';
const LGREY = 'F2F2F2', WHITE = 'FFFFFF', BLACK = '000000';

const BORDER    = { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' };
const BORDERS   = { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER };
const NO_BORDER = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
const NO_BORDERS= { top: NO_BORDER, bottom: NO_BORDER, left: NO_BORDER, right: NO_BORDER };

// ── Helpers ──────────────────────────────────────────────────────────────────

function cell(text, opts) {
  opts = opts || {};
  const bold    = opts.bold    || false;
  const color   = opts.color   || BLACK;
  const bg      = opts.bg      || WHITE;
  const w       = opts.w       || 2000;
  const align   = opts.align   || AlignmentType.LEFT;
  const size    = opts.size    || 18;
  const italic  = opts.italic  || false;
  const colspan = opts.colspan || 1;
  return new TableCell({
    borders: BORDERS,
    width: { size: w, type: WidthType.DXA },
    shading: { fill: bg, type: ShadingType.CLEAR },
    columnSpan: colspan,
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 60, bottom: 60, left: 120, right: 120 },
    children: [new Paragraph({
      alignment: align,
      children: [new TextRun({
        text: String(text == null ? '\u2014' : text),
        bold, color, size, italics: italic, font: 'Arial',
      })]
    })]
  });
}

function hdrCell(text, w, bg) {
  return cell(text, { bold: true, color: WHITE, bg: bg || NAVY, w: w || 2000 });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    pageBreakBefore: true,
    children: [new TextRun({ text, font: 'Arial', size: 32, bold: true, color: NAVY })]
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text, font: 'Arial', size: 24, bold: true, color: BLUE })]
  });
}

function para(text, opts) {
  opts = opts || {};
  return new Paragraph({
    alignment: opts.align || AlignmentType.LEFT,
    spacing: { after: opts.spaceAfter || 120 },
    children: [new TextRun({
      text: String(text || ''),
      bold: opts.bold || false,
      color: opts.color || BLACK,
      size: opts.size || 20,
      italics: opts.italic || false,
      font: 'Arial',
    })]
  });
}

function spacer() {
  return new Paragraph({ children: [new TextRun('')], spacing: { after: 80 } });
}

function decisionColor(d) {
  if (d === 'APPROVE') return GREEN;
  if (d === 'PARTIAL') return AMBER;
  return RED;
}

function gradeColor(g) {
  if (g === 'A+' || g === 'A') return GREEN;
  if (g === 'B+' || g === 'B') return AMBER;
  return RED;
}

function fmtCr(v)  { return '\u20b9' + Number(v || 0).toFixed(2) + ' Cr'; }
function fmtL(v)   { return '\u20b9' + Number(v || 0).toFixed(0) + 'L'; }
function fmtPct(v) { return Number(v || 0).toFixed(1) + '%'; }
function fmtX(v)   { return Number(v || 0).toFixed(2) + 'x'; }

// ── Sections ─────────────────────────────────────────────────────────────────

function coverPage() {
  const m = data.meta, sc = data.scorecard, d = sc.decision;
  return [
    spacer(), spacer(), spacer(),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: 240 },
      children: [new TextRun({ text: 'CREDIT APPRAISAL MEMORANDUM',
        font: 'Arial', size: 52, bold: true, color: NAVY })]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: 120 },
      children: [new TextRun({ text: m.company_name,
        font: 'Arial', size: 36, bold: true, color: BLUE })]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: 480 },
      children: [new TextRun({ text: (m.sector || '').toUpperCase() + ' SECTOR',
        font: 'Arial', size: 22, color: '666666' })]
    }),
    new Table({
      width: { size: 4000, type: WidthType.DXA },
      columnWidths: [4000],
      rows: [new TableRow({ children: [
        new TableCell({
          borders: BORDERS,
          shading: { fill: decisionColor(d), type: ShadingType.CLEAR },
          width: { size: 4000, type: WidthType.DXA },
          margins: { top: 160, bottom: 160, left: 200, right: 200 },
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [new TextRun({
              text: 'RECOMMENDATION: ' + d,
              font: 'Arial', size: 32, bold: true, color: WHITE
            })]
          })]
        })
      ]})]
    }),
    spacer(),
    new Table({
      width: { size: 6000, type: WidthType.DXA },
      columnWidths: [2400, 3600],
      rows: [
        ['CIN', m.cin || '\u2014'],
        ['PAN', m.pan || '\u2014'],
        ['Sector', m.sector || '\u2014'],
        ['Credit Grade', sc.grade + '  \u2014  ' + sc.label],
        ['Score', sc.score + ' / 100  (raw: ' + sc.raw_score + ' / 200)'],
        ['Generated', m.generated_at],
        ['Prepared by', m.analyst_id],
      ].map(function(row) {
        return new TableRow({ children: [
          cell(row[0], { bold: true, bg: LGREY, w: 2400 }),
          cell(row[1], { w: 3600,
            color: row[0] === 'Credit Grade' ? gradeColor(sc.grade) : BLACK,
            bold: row[0] === 'Credit Grade',
          }),
        ]});
      })
    }),
  ];
}

function execSummary() {
  const sc = data.scorecard;
  const children = [
    h1('1. Executive Summary'),
    para(data.narrative.executive_summary, { size: 20 }),
    spacer(),
  ];
  if (sc.knockouts && sc.knockouts.length > 0) {
    children.push(h2('Knockout Flags'));
    sc.knockouts.forEach(function(k) {
      children.push(para('\u26a0  ' + k, { color: RED, bold: true }));
    });
  }
  if (sc.counter) {
    children.push(spacer());
    children.push(para('Path to Approval: ' + sc.counter, { color: BLUE }));
  }
  return children;
}

function companyProfile() {
  const sh = data.shareholding || {};
  return [
    h1('2. Company Profile'),
    para(data.narrative.company_background, { size: 20 }),
    spacer(),
    h2('2.1 Promoter & Shareholding Profile'),
    new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: [3200, 2500, 1830, 1830],
      rows: [
        new TableRow({ children: [
          hdrCell('Promoter Name', 3200),
          hdrCell('Designation', 2500),
          hdrCell('Holding %', 1830),
          hdrCell('Pledged %', 1830),
        ]}),
      ].concat((data.promoters || []).map(function(p) {
        return new TableRow({ children: [
          cell(p.name, { w: 3200 }),
          cell(p.designation, { w: 2500 }),
          cell(fmtPct(p.holding_pct), { w: 1830, align: AlignmentType.RIGHT }),
          cell(fmtPct(p.pledged_pct), {
            w: 1830, align: AlignmentType.RIGHT,
            color: p.pledged_pct >= 50 ? RED : BLACK,
            bold: p.pledged_pct >= 50,
          }),
        ]});
      })).concat([
        new TableRow({ children: [
          cell('Total Promoter Holding', { bold: true, bg: LGREY, w: 3200 }),
          cell('', { w: 2500 }),
          cell(fmtPct(sh.promoter_pct), { bold: true, w: 1830, align: AlignmentType.RIGHT }),
          cell(fmtPct(sh.pledged_pct), {
            bold: true, w: 1830, align: AlignmentType.RIGHT,
            color: (sh.pledged_pct || 0) >= 50 ? RED : BLACK,
          }),
        ]}),
      ])
    }),
  ];
}

function proposedFacility() {
  const ln = data.loan || {};
  const loanRows = [
    ['Facility Type',           ln.facility_type || '\u2014'],
    ['Term Loan Requested',     fmtCr(ln.tl_cr)],
    ['CC / WC Limit Requested', fmtCr(ln.cc_cr)],
    ['Total Requested',         fmtCr(ln.total_cr)],
    ['Tenor (Term Loan)',        (ln.tenor_yr || 7) + ' years'],
    ['Purpose',                  ln.purpose || '\u2014'],
    ['DSCR-Based Limit',         fmtCr(ln.dscr_limit_cr)],
    ['Collateral-Based Limit',   fmtCr(ln.coll_limit_cr)],
    ['RECOMMENDED AMOUNT',       ln.recommended_cr > 0 ? fmtCr(ln.recommended_cr) : 'NIL \u2014 REJECT'],
    ['Recommended Rate',         ln.recommended_cr > 0 ? fmtPct(ln.rate_pct) + ' p.a.' : 'N/A'],
    ['Monthly EMI (Term Loan)',  ln.emi_lakhs > 0 ? fmtL(ln.emi_lakhs) + ' / month' : 'N/A'],
    ['Binding Constraint',       ln.binding || '\u2014'],
  ];
  return [
    h1('3. Proposed Facility'),
    new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: [3500, 5860],
      rows: loanRows.map(function(row) {
        const isRec = row[0].startsWith('RECOMMENDED');
        return new TableRow({ children: [
          cell(row[0], { bold: isRec, bg: isRec ? LBLUE : WHITE, w: 3500 }),
          cell(row[1], {
            bold: isRec, w: 5860,
            color: isRec ? decisionColor(data.scorecard.decision) : BLACK,
          }),
        ]});
      })
    }),
    spacer(),
    h2('3.1 Security Proposed'),
    new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: [2800, 2760, 1300, 1000, 1500],
      rows: [
        new TableRow({ children: [
          hdrCell('Asset Type', 2800),
          hdrCell('Location', 2760),
          hdrCell('FMV (\u20b9L)', 1300),
          hdrCell('LTV', 1000),
          hdrCell('Eligible (\u20b9L)', 1500),
        ]}),
      ].concat((data.security || []).map(function(s) {
        return new TableRow({ children: [
          cell(s.type, { w: 2800 }),
          cell(s.location || '\u2014', { w: 2760 }),
          cell(fmtL(s.fmv_lakhs), { w: 1300, align: AlignmentType.RIGHT }),
          cell(fmtPct((s.ltv || 0) * 100), { w: 1000, align: AlignmentType.RIGHT }),
          cell(fmtL(s.eligible_lakhs), { w: 1500, align: AlignmentType.RIGHT }),
        ]});
      }))
    }),
  ];
}

function financialSummary() {
  const rows = data.fin_rows || [];
  const wcRows = data.wc_rows || [];
  const n = rows.length;
  const colW = n > 0 ? Math.floor((9360 - 2800) / n) : 2186;
  const colWidths = [2800].concat(rows.map(function() { return colW; }));

  function makeFinRow(label, key, fmt, bold, bg) {
    fmt = fmt || fmtL; bold = !!bold; bg = bg || WHITE;
    return new TableRow({ children: [
      cell(label, { bold: bold, bg: bg, w: 2800 }),
    ].concat(rows.map(function(r) {
      return cell(fmt(r[key]), {
        w: colW, align: AlignmentType.RIGHT, bold: bold, bg: bg,
      });
    }))});
  }

  function sectionHdr(label) {
    return new TableRow({ children: [
      cell(label, { bold: true, bg: LBLUE, w: 2800 }),
    ].concat(rows.map(function() { return cell('', { bg: LBLUE, w: colW }); }))});
  }

  const wcColW = wcRows.length > 0 ? Math.floor((9360 - 2800) / wcRows.length) : 2186;
  const wcColWidths = [2800].concat(wcRows.map(function() { return wcColW; }));

  function makeWCRow(label, key, fmt, threshold, above) {
    // above=true means red when above threshold; above=false means red when below
    return new TableRow({ children: [
      cell(label, { w: 2800 }),
    ].concat(wcRows.map(function(r) {
      const val = r[key] || 0;
      const isRed = above ? val > threshold : val < threshold;
      return cell(fmt(val), {
        w: wcColW, align: AlignmentType.RIGHT,
        color: isRed ? RED : BLACK, bold: isRed,
      });
    }))});
  }

  return [
    h1('4. Financial Summary'),
    para('All figures in \u20b9 Lakhs unless stated otherwise.  Source: Audited Accounts.',
      { italic: true, size: 16, color: '666666' }),
    spacer(),
    new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: colWidths,
      rows: [
        new TableRow({ children: [
          hdrCell('Particulars (\u20b9L)', 2800),
        ].concat(rows.map(function(r) { return hdrCell(r.year, colW); }))}),
        sectionHdr('PROFIT & LOSS'),
        makeFinRow('Revenue from Operations', 'revenue'),
        makeFinRow('EBITDA', 'ebitda', fmtL, true),
        makeFinRow('EBITDA Margin', 'ebitda_pct', fmtPct),
        makeFinRow('PAT', 'pat', fmtL, true),
        makeFinRow('PAT Margin', 'pat_pct', fmtPct),
        makeFinRow('Interest Expense', 'interest'),
        sectionHdr('BALANCE SHEET'),
        makeFinRow('Total Debt', 'total_debt'),
        makeFinRow('Tangible Net Worth', 'tnw', fmtL, true),
        makeFinRow('Current Assets', 'ca'),
        makeFinRow('Current Liabilities', 'cl'),
      ]
    }),
    spacer(),
    h2('4.1 Working Capital Ratios'),
    new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: wcColWidths,
      rows: [
        new TableRow({ children: [
          hdrCell('Ratio', 2800),
        ].concat(wcRows.map(function(r) { return hdrCell(r.year, wcColW); }))}),
        makeWCRow('DSCR',                  'dscr',                 fmtX,    1.30, false),
        makeWCRow('D/E Ratio',             'de_ratio',             fmtX,    3.0,  true),
        makeWCRow('Current Ratio',         'current_ratio',        fmtX,    1.0,  false),
        makeWCRow('Debtor Days (DSO)',      'debtor_days',          function(v){ return v.toFixed(0)+'d'; }, 120, true),
        makeWCRow('Creditor Days (DPO)',    'creditor_days',        function(v){ return v.toFixed(0)+'d'; }, 180, true),
        makeWCRow('Inventory Days',        'inventory_days',       function(v){ return v.toFixed(0)+'d'; }, 999, false),
        makeWCRow('Cash Conversion Cycle', 'cash_conversion_cycle',function(v){ return v.toFixed(0)+'d'; }, 120, true),
        makeWCRow('Interest Coverage',     'interest_coverage',    fmtX,    1.5,  false),
      ]
    }),
  ];
}

function gstSection() {
  const flags = data.gst_flags || [];
  if (!flags.length) return [
    h1('5. GST & Bank Reconciliation'),
    para('No significant GST reconciliation flags identified.', { color: GREEN }),
  ];
  return [
    h1('5. GST & Bank Reconciliation'),
    new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: [1400, 2200, 4160, 1600],
      rows: [
        new TableRow({ children: [
          hdrCell('Severity', 1400), hdrCell('Flag Type', 2200),
          hdrCell('Description', 4160), hdrCell('Metric', 1600),
        ]}),
      ].concat(flags.map(function(f) {
        const sev = f.severity || 'MEDIUM';
        const bg  = sev === 'CRITICAL' ? 'FFE0E0' : sev === 'HIGH' ? 'FFF0E0' : WHITE;
        const col = sev === 'CRITICAL' ? RED : sev === 'HIGH' ? AMBER : BLACK;
        return new TableRow({ children: [
          cell(sev,  { w: 1400, color: col, bold: true, bg: bg }),
          cell(f.flag_type, { w: 2200, bg: bg }),
          cell((f.description || '').substring(0, 120), { w: 4160, size: 16 }),
          cell(f.metric_value != null ? Number(f.metric_value).toFixed(2) : '\u2014',
            { w: 1600, align: AlignmentType.RIGHT }),
        ]});
      }))
    }),
  ];
}

function researchSection() {
  const items = data.research || [];
  const lit   = data.lit || {};
  const children = [
    h1('6. Research & Litigation Findings'),
    para('Litigation Status: ' + (lit.label || 'N/A') +
      (lit.knockout ? '  \u2014  KNOCKOUT FLAG' : ''),
      { bold: true, color: lit.knockout ? RED : BLACK }),
    spacer(),
  ];
  if (lit.primary) {
    children.push(para('Primary Risk: ' + lit.primary, { color: RED }));
    children.push(para('Resolution Required: ' + (lit.resolution || ''), { color: BLUE }));
    children.push(spacer());
  }
  if (items.length) {
    children.push(new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: [900, 5460, 1600, 1400],
      rows: [
        new TableRow({ children: [
          hdrCell('Tier', 900), hdrCell('Finding', 5460),
          hdrCell('Source', 1600), hdrCell('Risk \u0394', 1400),
        ]}),
      ].concat(items.map(function(r) {
        const tier  = r.risk_tier;
        const bg    = tier === 1 ? 'FFE0E0' : tier === 2 ? 'FFF0E0' : WHITE;
        const col   = tier === 1 ? RED : tier === 2 ? AMBER : BLACK;
        const delta = r.risk_score_delta || 0;
        return new TableRow({ children: [
          cell(tier ? 'T' + tier : '+', { w: 900, color: col, bold: !!tier, bg: bg }),
          cell((r.title || '').substring(0, 100), { w: 5460, size: 16 }),
          cell(r.source_name || '\u2014', { w: 1600, size: 16 }),
          cell((delta > 0 ? '+' : '') + delta,
            { w: 1400, align: AlignmentType.RIGHT,
              color: delta < 0 ? RED : GREEN, bold: delta < -15 }),
        ]});
      }))
    }));
  } else {
    children.push(para('No research findings recorded.', { color: '666666' }));
  }
  return children;
}

function scorecardSection() {
  const sc = data.scorecard || {};
  const pillars = sc.pillars || {};
  const contribs = (sc.contribs || []).slice(0, 10);

  const pillarDefs = [
    ['Character',  'character',  60, 'Litigation, promoter track record, GST, management'],
    ['Capacity',   'capacity',   60, 'DSCR, EBITDA trend, revenue CAGR, plant utilization'],
    ['Capital',    'capital',    45, 'D/E ratio, net worth trend, promoter equity'],
    ['Collateral', 'collateral', 30, 'Security cover, encumbrance'],
    ['Conditions', 'conditions', 35, 'Sector outlook, customer concentration, regulatory'],
  ];

  const pillarRows = pillarDefs.map(function(def) {
    const label = def[0], key = def[1], max = def[2], desc = def[3];
    const score = (pillars[key] || {}).score || 0;
    const pct   = Math.round(score / max * 100);
    const color = pct >= 70 ? GREEN : pct >= 50 ? AMBER : RED;
    return new TableRow({ children: [
      cell(label, { bold: true, w: 2000 }),
      cell(score + ' / ' + max, { w: 1500, align: AlignmentType.RIGHT, color: color, bold: true }),
      cell(pct + '%', { w: 1000, align: AlignmentType.RIGHT }),
      cell(desc, { w: 4860, size: 16 }),
    ]});
  });

  const totalRow = new TableRow({ children: [
    cell('TOTAL', { bold: true, bg: NAVY, color: WHITE, w: 2000 }),
    cell(sc.raw_score + ' / 200', { bold: true, bg: NAVY, color: WHITE, w: 1500, align: AlignmentType.RIGHT }),
    cell(sc.score + ' / 100', { bold: true, bg: NAVY, color: WHITE, w: 1000, align: AlignmentType.RIGHT }),
    cell('Grade: ' + sc.grade + '  \u2014  ' + sc.label, { bold: true, bg: NAVY, color: WHITE, w: 4860 }),
  ]});

  const contribRows = contribs.map(function(c) {
    const gap   = (c.max_points || 0) - (c.points_awarded || 0);
    const pct   = c.pct || 0;
    const color = pct >= 70 ? GREEN : pct >= 40 ? AMBER : RED;
    return new TableRow({ children: [
      cell((c.feature || '').replace(/_/g, ' '), { w: 3200 }),
      cell(c.points_awarded, { w: 1680, align: AlignmentType.RIGHT, color: color, bold: pct < 40 }),
      cell(c.max_points, { w: 1680, align: AlignmentType.RIGHT }),
      cell(pct.toFixed(0) + '%', { w: 1600, align: AlignmentType.RIGHT, color: color }),
      cell(gap > 0 ? '-' + gap : '0', { w: 1200, align: AlignmentType.RIGHT, color: gap > 5 ? RED : '666666' }),
    ]});
  });

  return [
    h1('7. Five Cs Scorecard'),
    new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: [2000, 1500, 1000, 4860],
      rows: [
        new TableRow({ children: [
          hdrCell('Pillar', 2000), hdrCell('Score', 1500),
          hdrCell('% of Max', 1000), hdrCell('Components', 4860),
        ]}),
      ].concat(pillarRows).concat([totalRow])
    }),
    spacer(),
    h2('7.1 Feature Contribution Detail'),
    new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: [3200, 1680, 1680, 1600, 1200],
      rows: [
        new TableRow({ children: [
          hdrCell('Feature', 3200), hdrCell('Awarded', 1680),
          hdrCell('Maximum', 1680), hdrCell('Score %', 1600), hdrCell('Gap', 1200),
        ]}),
      ].concat(contribRows)
    }),
  ];
}

function riskSection() {
  const lines = (data.narrative.risk_factors || '').split('\n').filter(function(l){ return l.trim(); });
  return [
    h1('8. Risk Factors & Mitigants'),
  ].concat(lines.map(function(line) {
    return para(line, { size: 20, spaceAfter: 160 });
  }));
}

function recommendationSection() {
  const sc = data.scorecard;
  return [
    h1('9. Recommendation & Audit Trail'),
    new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: [9360],
      rows: [new TableRow({ children: [
        new TableCell({
          borders: BORDERS,
          shading: { fill: decisionColor(sc.decision), type: ShadingType.CLEAR },
          width: { size: 9360, type: WidthType.DXA },
          margins: { top: 120, bottom: 120, left: 200, right: 200 },
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [new TextRun({
              text: sc.decision + '  \u2014  Grade ' + sc.grade + '  (' + sc.score + '/100)',
              font: 'Arial', size: 28, bold: true, color: WHITE,
            })]
          })]
        })
      ]})]
    }),
    spacer(),
    para(data.narrative.recommendation, { size: 20 }),
    spacer(),
    h2('Audit Trail'),
    new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: [3000, 6360],
      rows: [
        ['Document generated',  data.meta.generated_at],
        ['Prepared by',         data.meta.analyst_id],
        ['Case ID',             data.meta.case_id],
        ['Narrative source',    data.meta.model_used === 'claude'
          ? 'AI-assisted (Claude Sonnet)' : 'Deterministic template'],
        ['Score',               sc.score + '/100  (raw: ' + sc.raw_score + '/200)'],
        ['Decision',            sc.decision],
        ['Overrides',           (data.override_log || []).length > 0
          ? (data.override_log.length + ' override(s) applied') : 'None'],
      ].map(function(row) {
        return new TableRow({ children: [
          cell(row[0], { bold: true, bg: LGREY, w: 3000 }),
          cell(row[1], { w: 6360 }),
        ]});
      })
    }),
    spacer(),
    para(
      'This document was generated by Intelli-Credit (Hackathon Demo). ' +
      'Scoring is deterministic; LLM generates narrative prose only. ' +
      'This memo does not constitute financial advice.',
      { size: 16, color: '888888', italic: true }
    ),
  ];
}

// ── Assemble & write ─────────────────────────────────────────────────────────

const allChildren = [].concat(
  coverPage(),
  execSummary(),
  companyProfile(),
  proposedFacility(),
  financialSummary(),
  gstSection(),
  researchSection(),
  scorecardSection(),
  riskSection(),
  recommendationSection()
);

const doc = new Document({
  styles: {
    default: { document: { run: { font: 'Arial', size: 20 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 32, bold: true, font: 'Arial', color: '1F3864' },
        paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 24, bold: true, font: 'Arial', color: '2E75B6' },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 }
      }
    },
    headers: {
      default: new Header({ children: [
        new Paragraph({
          alignment: AlignmentType.RIGHT,
          border: { bottom: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' } },
          children: [new TextRun({
            text: 'CONFIDENTIAL \u2014 Credit Appraisal Memo: ' + data.meta.company_name,
            font: 'Arial', size: 16, color: '888888',
          })]
        })
      ]})
    },
    footers: {
      default: new Footer({ children: [
        new Paragraph({
          alignment: AlignmentType.CENTER,
          border: { top: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' } },
          children: [
            new TextRun({ text: 'Page ', font: 'Arial', size: 16, color: '888888' }),
            new TextRun({ children: [PageNumber.CURRENT], font: 'Arial', size: 16, color: '888888' }),
            new TextRun({ text: ' of ', font: 'Arial', size: 16, color: '888888' }),
            new TextRun({ children: [PageNumber.TOTAL_PAGES], font: 'Arial', size: 16, color: '888888' }),
          ]
        })
      ]})
    },
    children: allChildren,
  }]
});

Packer.toBuffer(doc).then(function(buf) {
  fs.writeFileSync(outPath, buf);
  console.log('CAM written: ' + outPath + ' (' + buf.length + ' bytes)');
}).catch(function(e) {
  console.error('Packer error: ' + e.message);
  process.exit(1);
});
"""


# ── Main build function ───────────────────────────────────────────────────────

def build_cam_docx(
    case_id:        str,
    financial_data: dict,
    scorecard:      dict,
    loan_sizing:    dict,
    wc_analysis:    dict,
    rp_analysis:    dict,
    gst_recon:      dict,
    research_items: list[dict],
    lit_summary:    dict,
    narrative:      "CAMNarrative",
    analyst_id:     str = "System",
    override_log:   list[dict] | None = None,
) -> Path:
    out_path = Path(OUTPUT_DIR) / f"{case_id}_CAM.docx"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = _build_payload(
        case_id, financial_data, scorecard, loan_sizing,
        wc_analysis, rp_analysis, gst_recon,
        research_items, lit_summary, narrative,
        analyst_id, override_log or [],
    )

    try:
        _run_node_builder(payload, str(out_path))
        logger.info("CAM DOCX built: %s (%.0f KB)", out_path, out_path.stat().st_size / 1024)
        return out_path
    except Exception as e:
        logger.error("DOCX build failed (%s) — falling back to .txt", e)
        return _write_txt_fallback(payload, case_id)


# ── Payload assembly ──────────────────────────────────────────────────────────

def _build_payload(
    case_id, fin, sc, ls, wc, rp, gst,
    research_items, lit, narrative,
    analyst_id, override_log,
) -> dict:
    company   = fin.get("company", {})
    lr        = fin.get("loan_request", {})
    financials= fin.get("financials", {})
    pnl       = financials.get("profit_and_loss", {})
    bs        = financials.get("balance_sheet", {})
    years     = financials.get("years", [])
    promoters = fin.get("promoters", [])
    sp        = fin.get("shareholding_pattern", {})

    def row(i):
        def v(d, k):
            val = d.get(k, [])
            return round(float(val[i]), 1) if isinstance(val, list) and i < len(val) else 0.0
        return {
            "year": years[i] if i < len(years) else f"Y{i+1}",
            "revenue":   v(pnl, "revenue_from_operations"),
            "ebitda":    v(pnl, "ebitda"),
            "ebitda_pct":v(pnl, "ebitda_margin_pct"),
            "pat":       v(pnl, "pat"),
            "pat_pct":   v(pnl, "pat_margin_pct"),
            "interest":  v(pnl, "interest_expense"),
            "total_debt":v(bs,  "total_debt"),
            "tnw":       v(bs,  "tangible_net_worth"),
            "ca":        v(bs,  "total_current_assets"),
            "cl":        v(bs,  "total_current_liabilities"),
        }

    return {
        "meta": {
            "case_id":        case_id,
            "company_name":   company.get("name", ""),
            "cin":            company.get("cin", ""),
            "pan":            company.get("pan", ""),
            "sector":         company.get("sector", ""),
            "rating":         company.get("rating", "N/A"),
            "rating_outlook": company.get("rating_outlook", ""),
            "generated_at":   datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
            "analyst_id":     analyst_id,
            "model_used":     narrative.model_used,
        },
        "loan": {
            "facility_type":  lr.get("facility_type", "Term Loan + CC"),
            "tl_cr":          lr.get("term_loan_requested_cr", 0),
            "cc_cr":          lr.get("wc_cc_requested_cr", 0),
            "total_cr":       lr.get("total_requested_cr", 0),
            "tenor_yr":       lr.get("tenor_term_loan_yr", 7),
            "purpose":        lr.get("purpose", ""),
            "recommended_cr": ls.get("recommendation", {}).get("recommended_cr", 0),
            "rec_tl_cr":      ls.get("recommendation", {}).get("term_loan_cr", 0),
            "rec_cc_cr":      ls.get("recommendation", {}).get("cc_limit_cr", 0),
            "rate_pct":       ls.get("rate", {}).get("recommended_rate_pct", 0),
            "base_rate":      ls.get("rate", {}).get("base_rate_pct", 0),
            "risk_premium":   ls.get("rate", {}).get("risk_premium_pct", 0),
            "emi_lakhs":      ls.get("repayment", {}).get("emi_monthly_lakhs", 0),
            "binding":        ls.get("recommendation", {}).get("binding_constraint", ""),
            "dscr_limit_cr":  ls.get("limits", {}).get("dscr_based_cr", 0),
            "coll_limit_cr":  ls.get("limits", {}).get("collateral_based_cr", 0),
        },
        "security":  lr.get("security_proposed", []),
        "promoters": [
            {
                "name":        p.get("name", ""),
                "designation": p.get("designation", ""),
                "holding_pct": p.get("shareholding_pct", 0),
                "pledged_pct": p.get("shares_pledged_pct", 0),
            }
            for p in promoters
        ],
        "shareholding": {
            "promoter_pct": sp.get("promoter_total_pct", 0),
            "pledged_pct":  sp.get("promoter_pledged_pct", 0),
            "public_pct":   sp.get("public_pct", 0),
            "other_pct":    sp.get("other_pct", 0),
        },
        "fin_rows":   [row(i) for i in range(len(years))],
        "wc_rows":    wc.get("yearly_metrics", []),
        "scorecard": {
            "grade":     sc.get("risk_grade", ""),
            "label":     sc.get("risk_label", ""),
            "score":     sc.get("normalised_score", 0),
            "raw_score": sc.get("total_raw_score", 0),
            "decision":  sc.get("decision", ""),
            "trigger":   sc.get("primary_rejection_trigger", ""),
            "counter":   sc.get("counter_factual", ""),
            "knockouts": sc.get("knockout_flags", []),
            "pillars":   sc.get("pillar_scores", {}),
            "contribs":  sorted(
                [{"feature": k, **v} for k, v in sc.get("contributions", {}).items()],
                key=lambda x: x.get("pct", 0)
            ),
            "rate_pct":  sc.get("recommended_rate_pct", 0),
        },
        "gst_flags":   gst.get("flags", [])[:6],
        "research":    sorted(
            [r for r in research_items if r.get("risk_score_delta", 0) != 0],
            key=lambda x: x.get("risk_score_delta", 0)
        )[:8],
        "lit": {
            "label":      lit.get("aggregate_label", ""),
            "knockout":   lit.get("knockout", False),
            "cases":      lit.get("cases", [])[:5],
            "primary":    lit.get("primary_trigger", ""),
            "resolution": lit.get("resolution_path", ""),
        },
        "narrative": {
            "executive_summary":  narrative.executive_summary,
            "company_background": narrative.company_background,
            "financial_analysis": narrative.financial_analysis,
            "risk_factors":       narrative.risk_factors,
            "recommendation":     narrative.recommendation,
        },
        "override_log": override_log,
    }


# ── Node runner ───────────────────────────────────────────────────────────────

def _run_node_builder(payload: dict, out_path: str) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        payload_path = os.path.join(tmpdir, "payload.json")
        script_path  = os.path.join(tmpdir, "builder.js")

        with open(payload_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, default=str)

        with open(script_path, "w", encoding="utf-8") as f:
            f.write(_NODE_SCRIPT)

        result = subprocess.run(
            ["node", script_path, payload_path, out_path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Node script error:\n{result.stderr[:600]}")


# ── TXT fallback ──────────────────────────────────────────────────────────────

def _write_txt_fallback(payload: dict, case_id: str) -> Path:
    txt_path = Path(OUTPUT_DIR) / f"{case_id}_CAM.txt"
    m   = payload["meta"]
    sc  = payload["scorecard"]
    ln  = payload["loan"]
    nav = payload["narrative"]

    lines = [
        "CREDIT APPRAISAL MEMORANDUM", "=" * 60,
        f"Company : {m['company_name']}",
        f"Grade   : {sc['grade']}  Score: {sc['score']}/100",
        f"Decision: {sc['decision']}",
        f"Generated: {m['generated_at']}",
        "", "EXECUTIVE SUMMARY", "-" * 40,
        nav["executive_summary"], "",
        "FINANCIAL SUMMARY (Rs Lakhs)", "-" * 40,
    ]
    for r in payload["fin_rows"]:
        lines.append(
            f"  {r['year']}: Rev={r['revenue']:.0f}L  EBITDA={r['ebitda']:.0f}L"
            f"  PAT={r['pat']:.0f}L  Debt={r['total_debt']:.0f}L  TNW={r['tnw']:.0f}L"
        )
    lines += [
        "", "RECOMMENDATION", "-" * 40,
        nav["recommendation"],
        "", "RISK FACTORS", "-" * 40,
        nav["risk_factors"],
        "", f"Recommended: Rs{ln['recommended_cr']:.2f} Cr @ {ln['rate_pct']:.2f}% p.a.",
    ]
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    return txt_path