function dashboard() {
  let _chart = null;   // stored outside Alpine proxy so assignments persist
  let _drivers = null;  // the "what moved the gap" chart, same reason
  return {
    // State
    allCountries: [],
    originalCountries: [],
    lastUpdated: null,
    dataVintage: null,
    projectionYear: null,
    imfLabel: null,
    dataStatus: [],
    typicalMonth: null,
    loadError: null,
    comparisons: {},
    revisions: null,
    period: '1M',
    yieldShift: 0,
    selectedCountry: null,
    sliderR: 4.0,
    sliderG: 3.0,
    editingCell: null,
    editValue: 0,
    hasEdits: false,
    chartFinalDebt: null,
    isDark: document.documentElement.classList.contains('dark'),

    // Computed
    get sustainableCountries() {
      return this.allCountries.filter(c => c.fiscal_gap >= 0);
    },
    get unsustainableCountries() {
      return this.allCountries.filter(c => c.fiscal_gap < 0);
    },
    // Table sections, rendered from one row template
    get groups() {
      return [
        { key: 'sustainable', label: 'Debt ratio stable or falling (gap ≥ 0)', dot: 'bg-emerald-500', countries: this.sustainableCountries },
        { key: 'unsustainable', label: 'Debt ratio rising (gap < 0)', dot: 'bg-rose-500', countries: this.unsustainableCountries },
      ].filter(g => g.countries.length > 0);
    },
    // Comparison periods available in the data, in display order
    get periods() {
      const labels = { '1M': '1M', '6M': '6M', '1Y': '1Y', IMF: 'Last IMF release' };
      return Object.keys(labels).filter(k => this.comparisons[k]).map(k => ({ key: k, label: labels[k] }));
    },
    get reference() {
      return this.comparisons[this.period] || null;
    },
    // One line describing what the change column and chart compare with
    get periodCaption() {
      const ref = this.reference;
      if (!ref) return 'No comparison snapshot available';
      const parts = [ref.kind === 'live' ? 'weekly run' : 'month end snapshot'];
      if (ref.imf_vintage) parts.push('IMF WEO ' + this.releaseLabel(ref.imf_vintage));
      if (ref.target_year && ref.target_year !== this.projectionYear) parts.push(ref.target_year + ' fundamentals');
      return 'Compared with ' + this.dateLabel(ref.date) + ' (' + parts.join(', ') + ')';
    },
    // Data older than 10 days means the weekly refresh has stopped
    get isStale() {
      if (!this.lastUpdated) return false;
      return (Date.now() - new Date(this.lastUpdated + 'T00:00:00Z').getTime()) / 86400000 > 10;
    },

    // Theme toggle
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

    // Initialise
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
        this.dataVintage = data.data_vintage || null;
        this.projectionYear = data.projection_year || null;
        this.imfLabel = data.imf?.vintage_label || null;
        this.dataStatus = data.data_status || [];
        this.typicalMonth = data.yields?.typical_month || null;
        this.comparisons = data.comparisons || {};
        this.revisions = data.revisions || null;
        let saved = null;
        try { saved = localStorage.getItem('period'); } catch (e) { /* storage blocked */ }
        this.period = this.comparisons[saved] ? saved : (this.periods[0]?.key || '1M');

        if (this.allCountries.length > 0) {
          this.selectedCountry = this.allCountries[0];
          this.sliderR = this.allCountries[0].r;
          this.sliderG = this.allCountries[0].g;
          window._dashboardReady = this;
          this.$nextTick(() => { this.updateChart(); this.updateDrivers(); });
        }
      } catch (e) {
        console.error('Failed to load fiscal_data.json:', e);
        this.loadError = e.message || String(e);
      }
    },

    // Yield at which the debt ratio is stable: g + 100 x pb / debt.
    // Fiscal gap = (breakeven - r) x debt / 100, so headroom is the gap in
    // bond market units.
    breakeven(c) {
      return c.g + 100 * c.pb / c.debt;
    },
    headroomBp(c) {
      return Math.round((this.breakeven(c) - c.r) * 100);
    },
    breakevenTitle(c) {
      return 'Debt ratio stable at a 10Y yield of ' + this.breakeven(c).toFixed(2) + '%. ' +
        'Each +10 bp on yields moves the fiscal gap by ' + (-c.debt / 1000).toFixed(2) + ' pp of GDP.';
    },

    // Change in the fiscal gap against the selected comparison snapshot,
    // split into four contributions that sum exactly (midpoint weights).
    // Mirrors decompose() in scripts/pipeline/dynamics.py.
    decompose(then, now) {
      const gap = x => x.pb - (x.r - x.real_growth - x.inflation) * x.debt / 100;
      const d = (then.debt + now.debt) / 2;
      const rg = ((then.r - then.real_growth - then.inflation) + (now.r - now.real_growth - now.inflation)) / 2;
      return {
        rates: -d * (now.r - then.r) / 100,
        real_growth: d * (now.real_growth - then.real_growth) / 100,
        inflation: d * (now.inflation - then.inflation) / 100,
        fiscal: (now.pb - then.pb) - rg * (now.debt - then.debt) / 100,
        net: gap(now) - gap(then),
      };
    },
    change(c) {
      const then = this.reference?.countries?.[c.iso3];
      return then ? this.decompose(then, c) : null;
    },
    changeTitle(c) {
      const ch = this.change(c);
      if (!ch) return '';
      const f = v => (v >= 0 ? '+' : '') + v.toFixed(2);
      return 'Rates ' + f(ch.rates) + ', real growth ' + f(ch.real_growth) + ', inflation ' + f(ch.inflation) +
        ', fiscal stance ' + f(ch.fiscal) + ' pp of GDP';
    },
    setPeriod(key) {
      this.period = key;
      try { localStorage.setItem('period', key); } catch (e) { /* storage blocked */ }
      this.updateDrivers();
    },

    // Shift every published yield by the same amount, for "markets have
    // moved since the monthly average" scenarios.
    setYieldShift(bp) {
      this.yieldShift = bp;
      for (const c of this.allCountries) {
        const orig = this.originalCountries.find(o => o.iso3 === c.iso3);
        c.r = +(orig.r + bp / 100).toFixed(2);
        this.recompute(c, false);
      }
      this.sortCountries();
      this.hasEdits = true;
      if (this.selectedCountry) this.sliderR = this.selectedCountry.r;
      this.updateChart();
      this.updateDrivers();
    },

    // Country selection
    selectCountry(c) {
      this.selectedCountry = c;
      this.sliderR = c.r;
      this.sliderG = c.g;
      setTimeout(() => this.updateChart(), 100);
    },
    selectCountryFromTable(c) {
      this.selectCountry(c);
    },
    selectCountryByIso(iso3) {
      const c = this.allCountries.find(c => c.iso3 === iso3);
      if (c) this.selectCountry(c);
    },

    // Sliders
    resetSliders() {
      if (this.selectedCountry) {
        this.sliderR = this.selectedCountry.r;
        this.sliderG = this.selectedCountry.g;
        this.updateChart();
      }
    },

    // Inline editing
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
        if (this.selectedCountry?.iso3 === c.iso3) {
          if (field === 'r') this.sliderR = newVal;
          if (field === 'g') this.sliderG = newVal;
          this.updateChart();
        }
        this.updateDrivers();
      }
      this.editingCell = null;
    },
    cancelEdit() {
      this.editingCell = null;
    },

    // Recompute derived fields
    recompute(c, sort = true) {
      // An edited g keeps inflation and moves real growth, so the change
      // decomposition stays consistent with the table.
      c.real_growth = c.g - c.inflation;
      c.r_g = +(c.r - c.g).toFixed(2);
      c.pb_star = +((c.r / 100 - c.g / 100) * c.debt).toFixed(2);
      c.fiscal_gap = +(c.pb - c.pb_star).toFixed(2);
      c.sustainable = c.fiscal_gap >= 0;
      if (sort) this.sortCountries();
    },
    sortCountries() {
      this.allCountries.sort((a, b) => b.fiscal_gap - a.fiscal_gap);
    },

    // Sync slider values back to selected country table row
    syncSliderToTable() {
      if (!this.selectedCountry) return;
      this.selectedCountry.r = +this.sliderR.toFixed(2);
      this.selectedCountry.g = +this.sliderG.toFixed(2);
      this.recompute(this.selectedCountry);
      this.hasEdits = true;
      this.updateDrivers();
    },

    resetEdits() {
      this.allCountries = this.originalCountries.map(c => ({ ...c }));
      this.hasEdits = false;
      this.yieldShift = 0;
      this.$nextTick(() => this.updateDrivers());
      if (this.selectedCountry) {
        const fresh = this.allCountries.find(c => c.iso3 === this.selectedCountry.iso3);
        if (fresh) this.selectCountry(fresh);
      }
    },

    // Formatting
    fmt(v) {
      return v === null || v === undefined ? '—' : parseFloat(v).toFixed(1);
    },
    // Flags raised by the pipeline for one displayed field. g covers its
    // two IMF components.
    flagText(c, field) {
      const fields = field === 'g' ? ['real_growth', 'inflation'] : [field];
      return (c.flags || []).filter(f => fields.includes(f.field)).map(f => f.message).join(' | ');
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
    verdictClass(v) {
      return {
        improving: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300',
        deteriorating: 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300',
        mixed: 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300',
      }[v] || 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300';
    },
    // Revisions rows in the same order as the main table
    get revisionRows() {
      if (!this.revisions) return [];
      return this.allCountries
        .filter(c => this.revisions.countries[c.iso3])
        .map(c => ({ iso3: c.iso3, name: c.name, ...this.revisions.countries[c.iso3] }));
    },
    fmtSigned(v) {
      if (v === null || v === undefined) return '—';
      const n = parseFloat(v);
      return (n >= 0 ? '+' : '') + n.toFixed(1);
    },

    // Debt trajectory
    computeDebtPath(startDebt, r, g, pb, years = 10) {
      const path = [startDebt];
      let d = startDebt;
      for (let t = 1; t <= years; t++) {
        d = d * (1 + r / 100) / (1 + g / 100) - pb;
        path.push(d);
      }
      return path;
    },

    // Chart
    updateChart() {
      if (!this.selectedCountry) return;

      const isDark = document.documentElement.classList.contains('dark');
      const startDebt = this.selectedCountry.debt;
      const pb = this.selectedCountry.pb;
      const r = this.sliderR;
      const g = this.sliderG;
      const baseYear = this.projectionYear || new Date().getFullYear();
      const years = Array.from({ length: 11 }, (_, i) => String(baseYear + i));
      const debtPath = this.computeDebtPath(startDebt, r, g, pb);
      const finalDebt = debtPath[debtPath.length - 1];
      this.chartFinalDebt = finalDebt;

      const isRising = finalDebt > startDebt;
      const lineColor = isRising
        ? (isDark ? '#f87171' : '#dc2626')
        : (isDark ? '#34d399' : '#059669');

      const ctx = document.getElementById('debtChart') || this.$refs.debtChart;
      if (!ctx) { console.warn('debtChart canvas not found'); return; }
      if (typeof Chart === 'undefined') { console.warn('Chart.js not loaded'); return; }

      // Update existing chart
      if (_chart) {
        const ds = _chart.data.datasets[0];
        ds.data.splice(0, ds.data.length, ...debtPath);
        ds.borderColor = lineColor;
        // Update gradient
        const chartCtx = ctx.getContext('2d');
        const gradient = chartCtx.createLinearGradient(0, 0, 0, 360);
        gradient.addColorStop(0, isRising ? (isDark ? 'rgba(248,113,113,0.15)' : 'rgba(220,38,38,0.1)') : (isDark ? 'rgba(52,211,153,0.15)' : 'rgba(5,150,105,0.1)'));
        gradient.addColorStop(1, 'transparent');
        ds.backgroundColor = gradient;
        // Update grid/tick colours for theme
        const gridColor = isDark ? 'rgba(100,116,139,0.12)' : 'rgba(148,163,184,0.15)';
        const tickColor = isDark ? '#64748b' : '#94a3b8';
        _chart.options.scales.x.grid.color = gridColor;
        _chart.options.scales.y.grid.color = gridColor;
        _chart.options.scales.x.ticks.color = tickColor;
        _chart.options.scales.y.ticks.color = tickColor;
        _chart.update('none');
        return;
      }

      // Create gradient
      const chartCtx = ctx.getContext('2d');
      const gradient = chartCtx.createLinearGradient(0, 0, 0, 360);
      gradient.addColorStop(0, isRising ? (isDark ? 'rgba(248,113,113,0.15)' : 'rgba(220,38,38,0.1)') : (isDark ? 'rgba(52,211,153,0.15)' : 'rgba(5,150,105,0.1)'));
      gradient.addColorStop(1, 'transparent');

      const gridColor = isDark ? 'rgba(100,116,139,0.15)' : 'rgba(148,163,184,0.15)';
      const tickColor = isDark ? '#94a3b8' : '#64748b';

      _chart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: years,
          datasets: [{
            label: 'Debt/GDP',
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
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 300, easing: 'easeOutCubic' },
          layout: { padding: { right: 56, top: 8, bottom: 4 } },
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
              displayColors: false,
              callbacks: {
                title: (items) => items[0].label,
                label: (ctx) => `Debt/GDP: ${ctx.parsed.y.toFixed(1)}%`,
              }
            }
          },
          scales: {
            x: {
              grid: { color: gridColor, drawBorder: false },
              ticks: { font: { family: 'Inter', size: 11 }, color: tickColor },
              border: { display: false },
            },
            y: {
              grid: { color: gridColor, drawBorder: false },
              border: { display: false },
              ticks: {
                callback: (v) => (+v).toFixed(1) + '%',
                font: { family: 'Inter', size: 11 },
                color: tickColor,
              }
            }
          }
        },
        plugins: [{
          id: 'endLabel',
          afterDatasetDraw(chart) {
            const { ctx, data } = chart;
            const dataset = data.datasets[0];
            const meta = chart.getDatasetMeta(0);
            const lastPoint = meta.data[meta.data.length - 1];
            if (!lastPoint) return;

            const finalVal = dataset.data[dataset.data.length - 1];
            const text = finalVal.toFixed(1) + '%';
            const x = lastPoint.x + 8;
            const y = lastPoint.y;

            ctx.save();
            // Draw pill background
            const metrics = ctx.measureText(text);
            const pw = metrics.width + 12;
            const ph = 22;
            ctx.fillStyle = isDark ? 'rgba(15,23,42,0.8)' : 'rgba(255,255,255,0.9)';
            ctx.beginPath();
            ctx.roundRect(x - 4, y - ph / 2, pw, ph, 6);
            ctx.fill();
            ctx.strokeStyle = dataset.borderColor;
            ctx.lineWidth = 1;
            ctx.stroke();

            ctx.font = '600 12px Inter, sans-serif';
            ctx.fillStyle = dataset.borderColor;
            ctx.textBaseline = 'middle';
            ctx.fillText(text, x + 2, y);
            ctx.restore();
          }
        }]
      });
    },

    // "What moved the fiscal gap": stacked contributions per country with a
    // dot for the net change.
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
      const parts = [
        ['Market rates', 'rates', '#D85A30'],
        ['Real growth', 'real_growth', '#1D9E75'],
        ['Inflation', 'inflation', '#EF9F27'],
        ['Fiscal stance', 'fiscal', '#7F77DD'],
      ];
      const datasets = parts.map(([label, key, color]) => ({
        label, data: rows.map(r => r.ch[key]), backgroundColor: color, stack: 's', barThickness: 16, order: 2,
      }));
      datasets.push({
        type: 'line', label: 'Net change', data: rows.map(r => r.ch.net), stack: 'net', indexAxis: 'y',
        showLine: false, pointStyle: 'circle', pointRadius: 7, pointHoverRadius: 8,
        backgroundColor: ink, borderColor: bg, borderWidth: 2.5, order: 1,
      });
      const neg = Math.min(-0.5, ...rows.map(r => parts.reduce((s, p) => s + Math.min(r.ch[p[1]], 0), 0)));
      const pos = Math.max(0.5, ...rows.map(r => parts.reduce((s, p) => s + Math.max(r.ch[p[1]], 0), 0)));
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
            tooltip: { callbacks: { label: c => c.dataset.label + ': ' + f(c.raw) + ' pp GDP' } },
          },
          scales: {
            x: {
              stacked: true, ...xs, grid: { color: grid }, border: { display: false },
              ticks: { color: tick, stepSize: 0.5, callback: v => f(v), font: { family: 'Inter', size: 11 } },
              title: { display: true, text: 'Change in fiscal gap, pp of GDP (right = improving)', color: tick, font: { family: 'Inter', size: 11 } },
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
