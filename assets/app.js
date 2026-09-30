function dashboard() {
  let _chart = null;   // stored outside Alpine proxy so assignments persist
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
        { key: 'sustainable', label: 'Sustainable Trajectory (Gap ≥ 0)', dot: 'bg-emerald-500', countries: this.sustainableCountries },
        { key: 'unsustainable', label: 'Unsustainable Trajectory (Gap < 0)', dot: 'bg-rose-500', countries: this.unsustainableCountries },
      ].filter(g => g.countries.length > 0);
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
      // Recreate chart with new theme colours
      if (_chart) { _chart.destroy(); _chart = null; }
      this.updateChart();
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

        if (this.allCountries.length > 0) {
          this.selectedCountry = this.allCountries[0];
          this.sliderR = this.allCountries[0].r;
          this.sliderG = this.allCountries[0].g;
          window._dashboardReady = this;
          this.$nextTick(() => this.updateChart());
        }
      } catch (e) {
        console.error('Failed to load fiscal_data.json:', e);
        this.loadError = e.message || String(e);
      }
    },

    // Debt 10Y calculation for table column
    debt10Y(c) {
      const path = this.computeDebtPath(c.debt, c.r, c.g, c.pb, 10);
      return path[path.length - 1];
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
      }
      this.editingCell = null;
    },
    cancelEdit() {
      this.editingCell = null;
    },

    // Recompute derived fields
    recompute(c) {
      c.r_g = +(c.r - c.g).toFixed(2);
      c.pb_star = +((c.r / 100 - c.g / 100) * c.debt).toFixed(2);
      c.fiscal_gap = +(c.pb - c.pb_star).toFixed(2);
      c.sustainable = c.fiscal_gap >= 0;
      this.allCountries.sort((a, b) => b.fiscal_gap - a.fiscal_gap);
    },

    // Sync slider values back to selected country table row
    syncSliderToTable() {
      if (!this.selectedCountry) return;
      this.selectedCountry.r = +this.sliderR.toFixed(2);
      this.selectedCountry.g = +this.sliderG.toFixed(2);
      this.recompute(this.selectedCountry);
      this.hasEdits = true;
    },

    resetEdits() {
      this.allCountries = this.originalCountries.map(c => ({ ...c }));
      this.hasEdits = false;
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
    }
  };
}
