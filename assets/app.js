// Contributions to the change in the fiscal gap, in display order.
// source says whether the driver comes from markets or IMF forecasts.
const DRIVERS = [
  { key: 'rates', label: '10Y yield', source: 'Market', tag: 'yields', color: '#D85A30',
    tagClass: 'bg-orange-100 text-orange-900 dark:bg-orange-950/60 dark:text-orange-200' },
  { key: 'real_growth', label: 'Real growth', source: 'IMF', tag: 'growth', color: '#1D9E75',
    tagClass: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-200' },
  { key: 'deflator', label: 'GDP deflator', source: 'IMF', tag: 'deflator', color: '#EF9F27',
    tagClass: 'bg-amber-100 text-amber-900 dark:bg-amber-950/60 dark:text-amber-200' },
  { key: 'fiscal', label: 'Primary balance and debt', source: 'IMF', tag: 'fiscal', color: '#7F77DD',
    tagClass: 'bg-violet-100 text-violet-900 dark:bg-violet-950/60 dark:text-violet-200' },
];

// Phrases for the generated sentences, by driver and direction of its
// effect on the gap (+1 improves it, -1 worsens it).
const DRIVER_PHRASES = {
  rates: { '1': 'lower 10Y yields', '-1': 'higher 10Y yields' },
  real_growth: { '1': 'stronger IMF real growth forecasts', '-1': 'weaker IMF real growth forecasts' },
  deflator: { '1': 'higher IMF GDP deflator forecasts', '-1': 'lower IMF GDP deflator forecasts' },
  fiscal: { '1': 'better IMF primary balance and debt forecasts', '-1': 'worse IMF primary balance and debt forecasts' },
};

// Changes smaller than this, in pp of GDP, count as no change.
const CHANGE_THRESHOLD = 0.05;

// Debt arithmetic, exact form of d_t = d_(t-1) (1 + r) / (1 + g) - pb_t with
// debt at the end of last year. Mirrors scripts/pipeline/compute.py.
function stabilisingBalance(r, g, debt) {
  return (r - g) / (1 + g / 100) * debt / 100;
}
// Nominal GDP growth from real growth and GDP deflator growth, %
function nominalGrowth(realGrowth, deflator) {
  return ((1 + realGrowth / 100) * (1 + deflator / 100) - 1) * 100;
}
function fiscalGap(x) {
  return x.pb - stabilisingBalance(x.r, nominalGrowth(x.real_growth, x.deflator), x.debt);
}
// Inputs moved by each driver in the decomposition
const DRIVER_INPUTS = { rates: ['r'], real_growth: ['real_growth'], deflator: ['deflator'], fiscal: ['pb', 'debt'] };

function dashboard() {
  let _chart = null;    // stored outside Alpine proxy so assignments persist
  let _drivers = null;  // the "what moved the gap" chart, same reason
  return {
    // State
    drivers: DRIVERS,
    allCountries: [],
    originalCountries: [],
    lastUpdated: null,
    projectionYear: null,
    debtYear: null,
    imfLabel: null,
    imfVintage: null,
    dataStatus: [],
    typicalMonth: null,
    loadError: null,
    comparisons: {},
    revisions: null,
    imfDebtPaths: {},
    imfBridge: {},
    period: '1M',
    yieldShift: 0,
    selectedCountry: null,
    editingCell: null,
    editValue: 0,
    hasEdits: false,
    chartFinalDebt: null,
    isDark: document.documentElement.classList.contains('dark'),

    // ── Labels built from the data. Each has a neutral fallback so a
    // partial or older data file never shows a wrong year or release.
    get yearText() {
      return this.projectionYear ? String(this.projectionYear) : '';
    },
    get debtYearText() {
      if (this.debtYear) return String(this.debtYear);
      return this.projectionYear ? String(this.projectionYear - 1) : 'last year';
    },
    get imfText() {
      return this.imfLabel ? 'IMF WEO ' + this.imfLabel : 'IMF WEO';
    },
    get monthText() {
      return this.typicalMonth ? this.monthLabel(this.typicalMonth) : 'latest month';
    },
    get periodLabel() {
      return this.periods.find(p => p.key === this.period)?.label || '';
    },
    get isScenario() {
      return this.yieldShift !== 0;
    },
    get hasFlags() {
      return this.allCountries.some(c => (c.flags || []).length > 0);
    },

    // ── Table sections, rendered from one row template
    get sustainableCountries() {
      return this.allCountries.filter(c => c.fiscal_gap >= 0);
    },
    get unsustainableCountries() {
      return this.allCountries.filter(c => c.fiscal_gap < 0);
    },
    get groups() {
      return [
        { key: 'sustainable', label: 'Debt ratio stable or falling (gap ≥ 0)', dot: 'bg-emerald-500', countries: this.sustainableCountries },
        { key: 'unsustainable', label: 'Debt ratio rising (gap < 0)', dot: 'bg-rose-500', countries: this.unsustainableCountries },
      ].filter(g => g.countries.length > 0);
    },

    // ── Comparison periods available in the data, in display order
    get periods() {
      const labels = { '1M': '1M', '6M': '6M', '1Y': '1Y', IMF: 'Last IMF release' };
      return Object.keys(labels).filter(k => this.comparisons?.[k]?.countries).map(k => ({ key: k, label: labels[k] }));
    },
    get reference() {
      return this.comparisons?.[this.period] || null;
    },
    // What the change column and chart compare with, in market terms
    get periodCaption() {
      const ref = this.reference;
      if (!ref) return 'No earlier snapshot available for comparison';
      const months = Object.values(ref.countries || {}).map(c => c.r_month).filter(Boolean);
      const thenMonth = this.mostCommon(months);
      const parts = [];
      if (thenMonth && this.typicalMonth) {
        parts.push(thenMonth === this.typicalMonth
          ? '10Y yields unchanged at ' + this.monthLabel(thenMonth) + ' averages'
          : '10Y yields ' + this.monthLabel(thenMonth) + ' to ' + this.monthLabel(this.typicalMonth) + ' averages');
      }
      if (ref.imf_vintage && this.imfVintage) {
        parts.push(ref.imf_vintage === this.imfVintage
          ? 'IMF forecasts unchanged'
          : 'IMF forecasts ' + this.releaseLabel(ref.imf_vintage) + ' to ' + this.releaseLabel(this.imfVintage));
      }
      if (ref.target_year && this.projectionYear && ref.target_year !== this.projectionYear) {
        parts.push('forecast year ' + ref.target_year + ' to ' + this.projectionYear);
      }
      return 'vs ' + this.dateLabel(ref.date) + (parts.length ? ': ' + parts.join(', ') : '');
    },

    // ── Data older than 10 days means the weekly refresh has stopped
    get isStale() {
      if (!this.lastUpdated) return false;
      return (Date.now() - new Date(this.lastUpdated + 'T00:00:00Z').getTime()) / 86400000 > 10;
    },

    // ── Key messages: generated sentences. A sentence whose inputs are
    // missing is left out rather than shown with gaps.
    get keyMessages() {
      const out = [];
      const n = this.allCountries.length;
      if (!n) return out;
      const prefix = this.hasEdits ? 'Scenario: ' : '';

      const rising = this.unsustainableCountries.length;
      const closest = [...this.allCountries].sort((a, b) => Math.abs(this.cushionBp(a)) - Math.abs(this.cushionBp(b)))[0];
      const cb = this.cushionBp(closest);
      out.push(prefix + 'The debt ratio is rising in ' + (rising === n ? 'all ' + n : rising + ' of ' + n) +
        ' countries at current yields. Closest to the threshold: ' + this.countryRef(closest.name) + ', whose 10Y yield is ' +
        Math.abs(cb) + ' bp ' + (cb < 0 ? 'above' : 'below') + ' the level that keeps debt stable.');

      const period = this.periodMessage;
      if (period) out.push(prefix + period);

      const eff = this.effectiveMessage;
      if (eff) out.push(prefix + eff);

      const imf = this.imfMessage;
      if (imf) out.push(imf);
      return out;
    },
    // How the gaps moved against the selected comparison, and why
    get periodMessage() {
      const ref = this.reference;
      if (!ref) return '';
      const changes = this.allCountries.map(c => this.change(c)).filter(Boolean);
      if (!changes.length) return '';
      const n = changes.length;
      const worse = changes.filter(ch => ch.net < -CHANGE_THRESHOLD).length;
      const better = changes.filter(ch => ch.net > CHANGE_THRESHOLD).length;
      const count = k => (k === n ? 'all ' + n : k + ' of ' + n);
      let text = 'Since ' + this.dateLabel(ref.date) + ', the fiscal gap ';
      if (worse && better) text += 'worsened in ' + worse + ' and improved in ' + better + ' of ' + n + ' countries';
      else if (worse) text += 'worsened in ' + count(worse) + ' countries';
      else if (better) text += 'improved in ' + count(better) + ' countries';
      else return text + 'was broadly unchanged everywhere.';
      const totals = DRIVERS.map(d => ({ key: d.key, sum: changes.reduce((s, ch) => s + ch[d.key], 0) }));
      const absTotal = totals.reduce((s, t) => s + Math.abs(t.sum), 0);
      const top = totals.reduce((a, b) => (Math.abs(b.sum) > Math.abs(a.sum) ? b : a));
      if (absTotal < CHANGE_THRESHOLD) return text + '.';
      const share = Math.abs(top.sum) / absTotal;
      const phrase = DRIVER_PHRASES[top.key][top.sum >= 0 ? '1' : '-1'];
      return text + ', ' + (share > 0.95 ? 'entirely' : share > 0.6 ? 'mainly' : 'partly') + ' from ' + phrase + '.';
    },
    // Today's arithmetic at the average rate paid, against the margin
    get effectiveMessage() {
      const rows = this.allCountries.filter(c => typeof c.r_eff === 'number')
        .map(c => ({ c, eff: this.gapEffective(c), diff: this.gapEffective(c) - c.fiscal_gap }));
      if (!rows.length) return '';
      const rising = rows.filter(x => x.eff < 0).length;
      const top = rows.reduce((a, b) => (b.diff > a.diff ? b : a));
      return 'At the average interest rate actually paid, the debt ratio is rising in ' +
        (rising === rows.length ? 'all ' + rows.length : rising + ' of ' + rows.length) +
        ' countries. Most refinancing pressure still to come: ' + this.countryRef(top.c.name) + ', where the gap is ' +
        this.fmt(top.diff) + ' pp better at its ' + this.fmt(top.c.r_eff) + '% average rate than at the ' +
        this.fmt(top.c.r) + '% 10Y yield.';
    },
    // What the latest IMF release changed
    get imfMessage() {
      const rev = this.revisions;
      if (!rev?.countries || !rev.current_label || !rev.previous_label) return '';
      const byVerdict = { improving: [], deteriorating: [], mixed: [] };
      for (const c of this.allCountries) {
        const v = rev.countries[c.iso3]?.verdict;
        if (byVerdict[v]) byVerdict[v].push(c.name);
      }
      const parts = Object.entries(byVerdict).filter(([, names]) => names.length)
        .map(([v, names]) => v + ' for ' + this.listText(names));
      if (!parts.length) return 'The IMF ' + rev.current_label + ' forecasts barely changed the fiscal outlook against ' + rev.previous_label + '.';
      return 'IMF ' + rev.current_label + ' against ' + rev.previous_label + ': fiscal outlook ' + parts.join(', ') + '.';
    },

    // ── Theme toggle
    toggleTheme() {
      this.isDark = !this.isDark;
      document.documentElement.classList.toggle('dark', this.isDark);
      try { localStorage.setItem('theme', this.isDark ? 'dark' : 'light'); } catch (e) { /* storage blocked */ }
      // Recreate charts with new theme colours
      if (_chart) { _chart.destroy(); _chart = null; }
      if (_drivers) { _drivers.destroy(); _drivers = null; }
      this.updateChart();
      this.updateDrivers();
    },

    // ── Initialise
    async init() {
      try {
        let data = window.FISCAL_DATA;
        if (!data) {
          const resp = await fetch('data/fiscal_data.json');
          if (!resp.ok) throw new Error('HTTP ' + resp.status);
          data = await resp.json();
        }
        if (!data.countries || data.countries.length === 0) throw new Error('no countries in the data file');
        this.allCountries = data.countries.map(c => ({ ...c }));
        this.originalCountries = data.countries.map(c => ({ ...c }));
        this.lastUpdated = data.last_updated || null;
        this.projectionYear = data.projection_year || null;
        this.debtYear = data.debt_year || null;
        this.imfLabel = data.imf?.vintage_label || null;
        this.imfVintage = data.imf?.vintage || null;
        this.dataStatus = data.data_status || [];
        this.typicalMonth = data.yields?.typical_month || null;
        this.comparisons = data.comparisons || {};
        this.revisions = data.revisions?.countries ? data.revisions : null;
        this.imfDebtPaths = data.imf_debt_paths || {};
        this.imfBridge = data.imf_bridge || {};
        let saved = null;
        try { saved = localStorage.getItem('period'); } catch (e) { /* storage blocked */ }
        this.period = this.periods.some(p => p.key === saved) ? saved : (this.periods[0]?.key || '1M');

        this.selectedCountry = this.allCountries[0];
        window._dashboardReady = this;
        this.$nextTick(() => { this.updateChart(); this.updateDrivers(); });
      } catch (e) {
        console.error('Failed to load fiscal_data.json:', e);
        this.loadError = e.message || String(e);
      }
    },

    // ── Market threshold. Breakeven = g + 100 x pb x (1 + g) / debt is the
    // 10Y yield at which the debt ratio is stable.
    breakeven(c) {
      return c.g + 100 * c.pb * (1 + c.g / 100) / c.debt;
    },
    // Fiscal gap at the IMF average interest rate on the whole debt stock,
    // instead of the 10Y yield: today's arithmetic rather than the margin.
    // The rate only changes with an IMF release, so the yield shift leaves it.
    gapEffective(c) {
      if (typeof c.r_eff !== 'number') return null;
      return c.pb - stabilisingBalance(c.r_eff, c.g, c.debt);
    },
    gapEffectiveTitle(c) {
      if (typeof c.r_eff !== 'number') return 'Not available in this data';
      return 'Fiscal gap if the whole debt stock paid the IMF average interest rate of ' + c.r_eff.toFixed(2) +
        '% (net interest paid divided by last year\'s debt) instead of the ' + this.fmt(c.r) + '% 10Y yield. ' +
        'The difference with the headline gap, ' + this.fmtSigned(this.gapEffective(c) - c.fiscal_gap) +
        ' pp, is the refinancing pressure still to come as old debt rolls over at market rates.';
    },
    get hasEffective() {
      return this.allCountries.some(c => typeof c.r_eff === 'number');
    },
    cushionBp(c) {
      return Math.round((this.breakeven(c) - c.r) * 100);
    },
    breakevenTitle(c) {
      return 'Debt ratio stable at a 10Y yield of ' + this.breakeven(c).toFixed(2) + '%. ' +
        'Each +10 bp on the yield changes the fiscal gap by ' + (-c.debt / (1000 * (1 + c.g / 100))).toFixed(2) + ' pp of GDP.';
    },

    // ── Change in the fiscal gap against the selected comparison snapshot,
    // split into four contributions that sum exactly. The gap is not linear
    // in its inputs, so each driver gets its Shapley value: its average
    // effect over every order in which the drivers could be switched.
    // Mirrors decompose() in scripts/pipeline/dynamics.py.
    decompose(then, now) {
      const keys = Object.keys(DRIVER_INPUTS);
      const n = keys.length;
      const fact = k => (k <= 1 ? 1 : k * fact(k - 1));
      const gapWith = moved => {
        const x = { ...then };
        for (const k of moved) for (const f of DRIVER_INPUTS[k]) x[f] = now[f];
        return fiscalGap(x);
      };
      const subsets = list => list.reduce((acc, item) => acc.concat(acc.map(s => [...s, item])), [[]]);
      const parts = {};
      for (const k of keys) {
        let total = 0;
        for (const s of subsets(keys.filter(o => o !== k))) {
          const w = fact(s.length) * fact(n - s.length - 1) / fact(n);
          total += w * (gapWith([...s, k]) - gapWith(s));
        }
        parts[k] = total;
      }
      parts.net = gapWith(keys) - gapWith([]);
      return parts;
    },
    change(c) {
      const then = this.reference?.countries?.[c.iso3];
      const keys = ['r', 'real_growth', 'deflator', 'pb', 'debt'];
      if (!then || keys.some(k => typeof then[k] !== 'number' || typeof c[k] !== 'number')) return null;
      return this.decompose(then, c);
    },
    // Largest contribution pushing in the direction of the net change
    mainDriver(c) {
      const ch = this.change(c);
      if (!ch || Math.abs(ch.net) < CHANGE_THRESHOLD) return null;
      const sign = Math.sign(ch.net);
      return DRIVERS.reduce((best, d) => (ch[d.key] * sign > (best ? ch[best.key] * sign : 0) ? d : best), null);
    },
    changeTitle(c) {
      const ch = this.change(c);
      if (!ch) return 'No comparison available';
      const f = v => (v >= 0 ? '+' : '') + v.toFixed(2);
      return DRIVERS.map(d => d.label + ' (' + d.source + ') ' + f(ch[d.key])).join(', ') + ' pp of GDP';
    },
    setPeriod(key) {
      this.period = key;
      try { localStorage.setItem('period', key); } catch (e) { /* storage blocked */ }
      this.updateDrivers();
    },

    // ── Scenario: shift every published yield by the same amount
    setYieldShift(bp) {
      this.yieldShift = bp;
      for (const c of this.allCountries) {
        const orig = this.originalCountries.find(o => o.iso3 === c.iso3);
        c.r = +(orig.r + bp / 100).toFixed(2);
        this.recompute(c, false);
      }
      this.sortCountries();
      this.hasEdits = true;
      this.updateChart();
      this.updateDrivers();
    },

    // ── Country selection. The trajectory always uses the table values,
    // including any cell edits or yield shift.
    selectCountry(c) {
      this.selectedCountry = c;
      this.$nextTick(() => this.updateChart());
    },
    selectCountryFromTable(c) {
      this.selectCountry(c);
    },
    selectCountryByIso(iso3) {
      const c = this.allCountries.find(c => c.iso3 === iso3);
      if (c) this.selectCountry(c);
    },

    // ── Inline editing
    startEdit(c, field) {
      this.editingCell = { iso3: c.iso3, field };
      this.editValue = c[field];
    },
    commitEdit(c, field) {
      if (this.editingCell?.iso3 !== c.iso3 || this.editingCell?.field !== field) return;
      const newVal = parseFloat(this.editValue);
      if (!isNaN(newVal) && newVal !== c[field]) {
        c[field] = newVal;
        this.recompute(c);
        this.hasEdits = true;
        if (this.selectedCountry?.iso3 === c.iso3) this.updateChart();
        this.updateDrivers();
      }
      this.editingCell = null;
    },
    cancelEdit() {
      this.editingCell = null;
    },

    // ── Recompute derived fields
    recompute(c, sort = true) {
      // An edited g keeps the deflator and moves real growth, so the change
      // decomposition stays consistent with the table.
      if (typeof c.deflator === 'number') c.real_growth = ((1 + c.g / 100) / (1 + c.deflator / 100) - 1) * 100;
      c.r_g = +(c.r - c.g).toFixed(2);
      c.pb_star = +stabilisingBalance(c.r, c.g, c.debt).toFixed(2);
      c.fiscal_gap = +(c.pb - c.pb_star).toFixed(2);
      c.sustainable = c.fiscal_gap >= 0;
      if (sort) this.sortCountries();
    },
    sortCountries() {
      this.allCountries.sort((a, b) => b.fiscal_gap - a.fiscal_gap);
    },

    // Back to the published data: cell edits and the yield shift are undone
    // everywhere (table, key messages, both charts).
    resetEdits() {
      const iso = this.selectedCountry?.iso3;
      this.allCountries = this.originalCountries.map(c => ({ ...c }));
      this.hasEdits = false;
      this.yieldShift = 0;
      this.editingCell = null;
      this.selectedCountry = this.allCountries.find(c => c.iso3 === iso) || this.allCountries[0];
      this.$nextTick(() => { this.updateChart(); this.updateDrivers(); });
    },

    // ── IMF revisions table
    verdictClass(v) {
      return {
        improving: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300',
        deteriorating: 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300',
        mixed: 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300',
      }[v] || 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300';
    },
    verdictReason(row) {
      const pb = row.pb_change > 0.2 ? 'Primary balance stronger' : row.pb_change < -0.2 ? 'Primary balance weaker' : 'Primary balance broadly unchanged';
      const debt = row.debt_slope_change < -1 ? 'debt path flatter' : row.debt_slope_change > 1 ? 'debt path steeper' : 'debt path broadly unchanged';
      return pb + ' (' + this.fmtSigned(row.pb_change) + ' pp), ' + debt + ' (' + this.fmtSigned(row.debt_slope_change) + ' pp).';
    },
    get revisionRows() {
      if (!this.revisions) return [];
      return this.allCountries
        .filter(c => this.revisions.countries[c.iso3])
        .map(c => ({ iso3: c.iso3, name: c.name, ...this.revisions.countries[c.iso3] }));
    },

    // ── Formatting
    fmt(v) {
      return v === null || v === undefined || isNaN(v) ? '—' : parseFloat(v).toFixed(1);
    },
    fmtSigned(v) {
      if (v === null || v === undefined || isNaN(v)) return '—';
      const n = +parseFloat(v).toFixed(1);
      return (n > 0 ? '+' : '') + (n === 0 ? '0.0' : n.toFixed(1));
    },
    // Flags raised by the pipeline for one displayed field. g covers its
    // two IMF components.
    flagText(c, field) {
      const fields = field === 'g' ? ['real_growth', 'deflator'] : [field];
      return (c.flags || []).filter(f => fields.includes(f.field)).map(f => f.message).join(' | ');
    },
    mostCommon(items) {
      const counts = {};
      for (const i of items) counts[i] = (counts[i] || 0) + 1;
      return Object.keys(counts).sort((a, b) => counts[b] - counts[a])[0] || null;
    },
    // Country names as they read inside a sentence
    countryRef(name) {
      return /^United /.test(name) ? 'the ' + name : name;
    },
    listText(names) {
      const refs = names.map(n => this.countryRef(n));
      return refs.length < 2 ? refs.join('') : refs.slice(0, -1).join(', ') + ' and ' + refs[refs.length - 1];
    },
    // '2026-08' -> 'Aug 2026'
    monthLabel(m) {
      if (!m) return '';
      const [y, mo] = m.split('-');
      return ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][+mo - 1] + ' ' + y;
    },
    // '2026-08-31' -> '31 Aug 2026'
    dateLabel(d) {
      if (!d) return '';
      const [y, m, day] = d.split('-');
      return +day + ' ' + this.monthLabel(y + '-' + m);
    },
    // 'Apr2026' -> 'April 2026'
    releaseLabel(v) {
      if (!v) return '';
      return ({ Apr: 'April', Oct: 'October' }[v.slice(0, 3)] || v.slice(0, 3)) + ' ' + v.slice(3);
    },

    // ── Debt trajectory, starting from debt at the end of last year
    computeDebtPath(startDebt, r, g, pb, years = 10) {
      const path = [startDebt];
      let d = startDebt;
      for (let t = 1; t <= years; t++) {
        d = d * (1 + r / 100) / (1 + g / 100) - pb;
        path.push(d);
      }
      return path;
    },
    get trajectoryStartYear() {
      return this.debtYear || (this.projectionYear ? this.projectionYear - 1 : new Date().getFullYear() - 1);
    },
    get trajectoryEndYear() {
      return this.trajectoryStartYear + 10;
    },
    get hasImfPath() {
      return !!(this.selectedCountry && this.imfDebtPaths?.[this.selectedCountry.iso3]);
    },
    // Why the simple projection and the IMF path differ in the forecast year.
    // Debt identity: d_t = d_(t-1) / (1 + g) + interest_t - pb_t + other flows.
    // The simple projection charges r on the whole stock and uses real growth
    // plus CPI. The IMF uses its own net interest and nominal GDP growth.
    get bridge() {
      const c = this.selectedCountry;
      const b = c && this.imfBridge?.[c.iso3];
      if (!b || typeof c.debt !== 'number') return null;
      const r = c.r, g = c.g, d = c.debt;
      const simple = d * (1 + r / 100) / (1 + g / 100) - c.pb;
      const interest = (r / 100) * d / (1 + g / 100) - b.net_interest;
      const growth = d / (1 + g / 100) - d / (1 + b.nominal_growth / 100);
      const total = simple - b.imf_debt;
      return {
        year: b.year, simple, imf: b.imf_debt, total, interest, growth,
        other: total - interest - growth,
        rEff: b.net_interest * (1 + b.nominal_growth / 100) / d * 100,
        gNominal: b.nominal_growth, r, g,
      };
    },

    updateChart() {
      if (!this.selectedCountry) return;
      const ctx = document.getElementById('debtChart');
      if (!ctx || typeof Chart === 'undefined') return;

      const isDark = document.documentElement.classList.contains('dark');
      const startDebt = this.selectedCountry.debt;
      const start = this.trajectoryStartYear;
      const years = Array.from({ length: 11 }, (_, i) => String(start + i));
      const debtPath = this.computeDebtPath(startDebt, this.selectedCountry.r, this.selectedCountry.g, this.selectedCountry.pb);
      const imfPath = this.imfDebtPaths?.[this.selectedCountry.iso3] || {};
      const imfData = years.map(y => (typeof imfPath[y] === 'number' ? imfPath[y] : null));
      const finalDebt = debtPath[debtPath.length - 1];
      this.chartFinalDebt = finalDebt;

      const isRising = finalDebt > startDebt;
      const lineColor = isRising ? (isDark ? '#f87171' : '#dc2626') : (isDark ? '#34d399' : '#059669');
      const imfColor = isDark ? '#94a3b8' : '#64748b';
      const gridColor = isDark ? 'rgba(100,116,139,0.15)' : 'rgba(148,163,184,0.15)';
      const tickColor = isDark ? '#94a3b8' : '#64748b';
      const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 360);
      gradient.addColorStop(0, isRising ? (isDark ? 'rgba(248,113,113,0.15)' : 'rgba(220,38,38,0.1)') : (isDark ? 'rgba(52,211,153,0.15)' : 'rgba(5,150,105,0.1)'));
      gradient.addColorStop(1, 'transparent');

      if (_chart) {
        _chart.data.labels = years;
        const [ds, imf] = _chart.data.datasets;
        ds.data = debtPath;
        ds.borderColor = lineColor;
        ds.pointHoverBackgroundColor = lineColor;
        ds.backgroundColor = gradient;
        imf.data = imfData;
        _chart.update('none');
        return;
      }

      _chart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: years,
          datasets: [{
            label: 'Simple projection',
            data: debtPath,
            borderColor: lineColor,
            backgroundColor: gradient,
            fill: true,
            tension: 0.3,
            pointRadius: 0,
            pointHoverRadius: 6,
            pointHoverBackgroundColor: lineColor,
            pointHoverBorderColor: isDark ? '#0f172a' : '#ffffff',
            pointHoverBorderWidth: 2,
            borderWidth: 3,
          }, {
            label: 'IMF forecast',
            data: imfData,
            borderColor: imfColor,
            borderDash: [6, 4],
            borderWidth: 2,
            fill: false,
            tension: 0.3,
            pointRadius: 0,
            pointHoverRadius: 4,
            spanGaps: false,
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 300, easing: 'easeOutCubic' },
          layout: { padding: { right: 56, top: 8, bottom: 4 } },
          interaction: { mode: 'index', intersect: false },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: isDark ? 'rgba(15,23,42,0.95)' : 'rgba(255,255,255,0.95)',
              titleColor: isDark ? '#e2e8f0' : '#1e293b',
              bodyColor: isDark ? '#94a3b8' : '#64748b',
              borderColor: isDark ? '#334155' : '#e2e8f0',
              borderWidth: 1,
              titleFont: { family: 'Inter', size: 12, weight: '600' },
              bodyFont: { family: 'Inter', size: 13 },
              padding: 12,
              cornerRadius: 8,
              callbacks: {
                title: items => 'End ' + items[0].label,
                label: c => c.parsed.y === null ? null : c.dataset.label + ': ' + c.parsed.y.toFixed(1) + '% of GDP',
              }
            }
          },
          scales: {
            x: {
              grid: { color: gridColor },
              ticks: { font: { family: 'Inter', size: 11 }, color: tickColor },
              border: { display: false },
            },
            y: {
              grid: { color: gridColor },
              border: { display: false },
              title: { display: true, text: 'Debt, % of GDP', color: tickColor, font: { family: 'Inter', size: 11 } },
              ticks: { callback: v => (+v).toFixed(0), font: { family: 'Inter', size: 11 }, color: tickColor },
            }
          }
        },
        plugins: [{
          id: 'endLabel',
          afterDatasetDraw(chart, args) {
            if (args.index !== 0) return;
            const { ctx, data } = chart;
            const dataset = data.datasets[0];
            const meta = chart.getDatasetMeta(0);
            const lastPoint = meta.data[meta.data.length - 1];
            if (!lastPoint) return;
            const text = dataset.data[dataset.data.length - 1].toFixed(1) + '%';
            const x = lastPoint.x + 8;
            const y = lastPoint.y;
            ctx.save();
            ctx.font = '600 12px Inter, sans-serif';
            const pw = ctx.measureText(text).width + 12;
            const ph = 22;
            ctx.fillStyle = isDark ? 'rgba(15,23,42,0.8)' : 'rgba(255,255,255,0.9)';
            ctx.beginPath();
            ctx.roundRect(x - 4, y - ph / 2, pw, ph, 6);
            ctx.fill();
            ctx.strokeStyle = dataset.borderColor;
            ctx.lineWidth = 1;
            ctx.stroke();
            ctx.fillStyle = dataset.borderColor;
            ctx.textBaseline = 'middle';
            ctx.fillText(text, x + 2, y);
            ctx.restore();
          }
        }]
      });
    },

    // ── "What moved the fiscal gap": stacked contributions per country with
    // a dot for the net change.
    updateDrivers() {
      const canvas = document.getElementById('driversChart');
      if (!canvas || typeof Chart === 'undefined') return;
      const rows = this.allCountries
        .map(c => ({ name: c.name, ch: this.change(c) }))
        .filter(r => r.ch)
        .sort((a, b) => b.ch.net - a.ch.net);
      const isDark = document.documentElement.classList.contains('dark');
      const ink = isDark ? '#f1f5f9' : '#0f172a';
      const bg = isDark ? '#0f172a' : '#ffffff';
      const tick = isDark ? '#94a3b8' : '#64748b';
      const grid = isDark ? 'rgba(100,116,139,0.15)' : 'rgba(148,163,184,0.15)';
      const f = v => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(2);
      const datasets = DRIVERS.map(d => ({
        label: d.label + ' (' + d.source + ')', data: rows.map(r => r.ch[d.key]),
        backgroundColor: d.color, stack: 's', barThickness: 16, order: 2,
      }));
      datasets.push({
        type: 'line', label: 'Net change', data: rows.map(r => r.ch.net), stack: 'net', indexAxis: 'y',
        showLine: false, pointStyle: 'circle', pointRadius: 7, pointHoverRadius: 8,
        backgroundColor: ink, borderColor: bg, borderWidth: 2.5, order: 1,
      });
      const neg = Math.min(-0.5, ...rows.map(r => DRIVERS.reduce((s, d) => s + Math.min(r.ch[d.key], 0), 0)));
      const pos = Math.max(0.5, ...rows.map(r => DRIVERS.reduce((s, d) => s + Math.max(r.ch[d.key], 0), 0)));
      const xs = { min: Math.floor((neg - 0.6) * 2) / 2, max: Math.ceil((pos + 0.7) * 2) / 2 };
      const data = { labels: rows.map(r => r.name), datasets };

      if (_drivers) {
        _drivers.data = data;
        Object.assign(_drivers.options.scales.x, xs);
        _drivers.update('none');
        return;
      }
      const netLabel = {
        id: 'netLabel',
        afterDatasetsDraw(chart) {
          const ds = chart.data.datasets, ctx = chart.ctx, meta = chart.getDatasetMeta(4);
          ctx.save();
          ctx.font = '600 12px Inter, sans-serif';
          ctx.textBaseline = 'middle';
          ctx.fillStyle = ink;
          meta.data.forEach((pt, i) => {
            const t = ds[4].data[i];
            const up = [0, 1, 2, 3].reduce((s, j) => s + Math.max(ds[j].data[i], 0), 0);
            const down = [0, 1, 2, 3].reduce((s, j) => s + Math.min(ds[j].data[i], 0), 0);
            const right = t >= 0;
            const edge = chart.scales.x.getPixelForValue(right ? Math.max(up, t) : Math.min(down, t));
            ctx.textAlign = right ? 'left' : 'right';
            ctx.fillText(f(t), edge + (right ? 12 : -12), pt.y);
          });
          ctx.restore();
        },
      };
      const zeroLine = {
        id: 'zeroLine',
        beforeDatasetsDraw(chart) {
          const x = chart.scales.x.getPixelForValue(0), a = chart.chartArea, ctx = chart.ctx;
          ctx.save();
          ctx.strokeStyle = isDark ? 'rgba(241,245,249,0.45)' : 'rgba(15,23,42,0.4)';
          ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(x, a.top); ctx.lineTo(x, a.bottom); ctx.stroke();
          ctx.restore();
        },
      };
      _drivers = new Chart(canvas, {
        type: 'bar',
        data,
        plugins: [zeroLine, netLabel],
        options: {
          indexAxis: 'y', responsive: true, maintainAspectRatio: false, animation: { duration: 250 },
          layout: { padding: { left: 8 } },
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: c => c.dataset.label + ': ' + f(c.raw) + ' pp of GDP' } },
          },
          scales: {
            x: {
              stacked: true, ...xs, grid: { color: grid }, border: { display: false },
              ticks: { color: tick, stepSize: 0.5, callback: v => f(v), font: { family: 'Inter', size: 11 } },
              title: { display: true, text: '← gap worsened     Change in fiscal gap, pp of GDP     gap improved →', color: tick, font: { family: 'Inter', size: 11 } },
            },
            y: {
              stacked: true, grid: { display: false }, border: { display: false },
              ticks: { color: tick, autoSkip: false, font: { family: 'Inter', size: 12 } },
            },
          },
        },
      });
      // Country labels are measured on first draw. Redraw once Inter has
      // loaded, or long names are clipped.
      document.fonts?.ready.then(() => _drivers && _drivers.update('none'));
    }
  };
}
