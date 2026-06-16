const CARD_TAG = "pool-tracker-graph-card";
const PANEL_TAG = "pool-tracker-panel";

const READING_LABELS = {
  free_chlorine: "Free chlorine",
  ph: "pH",
  total_alkalinity: "Total alkalinity",
  cya: "CYA/stabilizer",
};

const COLORS = {
  prediction: "var(--primary-color)",
  uncertainty: "var(--primary-color)",
  actual: "var(--success-color, #43a047)",
  chemical: "var(--warning-color, #ffa600)",
  grid: "var(--divider-color)",
  text: "var(--primary-text-color)",
  secondary: "var(--secondary-text-color)",
  card: "var(--ha-card-background, var(--card-background-color))",
};

class PoolTrackerGraphCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._selectedEntityId = undefined;
  }

  setConfig(config) {
    this._config = config || {};
    this._selectedEntityId = this._config.entity;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 5;
  }

  _predictionStates() {
    if (!this._hass) {
      return [];
    }
    const configured = [
      ...(this._config.entities || []),
      ...(this._config.entity ? [this._config.entity] : []),
    ];
    const states = configured.length
      ? configured.map((entityId) => this._hass.states[entityId]).filter(Boolean)
      : Object.values(this._hass.states).filter((state) =>
          isPredictionState(state),
        );

    return states.sort((left, right) =>
      stateTitle(left).localeCompare(stateTitle(right)),
    );
  }

  _render() {
    if (!this.shadowRoot) {
      return;
    }

    const states = this._predictionStates();
    if (!this._selectedEntityId && states.length) {
      this._selectedEntityId = states[0].entity_id;
    }
    const selected =
      states.find((state) => state.entity_id === this._selectedEntityId) ||
      states[0];

    this.shadowRoot.innerHTML = `
      <style>${styles()}</style>
      <ha-card>
        ${this._renderContent(states, selected)}
      </ha-card>
    `;

    for (const button of this.shadowRoot.querySelectorAll("button[data-entity]")) {
      button.addEventListener("click", () => {
        this._selectedEntityId = button.dataset.entity;
        this._render();
      });
    }
  }

  _renderContent(states, selected) {
    if (!this._hass) {
      return `<div class="empty">Waiting for Home Assistant.</div>`;
    }
    if (!states.length) {
      return `<div class="empty">No Pool Tracker predictions yet.</div>`;
    }

    return `
      <div class="header">
        <div>
          <div class="title">${escapeHtml(this._config.title || "Pool Tracker")}</div>
          <div class="subtitle">${escapeHtml(cleanTitle(selected))}</div>
        </div>
        <div class="state-block">
          <div class="current">${escapeHtml(stateValue(selected))}</div>
          <div class="state-label">Predicted now</div>
        </div>
      </div>
      ${states.length > 1 ? this._renderTabs(states, selected) : ""}
      ${renderChart(selected)}
      ${renderMeta(selected)}
    `;
  }

  _renderTabs(states, selected) {
    return `
      <div class="tabs" role="tablist">
        ${states
          .map(
            (state) => `
              <button
                type="button"
                role="tab"
                aria-selected="${state.entity_id === selected.entity_id}"
                data-entity="${escapeHtml(state.entity_id)}"
                class="${state.entity_id === selected.entity_id ? "selected" : ""}"
              >
                ${escapeHtml(shortTitle(state))}
              </button>
            `,
          )
          .join("")}
      </div>
    `;
  }
}

class PoolTrackerPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  set panel(panel) {
    this._panel = panel;
    this._render();
  }

  _render() {
    if (!this.shadowRoot || !this._hass) {
      return;
    }
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          padding: 16px;
        }
        ${styles()}
      </style>
      <${CARD_TAG}></${CARD_TAG}>
    `;
    const card = this.shadowRoot.querySelector(CARD_TAG);
    card.setConfig({ title: "Pool Tracker" });
    card.hass = this._hass;
  }
}

function isPredictionState(state) {
  return (
    state &&
    state.entity_id.startsWith("sensor.") &&
    Array.isArray(state.attributes?.series) &&
    Array.isArray(state.attributes?.actuals) &&
    Array.isArray(state.attributes?.chemical_additions)
  );
}

function renderChart(state) {
  const series = state.attributes.series || [];
  const actuals = state.attributes.actuals || [];
  const chemicals = (state.attributes.chemical_additions || []).filter(
    (point) => point.value !== undefined,
  );
  if (!series.length) {
    return `<div class="empty">No chart points for this reading yet.</div>`;
  }

  const width = 720;
  const height = 238;
  const margin = { top: 14, right: 14, bottom: 30, left: 42 };
  const allTimes = [
    ...series.map((point) => point.timestamp),
    ...actuals.map((point) => point.timestamp),
    ...chemicals.map((point) => point.timestamp),
  ].map((timestamp) => new Date(timestamp).getTime());
  const minTime = Math.min(...allTimes);
  const maxTime = Math.max(...allTimes);
  const values = [
    ...series.flatMap((point) => [
      point.lower_bound,
      point.value,
      point.upper_bound,
    ]),
    ...actuals.map((point) => point.value),
    ...chemicals.map((point) => point.value),
  ].filter((value) => Number.isFinite(Number(value)));
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const valuePad = Math.max((maxValue - minValue) * 0.12, 0.1);
  const yMin = Math.max(0, minValue - valuePad);
  const yMax = maxValue + valuePad;
  const currentTime = new Date(state.attributes.as_of || Date.now()).getTime();
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;
  const x = (timestamp) => {
    const time = new Date(timestamp).getTime();
    if (maxTime === minTime) {
      return margin.left + chartWidth / 2;
    }
    return margin.left + ((time - minTime) / (maxTime - minTime)) * chartWidth;
  };
  const y = (value) => {
    if (yMax === yMin) {
      return margin.top + chartHeight / 2;
    }
    return margin.top + chartHeight - ((value - yMin) / (yMax - yMin)) * chartHeight;
  };

  const lowerPath = pathFor(series, x, (point) => y(point.lower_bound));
  const upperPath = pathFor(series, x, (point) => y(point.upper_bound));
  const predictionPath = pathFor(series, x, (point) => y(point.value));
  const actualPath = pathFor(actuals, x, (point) => y(point.value));
  const bandPath = [
    ...series.map((point, index) =>
      `${index === 0 ? "M" : "L"} ${x(point.timestamp).toFixed(1)} ${y(
        point.upper_bound,
      ).toFixed(1)}`,
    ),
    ...[...series].reverse().map((point) =>
      `L ${x(point.timestamp).toFixed(1)} ${y(point.lower_bound).toFixed(1)}`,
    ),
    "Z",
  ].join(" ");
  const ticks = valueTicks(yMin, yMax);
  const xLabels = timeLabels(minTime, maxTime);
  const nowX =
    currentTime >= minTime && currentTime <= maxTime
      ? margin.left + ((currentTime - minTime) / (maxTime - minTime)) * chartWidth
      : undefined;

  return `
    <svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(
      stateTitle(state),
    )} prediction chart">
      <defs>
        <clipPath id="plot-area-${escapeHtml(svgId(state.entity_id))}">
          <rect x="${margin.left}" y="${margin.top}" width="${chartWidth}" height="${chartHeight}"></rect>
        </clipPath>
      </defs>
      ${ticks
        .map(
          (tick) => `
            <line class="grid" x1="${margin.left}" x2="${width - margin.right}" y1="${y(
              tick,
            ).toFixed(1)}" y2="${y(tick).toFixed(1)}"></line>
            <text class="axis" x="${margin.left - 8}" y="${(y(tick) + 4).toFixed(
              1,
            )}" text-anchor="end">${formatNumber(tick)}</text>
          `,
        )
        .join("")}
      <text class="time-axis" x="${margin.left}" y="${height - 6}" text-anchor="start">${escapeHtml(
        xLabels.start,
      )}</text>
      <text class="time-axis" x="${width - margin.right}" y="${height - 6}" text-anchor="end">${escapeHtml(
        xLabels.end,
      )}</text>
      <g clip-path="url(#plot-area-${escapeHtml(svgId(state.entity_id))})">
        <path class="uncertainty" d="${bandPath}"></path>
        <path class="bound" d="${upperPath}"></path>
        <path class="bound" d="${lowerPath}"></path>
        ${
          actualPath
            ? `<path class="actual-line" d="${actualPath}"></path>`
            : ""
        }
        ${
          nowX === undefined
            ? ""
            : `<line class="now-line" x1="${nowX.toFixed(1)}" x2="${nowX.toFixed(
                1,
              )}" y1="${margin.top}" y2="${height - margin.bottom}"></line>`
        }
        <path class="prediction-line" d="${predictionPath}"></path>
        ${actuals
          .map(
            (point) => `
              <circle class="actual-point" cx="${x(point.timestamp).toFixed(
                1,
              )}" cy="${y(point.value).toFixed(1)}" r="3.6">
                <title>${escapeHtml(`Test: ${formatNumber(point.value)}`)}</title>
              </circle>
            `,
          )
          .join("")}
        ${chemicals
          .map((point) => {
            const cx = x(point.timestamp);
            const cy = y(point.value);
            return `
              <path class="chemical-point" d="M ${cx.toFixed(1)} ${(cy - 5).toFixed(
                1,
              )} L ${(cx + 5).toFixed(1)} ${cy.toFixed(1)} L ${cx.toFixed(1)} ${(
                cy + 5
              ).toFixed(1)} L ${(cx - 5).toFixed(1)} ${cy.toFixed(1)} Z">
                <title>${escapeHtml(point.summary || "Chemical addition")}</title>
              </path>
            `;
          })
          .join("")}
      </g>
    </svg>
  `;
}

function pathFor(points, x, y) {
  return points
    .map(
      (point, index) =>
        `${index === 0 ? "M" : "L"} ${x(point.timestamp).toFixed(1)} ${y(
          point,
        ).toFixed(1)}`,
    )
    .join(" ");
}

function renderMeta(state) {
  const attrs = state.attributes || {};
  const actuals = attrs.actuals || [];
  const chemicals = attrs.chemical_additions || [];
  const uncertainty =
    attrs.uncertainty === undefined ? "" : `±${formatNumber(attrs.uncertainty)}`;
  const unit = attrs.unit || attrs.unit_of_measurement || "";

  return `
    <div class="meta-row">
      <span><i class="swatch prediction"></i>Prediction</span>
      <span><i class="swatch uncertainty"></i>${escapeHtml(
        uncertainty ? `${uncertainty}${unit ? ` ${unit}` : ""}` : "Uncertainty",
      )}</span>
      <span><i class="swatch actual"></i>${actuals.length} tests</span>
      <span><i class="swatch chemical"></i>${chemicals.length} chemicals</span>
    </div>
  `;
}

function valueTicks(min, max) {
  const ticks = [];
  const step = (max - min) / 4;
  for (let index = 0; index <= 4; index += 1) {
    ticks.push(min + step * index);
  }
  return ticks;
}

function stateTitle(state) {
  return state?.attributes?.friendly_name || state?.entity_id || "Pool reading";
}

function cleanTitle(state) {
  return stateTitle(state).replace(" (Predicted)", "");
}

function shortTitle(state) {
  const entityId = state?.entity_id || "";
  const reading = Object.keys(READING_LABELS).find((key) => entityId.includes(key));
  return reading ? READING_LABELS[reading] : cleanTitle(state);
}

function stateValue(state) {
  const unit = state?.attributes?.unit || state?.attributes?.unit_of_measurement || "";
  if (!state || state.state === "unknown" || state.state === "unavailable") {
    return "Unknown";
  }
  return `${formatNumber(Number(state.state))}${unit ? ` ${unit}` : ""}`;
}

function formatNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return String(value);
  }
  return number.toLocaleString(undefined, {
    maximumFractionDigits: Math.abs(number) < 10 ? 2 : 0,
  });
}

function timeLabels(minTime, maxTime) {
  const formatter = new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  });
  return {
    start: formatter.format(new Date(minTime)),
    end: formatter.format(new Date(maxTime)),
  };
}

function svgId(value) {
  return String(value).replaceAll(/[^a-zA-Z0-9_-]/g, "-");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function styles() {
  return `
    :host {
      --pool-tracker-chart-height: 238px;
    }
    ha-card {
      display: block;
      padding: 0;
      overflow: hidden;
    }
    .header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      padding: 16px 16px 6px;
    }
    .title {
      color: ${COLORS.text};
      font-size: var(--ha-font-size-l, 18px);
      font-weight: var(--ha-font-weight-medium, 500);
      line-height: 1.2;
    }
    .subtitle {
      color: ${COLORS.secondary};
      font-size: var(--ha-font-size-s, 12px);
      margin-top: 4px;
    }
    .state-block {
      text-align: right;
    }
    .current {
      color: ${COLORS.text};
      font-size: var(--ha-font-size-xl, 22px);
      font-weight: var(--ha-font-weight-normal, 400);
      line-height: 1;
      white-space: nowrap;
    }
    .state-label {
      color: ${COLORS.secondary};
      font-size: var(--ha-font-size-xs, 11px);
      margin-top: 5px;
      white-space: nowrap;
    }
    .tabs {
      display: flex;
      gap: 18px;
      margin: 0 16px 4px;
      overflow-x: auto;
      scrollbar-width: none;
    }
    .tabs::-webkit-scrollbar {
      display: none;
    }
    button {
      appearance: none;
      background: transparent;
      border: 0;
      border-bottom: 2px solid transparent;
      color: ${COLORS.secondary};
      cursor: pointer;
      font: inherit;
      font-size: var(--ha-font-size-s, 12px);
      min-height: 36px;
      padding: 0;
      white-space: nowrap;
    }
    button.selected {
      color: ${COLORS.prediction};
      border-bottom-color: ${COLORS.prediction};
      font-weight: var(--ha-font-weight-medium, 500);
    }
    .chart {
      display: block;
      width: 100%;
      height: var(--pool-tracker-chart-height);
      margin-top: 2px;
    }
    .grid {
      stroke: ${COLORS.grid};
      stroke-width: 1;
      opacity: 0.56;
    }
    .axis,
    .time-axis {
      fill: ${COLORS.secondary};
      font-size: 11px;
      opacity: 0.82;
    }
    .uncertainty {
      fill: ${COLORS.uncertainty};
      opacity: 0.12;
      stroke: none;
    }
    .bound {
      fill: none;
      stroke: ${COLORS.prediction};
      stroke-width: 1;
      opacity: 0.18;
    }
    .actual-line {
      fill: none;
      stroke: ${COLORS.actual};
      stroke-width: 1.5;
      opacity: 0.34;
    }
    .prediction-line {
      fill: none;
      stroke: ${COLORS.prediction};
      stroke-linecap: round;
      stroke-linejoin: round;
      stroke-width: 2.2;
    }
    .now-line {
      stroke: ${COLORS.secondary};
      stroke-dasharray: 2 4;
      stroke-width: 1;
      opacity: 0.28;
    }
    .actual-point {
      fill: ${COLORS.actual};
      stroke: ${COLORS.card};
      stroke-width: 1.5;
    }
    .chemical-point {
      fill: ${COLORS.chemical};
      stroke: ${COLORS.card};
      stroke-width: 1.5;
    }
    .meta-row {
      align-items: center;
      color: ${COLORS.secondary};
      display: flex;
      flex-wrap: wrap;
      gap: 10px 14px;
      font-size: var(--ha-font-size-xs, 11px);
      padding: 0 16px 16px;
    }
    .meta-row span {
      align-items: center;
      display: inline-flex;
      gap: 6px;
    }
    .swatch {
      display: inline-block;
      height: 8px;
      width: 8px;
    }
    .swatch.prediction {
      border-top: 2px solid ${COLORS.prediction};
      height: 0;
      width: 14px;
    }
    .swatch.uncertainty {
      background: ${COLORS.prediction};
      opacity: 0.18;
    }
    .swatch.actual {
      background: ${COLORS.actual};
      border-radius: 50%;
    }
    .swatch.chemical {
      background: ${COLORS.chemical};
      transform: rotate(45deg);
    }
    .empty {
      color: ${COLORS.secondary};
      padding: 24px 16px;
      text-align: center;
    }
  `;
}

if (!customElements.get(CARD_TAG)) {
  customElements.define(CARD_TAG, PoolTrackerGraphCard);
}

if (!customElements.get(PANEL_TAG)) {
  customElements.define(PANEL_TAG, PoolTrackerPanel);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: CARD_TAG,
  name: "Pool Tracker Graph",
  description: "Shows Pool Tracker predictions, uncertainty, tests, and chemicals.",
});
