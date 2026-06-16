const CARD_TAG = "pool-tracker-graph-card";
const PANEL_TAG = "pool-tracker-panel";

const READING_LABELS = {
  free_chlorine: "Free chlorine",
  ph: "pH",
  total_alkalinity: "Total alkalinity",
  cya: "CYA/stabilizer",
};

const COLORS = {
  prediction: "#1a73e8",
  uncertainty: "rgba(26, 115, 232, 0.16)",
  lowerUpper: "#9aa0a6",
  actual: "#188038",
  chemical: "#fa7b17",
  grid: "rgba(95, 99, 104, 0.24)",
  text: "var(--primary-text-color)",
  secondary: "var(--secondary-text-color)",
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
          <div class="subtitle">${escapeHtml(stateTitle(selected))}</div>
        </div>
        <div class="current">${escapeHtml(stateValue(selected))}</div>
      </div>
      ${states.length > 1 ? this._renderTabs(states, selected) : ""}
      ${renderChart(selected)}
      <div class="legend">
        <span><i class="line prediction"></i>Prediction</span>
        <span><i class="band"></i>Uncertainty</span>
        <span><i class="dot actual"></i>Tests</span>
        <span><i class="diamond chemical"></i>Chemicals</span>
      </div>
    `;
  }

  _renderTabs(states, selected) {
    return `
      <div class="tabs">
        ${states
          .map(
            (state) => `
              <button
                type="button"
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
  const height = 260;
  const margin = { top: 18, right: 18, bottom: 34, left: 44 };
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

  return `
    <svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(
      stateTitle(state),
    )} prediction chart">
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
      <path class="uncertainty" d="${bandPath}"></path>
      <path class="bound" d="${upperPath}"></path>
      <path class="bound" d="${lowerPath}"></path>
      <path class="prediction-line" d="${predictionPath}"></path>
      ${actuals
        .map(
          (point) => `
            <circle class="actual-point" cx="${x(point.timestamp).toFixed(
              1,
            )}" cy="${y(point.value).toFixed(1)}" r="5">
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
            <path class="chemical-point" d="M ${cx.toFixed(1)} ${(cy - 7).toFixed(
              1,
            )} L ${(cx + 7).toFixed(1)} ${cy.toFixed(1)} L ${cx.toFixed(1)} ${(
              cy + 7
            ).toFixed(1)} L ${(cx - 7).toFixed(1)} ${cy.toFixed(1)} Z">
              <title>${escapeHtml(point.summary || "Chemical addition")}</title>
            </path>
          `;
        })
        .join("")}
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

function shortTitle(state) {
  const entityId = state?.entity_id || "";
  const reading = Object.keys(READING_LABELS).find((key) => entityId.includes(key));
  return reading ? READING_LABELS[reading] : stateTitle(state).replace(" (Predicted)", "");
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
    ha-card {
      display: block;
      padding: 16px;
      overflow: hidden;
    }
    .header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }
    .title {
      color: ${COLORS.text};
      font-size: 18px;
      font-weight: 600;
      line-height: 1.2;
    }
    .subtitle {
      color: ${COLORS.secondary};
      font-size: 13px;
      margin-top: 3px;
    }
    .current {
      color: ${COLORS.text};
      font-size: 22px;
      font-weight: 600;
      line-height: 1;
      white-space: nowrap;
    }
    .tabs {
      display: flex;
      gap: 6px;
      margin-bottom: 12px;
      overflow-x: auto;
      padding-bottom: 2px;
    }
    button {
      appearance: none;
      border: 1px solid var(--divider-color);
      background: var(--card-background-color);
      color: ${COLORS.text};
      border-radius: 6px;
      cursor: pointer;
      font: inherit;
      min-height: 32px;
      padding: 0 10px;
      white-space: nowrap;
    }
    button.selected {
      border-color: ${COLORS.prediction};
      color: ${COLORS.prediction};
      font-weight: 600;
    }
    .chart {
      display: block;
      width: 100%;
      min-height: 260px;
    }
    .grid {
      stroke: ${COLORS.grid};
      stroke-width: 1;
    }
    .axis {
      fill: ${COLORS.secondary};
      font-size: 11px;
    }
    .uncertainty {
      fill: ${COLORS.uncertainty};
      stroke: none;
    }
    .bound {
      fill: none;
      stroke: ${COLORS.lowerUpper};
      stroke-dasharray: 4 4;
      stroke-width: 1.5;
    }
    .prediction-line {
      fill: none;
      stroke: ${COLORS.prediction};
      stroke-linecap: round;
      stroke-linejoin: round;
      stroke-width: 3;
    }
    .actual-point {
      fill: ${COLORS.actual};
      stroke: var(--card-background-color);
      stroke-width: 2;
    }
    .chemical-point {
      fill: ${COLORS.chemical};
      stroke: var(--card-background-color);
      stroke-width: 2;
    }
    .legend {
      align-items: center;
      color: ${COLORS.secondary};
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      font-size: 12px;
      margin-top: 8px;
    }
    .legend span {
      align-items: center;
      display: inline-flex;
      gap: 5px;
    }
    .line,
    .band,
    .dot,
    .diamond {
      display: inline-block;
      height: 10px;
      width: 10px;
    }
    .line {
      border-top: 3px solid ${COLORS.prediction};
      height: 0;
      width: 18px;
    }
    .band {
      background: ${COLORS.uncertainty};
      border: 1px solid ${COLORS.prediction};
    }
    .dot {
      background: ${COLORS.actual};
      border-radius: 50%;
    }
    .diamond {
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
