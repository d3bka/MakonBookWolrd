class PreTestConfigModal {
  constructor() {
    this.modes = [
      { id: "full_test", title: "Full Test", desc: "All modules (RW + Math)", baseMin: 134, isDefault: true, icon: "bi-bullseye" },
      { id: "rw_only", title: "English Only", desc: "Both RW modules", baseMin: 64, icon: "bi-book" },
      { id: "math_only", title: "Math Only", desc: "Both Math modules", baseMin: 70, icon: "bi-calculator" },
      { id: "single_module", title: "Single Module", desc: "Practice one module", baseMin: 32, icon: "bi-lightning-charge" }
    ];
    this.subModes = [
      { id: "single_english_m1", title: "Eng M1", baseMin: 32 },
      { id: "single_english_m2", title: "Eng M2", baseMin: 32 },
      { id: "single_math_m1", title: "Math M1", baseMin: 35 },
      { id: "single_math_m2", title: "Math M2", baseMin: 35 }
    ];
    this.integrityModes = [
      { id: "off", title: "Off", desc: "No Anti-Cheat monitoring." },
      { id: "standard", title: "Standard", desc: "3 strikes, tab/app, inactivity and fullscreen monitoring.", isDefault: true },
      { id: "strict", title: "Strict", desc: "Standard + copy/paste, right-click and shortcut protection." }
    ];
    this.state = {
      mode: "full_test",
      integrity: "standard",
      testName: null,
      classroomId: null,
      targetHref: null
    };
    this._buildDOM();
    this._bindEvents();
  }

  _buildDOM() {
    if (document.getElementById("ptc-overlay")) return;
    const overlay = document.createElement("div");
    overlay.id = "ptc-overlay";
    overlay.className = "ptc-overlay";

    const modeHtml = this.modes.map(m => `
      <div class="ptc-mode-card ${m.isDefault ? "is-active" : ""}" data-id="${m.id}">
        <div class="ptc-radio-wrapper"><div class="ptc-radio"></div></div>
        <div class="ptc-mode-info">
          <div class="ptc-mode-title-wrapper">
            <i class="bi ${m.icon} ptc-mode-icon"></i>
            <div class="ptc-mode-title">${m.title}</div>
          </div>
          <div class="ptc-mode-desc">${m.desc}</div>
          <div class="ptc-badge" id="ptc-badge-${m.id}">${this._fmt(m.baseMin)}</div>
        </div>
      </div>
    `).join("");

    const integrityHtml = this.integrityModes.map(m => `
      <div class="ptc-integrity-card ${m.isDefault ? "is-active" : ""}" data-integrity="${m.id}">
        <strong>${m.title}</strong>
        <span>${m.desc}</span>
      </div>
    `).join("");

    overlay.innerHTML = `
      <div class="ptc-dialog" role="dialog" aria-modal="true" aria-label="Configure practice test">
        <div class="ptc-section-title">Choose module</div>
        <div class="ptc-mode-grid">${modeHtml}</div>

        <div class="ptc-submode-container" id="ptc-submode-container" style="display:none;margin-top:12px;animation:ptcFadeIn .2s ease-out;">
          <div class="ptc-submode-grid">
            ${this.subModes.map(sm => `
              <div class="ptc-submode-card" data-sub="${sm.id}">${sm.title}</div>
            `).join("")}
          </div>
        </div>

        <div class="ptc-section-title">Exam Integrity</div>
        <div class="ptc-integrity-grid">${integrityHtml}</div>
        <div class="ptc-integrity-note" id="ptc-integrity-note">
          Standard uses the 3-strike Anti-Cheat system. You can change this before opening the test cover.
        </div>

        <div class="ptc-summary">
          <div>
            <div class="ptc-summary-label">Estimated Duration</div>
            <div class="ptc-summary-val" id="ptc-total-time">2h 14min</div>
          </div>
          <div style="text-align:right;">
            <div class="ptc-summary-label">Protection</div>
            <div class="ptc-summary-val" id="ptc-integrity-setting" style="font-size:1.1rem;font-weight:500;">Standard</div>
          </div>
        </div>

        <div class="ptc-footer">
          <button class="ptc-btn ptc-btn-cancel" id="ptc-btn-cancel">Cancel</button>
          <button class="ptc-btn ptc-btn-start" id="ptc-btn-start">
            <span>Continue</span>
            <i class="bi bi-arrow-right" style="font-size:1.05rem;line-height:1;"></i>
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);
    this.el = overlay;
    this._updateUI();
  }

  _bindEvents() {
    this.el.addEventListener("click", e => {
      if (e.target === this.el) this.close();
    });
    this.el.querySelector("#ptc-btn-cancel").addEventListener("click", () => this.close());

    this.el.querySelectorAll(".ptc-mode-card").forEach(card => {
      card.addEventListener("click", () => {
        const clickedMode = card.getAttribute("data-id");
        this.state.mode = clickedMode === "single_module" ? "single_english_m1" : clickedMode;
        this._updateUI();
      });
    });

    this.el.querySelectorAll(".ptc-submode-card").forEach(card => {
      card.addEventListener("click", () => {
        if (!this.state.mode.startsWith("single_")) return;
        this.state.mode = card.getAttribute("data-sub");
        this._updateUI();
      });
    });

    this.el.querySelectorAll(".ptc-integrity-card").forEach(card => {
      card.addEventListener("click", () => {
        this.state.integrity = card.getAttribute("data-integrity") || "standard";
        this._updateUI();
        try { localStorage.setItem("makonbook:practice-integrity-mode", this.state.integrity); } catch (_e) {}
      });
    });

    this.el.querySelector("#ptc-btn-start").addEventListener("click", () => this._continueToCover());
  }

  _fmt(min) {
    if (min < 60) return `${min} min`;
    const h = Math.floor(min / 60);
    const m = min % 60;
    return m > 0 ? `${h}h ${m}min` : `${h}h`;
  }

  _currentMode() {
    return this.modes.find(m => m.id === this.state.mode) ||
           this.subModes.find(m => m.id === this.state.mode) ||
           this.modes[0];
  }

  _updateUI() {
    const isSingle = this.state.mode.startsWith("single_");
    const parentModeId = isSingle ? "single_module" : this.state.mode;

    this.el.querySelectorAll(".ptc-mode-card").forEach(card => {
      card.classList.toggle("is-active", card.getAttribute("data-id") === parentModeId);
    });

    const subContainer = this.el.querySelector("#ptc-submode-container");
    if (isSingle) {
      subContainer.style.display = "block";
      this.el.querySelectorAll(".ptc-submode-card").forEach(card => {
        card.classList.toggle("is-active", card.getAttribute("data-sub") === this.state.mode);
      });
    } else {
      subContainer.style.display = "none";
    }

    this.el.querySelectorAll(".ptc-integrity-card").forEach(card => {
      card.classList.toggle("is-active", card.getAttribute("data-integrity") === this.state.integrity);
    });

    const mode = this._currentMode();
    this.el.querySelector("#ptc-total-time").textContent = this._fmt(mode.baseMin);
    this.el.querySelector("#ptc-integrity-setting").textContent =
      this.state.integrity.charAt(0).toUpperCase() + this.state.integrity.slice(1);

    const note = this.el.querySelector("#ptc-integrity-note");
    if (this.state.classroomId) {
      note.textContent = "Classroom Anti-Cheat policy is managed by the teacher and may override this selection.";
    } else if (this.state.integrity === "off") {
      note.textContent = "Anti-Cheat is off. No strikes, fullscreen requirement or tab/app monitoring.";
    } else if (this.state.integrity === "strict") {
      note.textContent = "Strict adds copy/paste, right-click and restricted shortcut protection.";
    } else {
      note.textContent = "Standard uses the 3-strike system and monitors tab/app switching, inactivity and fullscreen exit.";
    }
  }

  _continueToCover() {
    if (!this.state.targetHref) return;

    const url = new URL(this.state.targetHref, window.location.href);
    url.searchParams.set("configured", "1");
    url.searchParams.set("test_mode", this.state.mode);
    url.searchParams.set("integrity_mode", this.state.integrity);
    url.searchParams.set("integrity_max_violations", "3");
    url.searchParams.set("integrity_fullscreen_required", this.state.integrity === "off" ? "0" : "1");
    window.location.href = url.toString();
  }

  open(testName, classroomId = null, href = null) {
    this.state.testName = testName;
    this.state.classroomId = classroomId;
    this.state.targetHref = href;

    try {
      const saved = localStorage.getItem("makonbook:practice-integrity-mode");
      if (saved === "off" || saved === "standard" || saved === "strict") {
        this.state.integrity = saved;
      }
    } catch (_e) {}

    this._updateUI();
    this.el.classList.add("is-open");
  }

  close() {
    this.el.classList.remove("is-open");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.PreTestConfig = new PreTestConfigModal();

  document.querySelectorAll(".practice-action[data-practice-navigate]").forEach(link => {
    link.addEventListener("click", function(e) {
      const href = this.getAttribute("href") || "";
      let testName = null;
      let classroomId = null;

      const mClassroom = href.match(/\/classroom\/(\d+)\/practice\/([^/?#]+)/);
      if (mClassroom) {
        classroomId = mClassroom[1];
        testName = decodeURIComponent(mClassroom[2]);
      } else {
        const m = href.match(/\/practise\/([^/?#]+)/);
        if (m) testName = decodeURIComponent(m[1]);
      }

      if (!testName) return;

      e.preventDefault();
      window.PreTestConfig.open(testName, classroomId, href);
    });
  });
});
