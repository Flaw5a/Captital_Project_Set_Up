// Page 1: enable/disable Standard/Light per department; auto-select the only option.
(function () {
  const form = document.getElementById("p1");
  if (form) {
    const deps = JSON.parse(form.dataset.deps || "[]");
    const byName = Object.fromEntries(deps.map((d) => [d.name, d]));
    const dept = document.getElementById("department");
    const radios = () => Array.from(document.querySelectorAll('input[name="structure"]'));

    function sync() {
      const d = byName[dept.value];
      radios().forEach((r) => {
        const allowed = d ? d[r.value] : false;
        r.disabled = !allowed;
        r.parentElement.style.opacity = allowed ? "1" : ".4";
        if (!allowed && r.checked) r.checked = false;
      });
      if (d) {
        const allowed = radios().filter((r) => !r.disabled);
        if (allowed.length === 1 && !allowed[0].checked) allowed[0].checked = true;
      }
    }
    dept.addEventListener("change", sync);
    sync();

    // ---- Postcode lookup + map ----------------------------------------
    const pc = document.getElementById("postcode");
    const btn = document.getElementById("pcLookup");
    const status = document.getElementById("pcStatus");
    const addr = document.getElementById("site_address");
    const addrPick = document.getElementById("addrPick");
    const mapEl = document.getElementById("map");
    const linksEl = document.getElementById("mapLinks");
    let map, marker;

    function renderLinks(d) {
      const parts = [];
      if (d.google_maps_url) parts.push(`<a href="${d.google_maps_url}" target="_blank" rel="noopener">Google Maps</a>`);
      if (d.google_earth_url) parts.push(`<a href="${d.google_earth_url}" target="_blank" rel="noopener">Google Earth</a>`);
      if (d.osm_url) parts.push(`<a href="${d.osm_url}" target="_blank" rel="noopener">OpenStreetMap</a>`);
      linksEl.innerHTML = parts.length ? "View: " + parts.join(" &middot; ") : "";
    }

    function showMap(lat, lon, label) {
      if (typeof L === "undefined" || lat == null) { mapEl.classList.add("hidden"); return; }
      mapEl.classList.remove("hidden");
      if (!map) {
        map = L.map(mapEl).setView([lat, lon], 16);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19, attribution: "© OpenStreetMap",
        }).addTo(map);
      } else {
        map.setView([lat, lon], 16);
      }
      if (marker) marker.remove();
      marker = L.marker([lat, lon]).addTo(map).bindPopup(label || "").openPopup();
      setTimeout(() => map.invalidateSize(), 100);
    }

    async function lookup() {
      const v = (pc.value || "").trim();
      if (!v) { status.textContent = ""; return; }
      status.textContent = "Looking up…";
      try {
        const r = await fetch("/api/postcode?pc=" + encodeURIComponent(v));
        const d = await r.json();
        renderLinks(d);
        if (d.valid) {
          status.textContent = d.area ? `Found: ${d.area}` : "Postcode found.";
          if (!addr.value && d.area) addr.value = `${d.area}, ${v.toUpperCase()}`;
          showMap(d.latitude, d.longitude, d.area || v.toUpperCase());
        } else {
          status.textContent = d.error || "Not found.";
        }
        // Full PAF addresses (only when a getAddress.io key is configured).
        if (d.addresses && d.addresses.length) {
          addrPick.innerHTML = '<option value="">— pick full address —</option>' +
            d.addresses.map((a) => `<option value="${a}">${a}</option>`).join("");
          addrPick.classList.remove("hidden");
        } else {
          addrPick.classList.add("hidden");
        }
      } catch (e) {
        status.textContent = "Lookup unavailable — enter address manually.";
        renderLinks({ google_maps_url: "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(v),
                      google_earth_url: "https://earth.google.com/web/search/" + encodeURIComponent(v) });
      }
    }

    if (btn) btn.addEventListener("click", lookup);
    if (pc) pc.addEventListener("blur", () => { if (pc.value.trim()) lookup(); });
    if (addrPick) addrPick.addEventListener("change", () => { if (addrPick.value) addr.value = addrPick.value; });
    if (pc && pc.value.trim()) lookup();
  }

  // Page 2: filter, select-all, per-group toggles, live count.
  const p2 = document.getElementById("p2");
  if (!p2) return;
  const filter = document.getElementById("filter");
  const selectAll = document.getElementById("selectAll");
  const selCount = document.getElementById("selCount");
  const fchks = () => Array.from(p2.querySelectorAll(".fchk"));

  function updateCount() {
    selCount.textContent = fchks().filter((c) => c.checked).length;
  }
  function syncGroup(section) {
    const boxes = Array.from(section.querySelectorAll(".fchk")).filter((c) => c.closest(".filerow").style.display !== "none");
    const grpAll = section.querySelector(".grpAll");
    grpAll.checked = boxes.length > 0 && boxes.every((c) => c.checked);
  }

  p2.querySelectorAll(".group").forEach((section) => {
    section.querySelector(".grpAll").addEventListener("change", (e) => {
      section.querySelectorAll(".fchk").forEach((c) => {
        if (c.closest(".filerow").style.display !== "none") c.checked = e.target.checked;
      });
      updateCount();
    });
  });
  p2.addEventListener("change", (e) => {
    if (e.target.classList.contains("fchk")) {
      syncGroup(e.target.closest(".group"));
      updateCount();
    }
  });
  if (selectAll) {
    selectAll.addEventListener("change", () => {
      fchks().forEach((c) => {
        if (c.closest(".filerow").style.display !== "none") c.checked = selectAll.checked;
      });
      p2.querySelectorAll(".group").forEach(syncGroup);
      updateCount();
    });
  }
  if (filter) {
    filter.addEventListener("input", () => {
      const q = filter.value.toLowerCase();
      p2.querySelectorAll(".filerow").forEach((row) => {
        row.style.display = row.textContent.toLowerCase().includes(q) ? "" : "none";
      });
      p2.querySelectorAll(".group").forEach(syncGroup);
    });
  }
  updateCount();
})();
