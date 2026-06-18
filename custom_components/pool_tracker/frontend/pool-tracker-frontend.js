const CARD_TAG = "pool-tracker-graph-card";
const PANEL_TAG = "pool-tracker-panel";

const READING_LABELS = {
  free_chlorine: "Free chlorine",
  ph: "pH",
  total_alkalinity: "Total alkalinity",
  cya: "CYA/stabilizer",
};

const WATER_READING_FIELDS = [
  { key: "free_chlorine", label: "Free chlorine", unit: "ppm", step: "0.1" },
  { key: "ph", label: "pH", unit: "", step: "0.1", max: "14" },
  { key: "total_alkalinity", label: "Total alkalinity", unit: "ppm", step: "1" },
  { key: "cya", label: "CYA/stabilizer", unit: "ppm", step: "1" },
];

const WATER_CLARITY_OPTIONS = ["", "clear", "hazy", "cloudy", "green", "other"];
const TESTING_METHOD_OPTIONS = [
  "",
  "strips",
  "drop_test",
  "digital_meter",
  "photometer",
  "pool_store",
  "other",
];
const CHEMICAL_SUGGESTIONS = [
  "dichlor",
  "trichlor",
  "calcium hypochlorite",
  "liquid chlorine",
  "bleach",
  "muriatic acid",
  "soda ash",
  "baking soda",
  "cyanuric acid",
  "salt",
  "algaecide",
  "clarifier",
  "calcium hardness increaser",
];
const UNIT_SUGGESTIONS = [
  "g",
  "kg",
  "oz",
  "lb",
  "mL",
  "L",
  "Tbsp",
  "fl. oz.",
  "gal",
];

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
    this._message = undefined;
    this._pending = false;
  }

  setConfig(config) {
    this._config = config || {};
    this._selectedEntityId = this._config.entity;
    this._render({ preserveFormState: false });
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

  _render(options = {}) {
    if (!this.shadowRoot) {
      return;
    }
    const { preserveFormState = true } = options;
    const formState = preserveFormState ? this._captureFormState() : [];

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

    this._restoreFormState(formState);
    for (const button of this.shadowRoot.querySelectorAll("button[data-entity]")) {
      button.addEventListener("click", () => {
        this._selectedEntityId = button.dataset.entity;
        this._message = undefined;
        this._render({ preserveFormState: false });
      });
    }
    this.shadowRoot
      .querySelector("form[data-log='water-test']")
      ?.addEventListener("submit", (event) => this._submitWaterTest(event));
    this.shadowRoot
      .querySelector("form[data-log='chemical-addition']")
      ?.addEventListener("submit", (event) => this._submitChemicalAddition(event));
    for (const button of this.shadowRoot.querySelectorAll("button[data-quick-chemical]")) {
      button.addEventListener("click", () => this._repeatChemicalAddition(button));
    }
  }

  _captureFormState() {
    return Array.from(this.shadowRoot.querySelectorAll("form[data-log]")).map(
      (form) => ({
        log: form.dataset.log,
        values: Array.from(form.elements)
          .filter(
            (element) =>
              element.name &&
              element.type !== "hidden" &&
              element.type !== "submit",
          )
          .map((element) => [element.name, element.value]),
      }),
    );
  }

  _restoreFormState(formState) {
    for (const savedForm of formState) {
      const form = this.shadowRoot.querySelector(
        `form[data-log='${savedForm.log}']`,
      );
      if (!form) {
        continue;
      }
      for (const [name, value] of savedForm.values) {
        const field = form.elements[name];
        if (field && field.type !== "hidden") {
          field.value = value;
        }
      }
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
      ${this._renderLogTools(selected)}
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

  _renderLogTools(selected) {
    const attrs = selected.attributes || {};
    const quickAdds = attrs.quick_chemical_additions || [];
    return `
      <div class="log-tools">
        ${this._message ? `<div class="message ${escapeHtml(this._message.type)}">${escapeHtml(this._message.text)}</div>` : ""}
        <div class="quick-panel">
          <div class="section-title">Quick chemicals</div>
          <div class="quick-actions">
            ${
              quickAdds.length
                ? quickAdds
                    .map(
                      (action) => `
                        <button
                          type="button"
                          class="quick-button"
                          data-quick-chemical
                          data-chemical="${escapeHtml(action.chemical || "")}"
                          data-amount="${escapeHtml(action.amount || "")}"
                          data-unit="${escapeHtml(action.unit || "")}"
                          ${this._pending ? "disabled" : ""}
                        >
                          <ha-icon icon="mdi:repeat"></ha-icon>
                          <span>${escapeHtml(action.summary || chemicalSummary(action))}</span>
                        </button>
                      `,
                    )
                    .join("")
                : `<span class="muted">Log a chemical addition to create a repeat.</span>`
            }
          </div>
        </div>
        <div class="forms">
          ${this._renderWaterTestForm(attrs)}
          ${this._renderChemicalForm(attrs)}
        </div>
      </div>
    `;
  }

  _renderWaterTestForm(attrs) {
    return `
      <form class="log-form" data-log="water-test">
        <div class="section-title">Log test</div>
        ${poolHiddenInput(attrs)}
        <div class="field-grid readings">
          ${WATER_READING_FIELDS.map(
            (field) => `
              <label>
                <span>${escapeHtml(field.label)}</span>
                <input
                  name="${escapeHtml(field.key)}"
                  inputmode="decimal"
                  type="number"
                  min="0"
                  ${field.max ? `max="${escapeHtml(field.max)}"` : ""}
                  step="${escapeHtml(field.step)}"
                  placeholder="${escapeHtml(field.unit)}"
                >
              </label>
            `,
          ).join("")}
        </div>
        <div class="field-grid">
          <label>
            <span>Clarity</span>
            <select name="water_clarity">
              ${WATER_CLARITY_OPTIONS.map(
                (value) => `<option value="${escapeHtml(value)}">${escapeHtml(value ? labelFor(value) : "None")}</option>`,
              ).join("")}
            </select>
          </label>
          <label>
            <span>Method</span>
            <select name="testing_method">
              ${TESTING_METHOD_OPTIONS.map(
                (value) => `<option value="${escapeHtml(value)}">${escapeHtml(value ? labelFor(value) : "Pool default")}</option>`,
              ).join("")}
            </select>
          </label>
        </div>
        <label>
          <span>When</span>
          <input name="event_timestamp" type="datetime-local">
        </label>
        <label>
          <span>Notes</span>
          <textarea name="notes" rows="2"></textarea>
        </label>
        <button type="submit" class="primary" ${this._pending ? "disabled" : ""}>
          <ha-icon icon="mdi:test-tube"></ha-icon>
          <span>Log test</span>
        </button>
      </form>
    `;
  }

  _renderChemicalForm(attrs) {
    return `
      <form class="log-form" data-log="chemical-addition">
        <div class="section-title">Log chemical</div>
        ${poolHiddenInput(attrs)}
        <div class="field-grid chemical-fields">
          <label>
            <span>Chemical</span>
            <select name="chemical" required>
              <option value="">Choose</option>
              ${CHEMICAL_SUGGESTIONS.map(
                (value) => `<option value="${escapeHtml(value)}">${escapeHtml(labelFor(value))}</option>`,
              ).join("")}
            </select>
          </label>
          <label>
            <span>Amount</span>
            <input name="amount" inputmode="decimal" type="number" min="0" step="any" required>
          </label>
          <label>
            <span>Unit</span>
            <select name="unit" required>
              <option value="">Unit</option>
              ${UNIT_SUGGESTIONS.map(
                (value) => `<option value="${escapeHtml(value)}">${escapeHtml(labelFor(value))}</option>`,
              ).join("")}
            </select>
          </label>
        </div>
        <label>
          <span>When</span>
          <input name="event_timestamp" type="datetime-local">
        </label>
        <label>
          <span>Notes</span>
          <textarea name="notes" rows="2"></textarea>
        </label>
        <button type="submit" class="primary" ${this._pending ? "disabled" : ""}>
          <ha-icon icon="mdi:flask-plus-outline"></ha-icon>
          <span>Log chemical</span>
        </button>
      </form>
    `;
  }

  async _submitWaterTest(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = payloadBase(form);
    for (const field of WATER_READING_FIELDS) {
      const value = form.elements[field.key]?.value;
      if (value !== undefined && value !== "") {
        payload[field.key] = Number(value);
      }
    }
    for (const key of ["water_clarity", "testing_method", "notes", "event_timestamp"]) {
      const value = form.elements[key]?.value?.trim();
      if (value) {
        payload[key] = value;
      }
    }
    if (!hasWaterTestContent(payload)) {
      this._setMessage("error", "Add at least one reading, clarity value, or note.");
      return;
    }
    await this._callService("log_water_test", payload, "Water test logged.", form);
  }

  async _submitChemicalAddition(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = payloadBase(form);
    for (const key of ["chemical", "amount", "unit", "notes", "event_timestamp"]) {
      const value = form.elements[key]?.value?.trim();
      if (value) {
        payload[key] = key === "amount" ? Number(value) : value;
      }
    }
    await this._callService(
      "log_chemical_addition",
      payload,
      "Chemical addition logged.",
      form,
    );
  }

  async _repeatChemicalAddition(button) {
    const payload = {
      source: "card",
      chemical: button.dataset.chemical,
      amount: Number(button.dataset.amount),
      unit: button.dataset.unit,
    };
    const poolId = selectedPoolId(this.shadowRoot);
    if (poolId) {
      payload.pool_id = poolId;
    }
    await this._callService(
      "log_chemical_addition",
      payload,
      `${chemicalSummary(payload)} logged.`,
    );
  }

  async _callService(service, payload, successMessage, form) {
    if (!this._hass) {
      return;
    }
    this._pending = true;
    this._message = undefined;
    try {
      await this._hass.callService("pool_tracker", service, payload);
      form?.reset();
      this._setMessage("success", successMessage);
    } catch (error) {
      this._setMessage("error", error?.message || "Unable to log record.");
    } finally {
      this._pending = false;
      this._render();
    }
  }

  _setMessage(type, text) {
    this._message = { type, text };
    this._render();
  }
}

class PoolTrackerPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    this._hass = hass;
    this._ensureCard();
    this._card.hass = hass;
  }

  set panel(panel) {
    this._panel = panel;
    this._ensureCard();
  }

  _ensureCard() {
    if (!this.shadowRoot || this._card) {
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
    this._card = this.shadowRoot.querySelector(CARD_TAG);
    this._card.setConfig({ title: "Pool Tracker" });
    if (this._hass) {
      this._card.hass = this._hass;
    }
  }
}

function poolHiddenInput(attrs) {
  return attrs.pool_id
    ? `<input type="hidden" name="pool_id" value="${escapeHtml(attrs.pool_id)}">`
    : "";
}

function payloadBase(form) {
  const payload = { source: "card" };
  const poolId = form.elements.pool_id?.value?.trim();
  if (poolId) {
    payload.pool_id = poolId;
  }
  return payload;
}

function selectedPoolId(root) {
  return root?.querySelector("input[name='pool_id']")?.value?.trim();
}

function hasWaterTestContent(payload) {
  return [
    "free_chlorine",
    "ph",
    "total_alkalinity",
    "cya",
    "water_clarity",
    "notes",
  ].some((key) => payload[key] !== undefined && payload[key] !== "");
}

function labelFor(value) {
  const labels = {
    drop_test: "Drop test",
    digital_meter: "Digital meter",
    pool_store: "Pool store",
    swim_spa: "Swim spa",
    salt_chlorine_generator: "Salt chlorine generator",
    ph: "pH",
    cya: "CYA/stabilizer",
    mL: "Milliliters",
    L: "Liters",
    Tbsp: "Tablespoons",
    "fl. oz.": "Fluid ounces",
    g: "Grams",
    kg: "Kilograms",
    oz: "Ounces",
    lb: "Pounds",
    gal: "Gallons",
  };
  if (labels[value]) {
    return labels[value];
  }
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function chemicalSummary(action) {
  const amount = formatNumber(action.amount);
  return `${action.chemical}: ${amount} ${action.unit}`;
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
  const margin = { top: 16, right: 16, bottom: 34, left: 46 };
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
      --pool-tracker-title-font-size: var(--ha-card-header-font-size, 24px);
      --pool-tracker-title-font-weight: var(--ha-font-weight-normal, 400);
      --pool-tracker-primary-font-size: var(--paper-font-body1_-_font-size, 14px);
      --pool-tracker-secondary-font-size: var(--paper-font-caption_-_font-size, 12px);
      --pool-tracker-state-font-size: var(--paper-font-display1_-_font-size, 34px);
      --pool-tracker-chart-height: 260px;
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
      gap: 16px;
      padding: 20px 16px 8px;
    }
    .title {
      color: ${COLORS.text};
      font-size: var(--pool-tracker-title-font-size);
      font-weight: var(--pool-tracker-title-font-weight);
      line-height: 1.2;
    }
    .subtitle {
      color: ${COLORS.secondary};
      font-size: var(--pool-tracker-primary-font-size);
      line-height: 20px;
      margin-top: 2px;
    }
    .state-block {
      text-align: right;
    }
    .current {
      color: ${COLORS.text};
      font-size: var(--pool-tracker-state-font-size);
      font-weight: 400;
      line-height: 36px;
      white-space: nowrap;
    }
    .state-label {
      color: ${COLORS.secondary};
      font-size: var(--pool-tracker-secondary-font-size);
      line-height: 16px;
      margin-top: 4px;
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
      font-size: var(--pool-tracker-primary-font-size);
      min-height: 40px;
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
      font-size: 12px;
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
      font-size: var(--pool-tracker-secondary-font-size);
      line-height: 18px;
      padding: 0 16px 16px;
    }
    .meta-row span {
      align-items: center;
      display: inline-flex;
      gap: 6px;
    }
    .log-tools {
      border-top: 1px solid ${COLORS.grid};
      padding: 16px;
    }
    .section-title {
      color: ${COLORS.text};
      font-size: var(--pool-tracker-primary-font-size);
      font-weight: var(--ha-font-weight-medium, 500);
      line-height: 20px;
      margin-bottom: 10px;
    }
    .quick-panel {
      margin-bottom: 16px;
    }
    .quick-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .quick-button,
    .primary {
      align-items: center;
      border: 1px solid ${COLORS.grid};
      border-radius: 6px;
      display: inline-flex;
      gap: 8px;
      justify-content: center;
      min-height: 40px;
      padding: 0 12px;
    }
    .quick-button {
      color: ${COLORS.text};
      max-width: 100%;
    }
    .quick-button span,
    .primary span {
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .quick-button ha-icon,
    .primary ha-icon {
      --mdc-icon-size: 18px;
      flex: 0 0 auto;
    }
    .primary {
      background: ${COLORS.prediction};
      border-color: ${COLORS.prediction};
      color: var(--text-primary-color, #fff);
      margin-top: 2px;
      padding: 0 14px;
    }
    button:disabled {
      cursor: progress;
      opacity: 0.62;
    }
    .forms {
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .log-form {
      display: flex;
      flex-direction: column;
      gap: 10px;
      min-width: 0;
    }
    .field-grid {
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .field-grid.readings {
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }
    .field-grid.chemical-fields {
      grid-template-columns: minmax(120px, 1.4fr) minmax(80px, 0.8fr) minmax(88px, 0.8fr);
    }
    label {
      color: ${COLORS.secondary};
      display: flex;
      flex-direction: column;
      font-size: var(--pool-tracker-secondary-font-size);
      gap: 4px;
      min-width: 0;
    }
    input,
    select,
    textarea {
      background: var(--mdc-text-field-fill-color, transparent);
      border: 1px solid ${COLORS.grid};
      border-radius: 6px;
      box-sizing: border-box;
      color: ${COLORS.text};
      font: inherit;
      font-size: var(--pool-tracker-primary-font-size);
      min-height: 38px;
      padding: 8px;
      width: 100%;
    }
    textarea {
      min-height: 66px;
      resize: vertical;
    }
    .message {
      border-radius: 6px;
      font-size: var(--pool-tracker-primary-font-size);
      line-height: 20px;
      margin-bottom: 12px;
      padding: 10px 12px;
    }
    .message.success {
      background: color-mix(in srgb, ${COLORS.actual} 14%, transparent);
      color: ${COLORS.text};
    }
    .message.error {
      background: color-mix(in srgb, var(--error-color, #db4437) 14%, transparent);
      color: ${COLORS.text};
    }
    .muted {
      color: ${COLORS.secondary};
      font-size: var(--pool-tracker-secondary-font-size);
      line-height: 18px;
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
    @media (max-width: 720px) {
      .forms,
      .field-grid,
      .field-grid.readings,
      .field-grid.chemical-fields {
        grid-template-columns: 1fr;
      }
      .header {
        flex-direction: column;
      }
      .state-block {
        text-align: left;
      }
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
