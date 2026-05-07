/**
 * JELD-WEN Interior Door Pricing Tool
 * Pure price lookup — no quantity, with door style images.
 */
(function () {
  'use strict';

  // ── Style → image URL map ────────────────────────────────────
  const STYLE_IMAGES = {
    'primed hardboard':      'https://edge.sitecorecloud.io/jeldwencanada1-jeldwen-p523-e8d9/media/Project/JeldWen/JeldWenCanada/Products/CAT009/S000122840/WebP-Images/JWC-WW-VC-DF_Slab_Fibre_AllPanel_Flush.webp?iar=0',
    'primed hardb':          'https://edge.sitecorecloud.io/jeldwencanada1-jeldwen-p523-e8d9/media/Project/JeldWen/JeldWenCanada/Products/CAT009/S000122840/WebP-Images/JWC-WW-VC-DF_Slab_Fibre_AllPanel_Flush.webp?iar=0',
    'colonist text':         'https://edge.sitecorecloud.io/jeldwencanada1-jeldwen-p523-e8d9/media/Project/JeldWen/JeldWenCanada/Products/CAT009/S000122840/WebP-Images/JWC-WW-VC-DF_Slab_Fibre_AllPanel_6.webp?iar=0',
    'colonial moulded':      'https://edge.sitecorecloud.io/jeldwencanada1-jeldwen-p523-e8d9/media/Project/JeldWen/JeldWenCanada/Products/CAT009/S000122840/WebP-Images/JWC-WW-VC-DF_Slab_Fibre_AllPanel_6.webp?iar=0',
    'craftsman':             'https://edge.sitecorecloud.io/jeldwencanada1-jeldwen-p523-e8d9/media/Project/JeldWen/JeldWenCanada/Products/CAT009/S000122840/WebP-Images/1-3-Panel---2-Narrow-Panels---Shaker.webp?iar=0',
    'flat moulded (shaker)': 'https://edge.sitecorecloud.io/jeldwencanada1-jeldwen-p523-e8d9/media/Project/JeldWen/JeldWenCanada/Products/CAT009/S000122840/WebP-Images/1-3-Panel---2-Narrow-Panels---Shaker.webp?iar=0',
    'camden':                'https://edge.sitecorecloud.io/jeldwencanada1-jeldwen-p523-e8d9/media/Project/JeldWen/JeldWenCanada/Products/CAT009/S000122840/WebP-Images/2-Panel-Door.webp?iar=0',
    'carrara':               'https://edge.sitecorecloud.io/jeldwencanada1-jeldwen-p523-e8d9/media/Project/JeldWen/JeldWenCanada/Products/CAT009/S000122840/WebP-Images/2-Panel-Square.webp?iar=0',
    'birkdale':              'https://edge.sitecorecloud.io/jeldwencanada1-jeldwen-p523-e8d9/media/Project/JeldWen/JeldWenCanada/Products/CAT009/S000123096/WebP-Images/3-Square-Panel.webp?iar=0',
    'santa fe':              'https://edge.sitecorecloud.io/jeldwencanada1-jeldwen-p523-e8d9/media/Project/JeldWen/JeldWenCanada/Products/CAT009/S000123096/WebP-Images/JWC-WW-VC-DF_Slab_Steel_AllPanel_2ArchPlanked.webp?iar=0',
    'madison':               'https://images.homedepot.ca/productimages/p_1001888151.jpg?product-images=l',
    'conmore':               'images/conmore.jpg',
  };

  function getStyleImage(style) {
    return STYLE_IMAGES[style.toLowerCase().trim()] || null;
  }

  // ── State ────────────────────────────────────────────────────
  const state = {
    group: '', type: '', style: '', size: '', variant: '',
    activeAddons: new Set(),
    qty: 1,
    rebateApplied: true,
  };

  // ── Fallback rebate map (used if data file omits 'rebates') ─────
  const DEFAULT_REBATES = {
    'Group A':      0.1275,
    'Group B':      0.1275,
    'Group D':      0.1075,
    'Group F':      0.18,
    'HomeHardware': 0.21,
    'PQ East':      0.05,
    'Trimlite':     0.00,
  };

  function getRebatePct(group) {
    if (!group) return 0;
    const map = (DATA && DATA.rebates) || DEFAULT_REBATES;
    return Number(map[group]) || 0;
  }

  let DATA = null;

  // ── Helpers ──────────────────────────────────────────────────
  const el  = id => document.getElementById(id);
  const fmt = n  => (n !== null && n !== undefined) ? '$' + Number(n).toFixed(2) : '\u2014';

  function unique(arr) { return [...new Set(arr)]; }
  function esc(str) {
    return String(str ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ── Data accessors ───────────────────────────────────────────
  function getProducts(f = {}) {
    return DATA.products.filter(p =>
      (!f.group   || p.group   === f.group)   &&
      (!f.type    || p.type    === f.type)     &&
      (!f.style   || p.style   === f.style)   &&
      (!f.size    || p.size    === f.size)     &&
      (!f.variant || p.variant === f.variant)
    );
  }
  function getStyles() {
    return unique(getProducts({ group: state.group, type: state.type }).map(p => p.style)).sort();
  }
  function getSizes() {
    return unique(getProducts({ group: state.group, type: state.type, style: state.style }).map(p => p.size));
  }
  function getVariants() {
    return unique(getProducts({
      group: state.group, type: state.type, style: state.style, size: state.size
    }).map(p => p.variant));
  }
  function getBasePrice() {
    const hits = getProducts({
      group: state.group, type: state.type,
      style: state.style, size: state.size, variant: state.variant
    });
    return hits.length ? hits[0].price : null;
  }

  // Returns the matched product object (with optional qty_tiers), or null.
  function getCurrentProduct() {
    const hits = getProducts({
      group: state.group, type: state.type,
      style: state.style, size: state.size, variant: state.variant
    });
    return hits.length ? hits[0] : null;
  }

  // Pick the price for a given quantity from a qty_tiers list.
  // Returns { price, tier } where tier is the matching tier object (or null).
  function pickTierPrice(tiers, qty) {
    if (!Array.isArray(tiers) || !tiers.length) return { price: null, tier: null };
    const q = Math.max(1, qty || 1);
    let chosen = null;
    for (const t of tiers) {
      const lo = (t.min_qty == null) ? 1 : t.min_qty;
      const hi = (t.max_qty == null) ? Infinity : t.max_qty;
      if (q >= lo && q <= hi) { chosen = t; break; }
    }
    // Fallback: if none matched (e.g. qty above last tier max), use the last tier.
    if (!chosen) chosen = tiers[tiers.length - 1];
    const pn = (chosen && chosen.price_numeric != null) ? chosen.price_numeric : null;
    return { price: pn, tier: chosen };
  }

  // Format a tier's qty range as "1–1099" / "1100+".
  function fmtTierRange(tier) {
    if (!tier) return '';
    const lo = tier.min_qty == null ? 1 : tier.min_qty;
    const hi = tier.max_qty;
    return (hi == null) ? (lo + '+') : (lo + '\u2013' + hi);
  }
  function getGroupAddons() {
    if (!state.group) return [];
    return DATA.addons.filter(a => {
      if (a.group !== state.group) return false;
      if (state.type && a.applies_to && a.applies_to.length && !a.applies_to.includes(state.type)) return false;
      return true;
    });
  }

  // ── Init ─────────────────────────────────────────────────────
  function init() {
    if (!window.PRICING_DATA) { showFatalError('Pricing data not found. Make sure data/pricing_data.js is present.'); return; }
    DATA = window.PRICING_DATA;
    populateGroups();
    wireEvents();
    const m = DATA.meta || {};
    el('dataMetaLabel').textContent = (m.record_count ?? '?') + ' prices \u00b7 ' + (m.addon_count ?? '?') + ' add-ons';
    el('quoteDateDisplay').textContent = new Date().toLocaleDateString('en-CA');
    ['step-type', 'step-style', 'step-size', 'step-variant', 'step-addons', 'step-qty'].forEach(s => setStepEnabled(s, false));
    renderAddons();
    updatePriceDisplay();
    updateGroupBadge();
    updateDoorImage();
  }

  function populateGroups() {
    const sel = el('groupSelect');
    Object.entries(DATA.groups).forEach(([id, label]) => {
      const opt = document.createElement('option');
      opt.value = id; opt.textContent = label;
      sel.appendChild(opt);
    });
  }

  // ── Event wiring ─────────────────────────────────────────────
  function wireEvents() {
    el('groupSelect').addEventListener('change', onGroupChange);
    document.querySelectorAll('.type-btn').forEach(btn =>
      btn.addEventListener('click', () => onTypeChange(btn.dataset.type)));
    el('styleSelect').addEventListener('change', onStyleChange);
    el('sizeSelect').addEventListener('change', onSizeChange);
    el('variantSelect').addEventListener('change', onVariantChange);
    el('clearSelectionBtn').addEventListener('click', clearSelection);

    // Quantity controls
    const qtyInput = el('qtyInput');
    if (qtyInput) {
      qtyInput.addEventListener('input', onQtyChange);
      qtyInput.addEventListener('change', onQtyChange);
    }
    const qm = el('qtyMinus'); if (qm) qm.addEventListener('click', () => bumpQty(-1));
    const qp = el('qtyPlus');  if (qp) qp.addEventListener('click', () => bumpQty(+1));

    // Quantity-tier dropdown: pick a tier directly to set qty to its min.
    const qts = el('qtyTierSelect');
    if (qts) qts.addEventListener('change', onTierSelect);

    // Rebate toggle
    const rb = el('rebateApply');
    if (rb) rb.addEventListener('change', () => {
      state.rebateApplied = rb.checked;
      updatePriceDisplay();
    });
  }

  function onQtyChange() {
    const v = parseInt(el('qtyInput').value, 10);
    state.qty = (Number.isFinite(v) && v > 0) ? v : 1;
    updatePriceDisplay();
  }

  function bumpQty(delta) {
    const next = Math.max(1, (state.qty || 1) + delta);
    state.qty = next;
    el('qtyInput').value = next;
    updatePriceDisplay();
  }

  // Triggered when the user picks a quantity-break tier directly.
  // Sets qty to the tier's min so the rest of the pricing logic
  // (which keys off state.qty) automatically uses the tier's price.
  function onTierSelect() {
    const sel = el('qtyTierSelect');
    if (!sel) return;
    const idx = parseInt(sel.value, 10);
    const product = getCurrentProduct();
    if (!product || !Array.isArray(product.qty_tiers)) return;
    const tier = product.qty_tiers[idx];
    if (!tier) return;
    const lo = tier.min_qty == null ? 1 : tier.min_qty;
    state.qty = lo;
    const qi = el('qtyInput'); if (qi) qi.value = lo;
    updatePriceDisplay();
  }

  // ── Handlers ─────────────────────────────────────────────────
  function onGroupChange() {
    state.group = el('groupSelect').value;
    state.type = ''; state.style = ''; state.size = ''; state.variant = '';
    state.activeAddons.clear();
    resetTypeButtons();
    ['step-type','step-style','step-size','step-variant','step-addons','step-qty'].forEach(s => setStepEnabled(s, false));
    setStepEnabled('step-type', !!state.group);
    disableAndClear(['styleSelect', 'sizeSelect', 'variantSelect']);
    updateGroupBadge(); renderAddons(); updatePriceDisplay(); updateDoorImage(); updateConfigHint();
  }

  function onTypeChange(type) {
    if (state.type === type) return;
    state.type = type; state.style = ''; state.size = ''; state.variant = '';
    state.activeAddons.clear();
    document.querySelectorAll('.type-btn').forEach(b => b.classList.toggle('active', b.dataset.type === type));
    populateSelectEl('styleSelect', getStyles());
    el('styleSelect').disabled = false;
    disableAndClear(['sizeSelect', 'variantSelect']);
    setStepEnabled('step-style', true);
    setStepEnabled('step-size', false);
    setStepEnabled('step-variant', false);
    renderAddons(); updatePriceDisplay(); updateDoorImage(); updateConfigHint();
  }

  function onStyleChange() {
    state.style = el('styleSelect').value;
    state.size = ''; state.variant = '';
    if (state.style) {
      populateSizeSelect(getSizes());
      el('sizeSelect').disabled = false;
      setStepEnabled('step-size', true);
    } else {
      disableAndClear(['sizeSelect']);
      setStepEnabled('step-size', false);
    }
    disableAndClear(['variantSelect']);
    setStepEnabled('step-variant', false);
    updatePriceDisplay(); updateDoorImage(); updateConfigHint();
  }

  function onSizeChange() {
    state.size = el('sizeSelect').value;
    state.variant = '';
    if (state.size) {
      const variants = getVariants();
      populateSelectEl('variantSelect', variants);
      el('variantSelect').disabled = false;
      setStepEnabled('step-variant', true);
      if (variants.length === 1) {
        el('variantSelect').value = variants[0];
        state.variant = variants[0];
        setStepEnabled('step-addons', true);
        renderAddons();
      } else {
        setStepEnabled('step-addons', false);
      }
    } else {
      disableAndClear(['variantSelect']);
      setStepEnabled('step-variant', false);
      setStepEnabled('step-addons', false);
    }
    updatePriceDisplay(); updateConfigHint();
  }

  function onVariantChange() {
    state.variant = el('variantSelect').value;
    setStepEnabled('step-addons', !!state.variant);
    renderAddons(); updatePriceDisplay(); updateConfigHint();
  }

  function clearSelection() {
    state.type = ''; state.style = ''; state.size = ''; state.variant = '';
    state.activeAddons.clear();
    state.qty = 1;
    const qi = el('qtyInput'); if (qi) qi.value = 1;
    resetTypeButtons();
    disableAndClear(['styleSelect', 'sizeSelect', 'variantSelect']);
    ['step-style', 'step-size', 'step-variant', 'step-addons', 'step-qty'].forEach(s => setStepEnabled(s, false));
    if (state.group) setStepEnabled('step-type', true);
    renderAddons(); updatePriceDisplay(); updateDoorImage(); updateConfigHint();
  }

  // ── Door image ───────────────────────────────────────────────
  function updateDoorImage() {
    const wrap    = el('doorImageWrap');
    const img     = el('doorImageEl');
    const caption = el('doorImageCaption');
    if (!state.style) { wrap.style.display = 'none'; img.src = ''; return; }
    const url = getStyleImage(state.style);
    if (url) {
      img.style.display = '';
      img.src = url; img.alt = state.style;
      caption.textContent = state.style;
      wrap.classList.remove('no-image');
    } else {
      img.style.display = 'none'; img.src = '';
      caption.textContent = state.style + ' — Image unavailable';
      wrap.classList.add('no-image');
    }
    wrap.style.display = '';
  }

  // ── Select helpers ───────────────────────────────────────────
  function populateSelectEl(id, options) {
    const sel = el(id);
    sel.innerHTML = '<option value="">\u2014 Select \u2014</option>';
    options.forEach(val => {
      const opt = document.createElement('option');
      opt.value = val; opt.textContent = val;
      sel.appendChild(opt);
    });
  }

  function populateSizeSelect(sizes) {
    const sel = el('sizeSelect');
    sel.innerHTML = '';
    const base   = sizes.filter(s => /^\d+["']{1,2}\s*$/.test(s.trim()) || /^\d+["']\s+Euro/i.test(s));
    const ranges = sizes.filter(s => /\b(to|&)\b/.test(s) && !/add/i.test(s));
    const adders = sizes.filter(s => /\badd\b|height/i.test(s) || /\d+["'].*sc/i.test(s));
    const other  = sizes.filter(s => !base.includes(s) && !ranges.includes(s) && !adders.includes(s));
    const ph = document.createElement('option');
    ph.value = ''; ph.textContent = '\u2014 Select a size \u2014';
    sel.appendChild(ph);
    const makeGroup = (label, items) => {
      if (!items.length) return;
      const og = document.createElement('optgroup');
      og.label = label;
      items.forEach(val => {
        const opt = document.createElement('option');
        opt.value = val; opt.textContent = val; og.appendChild(opt);
      });
      sel.appendChild(og);
    };
    makeGroup('Sizes', base);
    makeGroup('Size Ranges', ranges);
    makeGroup('Other', other);
    makeGroup('Adders (add to base)', adders);
  }

  function disableAndClear(ids) {
    ids.forEach(id => {
      const sel = el(id);
      if (sel) { sel.innerHTML = '<option value="">\u2014 Select \u2014</option>'; sel.disabled = true; }
    });
  }

  // ── Add-ons ──────────────────────────────────────────────────
  function renderAddons() {
    const container = el('addonsList');
    const badge     = el('addonBadge');
    const allAddons = getGroupAddons();
    if (!allAddons.length) {
      container.innerHTML = '<p class="empty-addons">No add-ons available for this selection.</p>';
      badge.style.display = 'none';
      return;
    }
    const byCategory = {};
    allAddons.forEach(a => {
      const c = a.category || 'Other';
      (byCategory[c] = byCategory[c] || []).push(a);
    });
    let html = '';
    for (const [cat, addons] of Object.entries(byCategory)) {
      html += '<div class="addon-category"><div class="addon-cat-header">' + esc(cat) + '</div>';
      addons.forEach(addon => {
        const checked = state.activeAddons.has(addon.name);
        const safeId  = 'ao_' + addon.name.replace(/\W+/g, '_').toLowerCase().slice(0, 40);
        html += '<label class="addon-item' + (checked ? ' active' : '') + '" for="' + safeId + '">'
          + '<input type="checkbox" id="' + safeId + '" data-name="' + esc(addon.name) + '"' + (checked ? ' checked' : '') + '>'
          + '<span class="addon-name">' + esc(addon.name) + '</span>'
          + '<span class="addon-price">' + fmt(addon.price) + '</span></label>';
      });
      html += '</div>';
    }
    container.innerHTML = html;
    container.querySelectorAll('input[type="checkbox"]').forEach(cb => {
      cb.addEventListener('change', () => {
        const name = cb.dataset.name;
        cb.checked ? state.activeAddons.add(name) : state.activeAddons.delete(name);
        cb.closest('label').classList.toggle('active', cb.checked);
        updateAddonBadge(); updatePriceDisplay();
      });
    });
    updateAddonBadge();
  }

  function updateAddonBadge() {
    const badge = el('addonBadge');
    badge.style.display = state.activeAddons.size ? '' : 'none';
    if (state.activeAddons.size) badge.textContent = state.activeAddons.size + ' selected';
  }

  // ── Price display ────────────────────────────────────────────
  function updatePriceDisplay() {
    const product    = state.variant ? getCurrentProduct() : null;
    const qty        = Math.max(1, state.qty || 1);

    // Determine effective base price honoring qty_tiers if present
    let basePrice = product ? product.price : null;
    let activeTier = null;
    if (product && Array.isArray(product.qty_tiers) && product.qty_tiers.length) {
      const picked = pickTierPrice(product.qty_tiers, qty);
      if (picked.price !== null) {
        basePrice = picked.price;
        activeTier = picked.tier;
      }
    }

    const activeList = getGroupAddons().filter(a => state.activeAddons.has(a.name));
    const cardEmpty   = document.querySelector('.product-card-empty');
    const cardContent = document.querySelector('.product-card-content');

    if (state.variant) {
      cardEmpty.style.display = 'none'; cardContent.style.display = '';
      el('pcTypeBadge').textContent = state.type;
      el('pcTypeBadge').className   = 'pc-type-badge ' + state.type;
      el('pcGroupTag').textContent  = DATA.groups[state.group] || state.group;
      el('pcStyle').textContent     = state.style;
      el('pcMeta').textContent      = [state.size, state.variant].filter(Boolean).join(' \u00b7 ');
      if (basePrice !== null) {
        el('pcBasePrice').textContent = fmt(basePrice); el('pcBasePrice').className = 'pc-base-price';
      } else {
        el('pcBasePrice').textContent = 'Not Available'; el('pcBasePrice').className = 'pc-base-price na';
      }
    } else {
      cardEmpty.style.display = ''; cardContent.style.display = 'none';
    }

    el('basePriceDisplay').textContent = fmt(basePrice);
    el('basePriceDisplay').className   = basePrice === null ? 'pr-value na' : 'pr-value';

    const addonRows = el('addonPriceRows');
    addonRows.innerHTML = '';
    let addonTotal = 0;
    activeList.forEach(addon => {
      addonTotal += addon.price;
      const row = document.createElement('div');
      row.className = 'price-row addon-row';
      row.innerHTML = '<span class="addon-row-name" title="' + esc(addon.name) + '">+ ' + esc(addon.name) + '</span>'
        + '<span class="pr-value">' + fmt(addon.price) + '</span>';
      addonRows.appendChild(row);
    });

    // Per-unit total (base + addons). We intentionally do NOT multiply
    // by qty — for tiered-volume products the tier selection just picks
    // the per-unit price; we never want to calculate the cost of N doors.
    const perUnit  = basePrice !== null ? basePrice + addonTotal : null;
    const subtotal = perUnit;

    // The qty/subtotal rows are no longer used (single-unit pricing only).
    const qtyRow      = el('qtyRow');
    const subtotalRow = el('subtotalRow');
    if (qtyRow)      qtyRow.style.display = 'none';
    if (subtotalRow) subtotalRow.style.display = 'none';

    // Show tier badge under qty input when product uses qty_tiers
    const tierHint = el('qtyHint');
    if (tierHint) {
      if (product && Array.isArray(product.qty_tiers) && product.qty_tiers.length) {
        const lbl = activeTier ? ('Tier: qty ' + fmtTierRange(activeTier) + ' \u00b7 ' + fmt(basePrice) + ' / unit') : 'Quantity-break pricing';
        tierHint.textContent = lbl;
        tierHint.classList.add('tier-active');
      } else {
        tierHint.textContent = 'Optional \u00b7 applies to selected line';
        tierHint.classList.remove('tier-active');
      }
    }

    // Quantity-tier dropdown: only shown when this product has tiered pricing
    const tierRow = el('qtyTierRow');
    const tierSel = el('qtyTierSelect');
    if (tierRow && tierSel) {
      if (product && Array.isArray(product.qty_tiers) && product.qty_tiers.length > 1) {
        // Rebuild options if the tier set changed
        const desired = product.qty_tiers.map((t, i) => {
          const lo = t.min_qty == null ? 1 : t.min_qty;
          const hi = t.max_qty;
          const range = (hi == null) ? (lo + '+ units') : (lo + '\u2013' + hi + ' units');
          const price = (t.price_numeric != null) ? ('\u00a0\u00b7\u00a0' + fmt(t.price_numeric) + ' / unit') : '';
          return { value: String(i), label: range + price };
        });
        const currentSig = desired.map(o => o.value + ':' + o.label).join('|');
        if (tierSel.dataset.sig !== currentSig) {
          tierSel.innerHTML = '';
          desired.forEach(o => {
            const opt = document.createElement('option');
            opt.value = o.value;
            opt.textContent = o.label;
            tierSel.appendChild(opt);
          });
          tierSel.dataset.sig = currentSig;
        }
        // Sync selection to the currently active tier
        if (activeTier) {
          const activeIdx = product.qty_tiers.indexOf(activeTier);
          if (activeIdx >= 0) tierSel.value = String(activeIdx);
        }
        tierRow.style.display = '';
      } else {
        tierRow.style.display = 'none';
        tierSel.dataset.sig = '';
      }
    }

    // Rebate computation
    const rebatePct = getRebatePct(state.group);
    const rebateSection = el('rebateSection');
    const rebatePctLbl  = el('rebatePctLabel');
    const rebateDisp    = el('rebateDisplay');
    let rebateAmt = 0;
    if (rebatePct > 0 && subtotal !== null) {
      rebateSection.style.display = '';
      rebatePctLbl.textContent = (rebatePct * 100).toFixed(2).replace(/\.?0+$/, '') + '%';
      const rb = el('rebateApply');
      const apply = !!(rb && rb.checked) && state.rebateApplied;
      if (apply) {
        rebateAmt = subtotal * rebatePct;
        rebateDisp.textContent = '\u2212' + fmt(rebateAmt).replace('-', '');
        rebateDisp.classList.add('active');
      } else {
        rebateAmt = 0;
        rebateDisp.textContent = fmt(0);
        rebateDisp.classList.remove('active');
      }
    } else {
      rebateSection.style.display = 'none';
      rebateAmt = 0;
    }

    const total = subtotal !== null ? (subtotal - rebateAmt) : null;
    el('totalDisplay').textContent = fmt(total);
    el('totalDisplay').className   = total === null ? 'pr-value grand na' : 'pr-value grand';

    // Quantity step is only relevant for products with tiered volume pricing.
    const hasTiers = !!(product && Array.isArray(product.qty_tiers) && product.qty_tiers.length > 1);
    const qtyStep  = el('step-qty');
    if (qtyStep) qtyStep.style.display = hasTiers ? '' : 'none';
    setStepEnabled('step-qty', hasTiers);
  }

  // ── UI helpers ───────────────────────────────────────────────
  function setStepEnabled(stepId, enabled) {
    const card = el(stepId);
    if (card) card.classList.toggle('disabled', !enabled);
  }
  function resetTypeButtons() {
    document.querySelectorAll('.type-btn').forEach(b => b.classList.remove('active'));
  }
  function updateGroupBadge() {
    const badge = el('quoteGroupBadge');
    if (state.group) {
      badge.textContent = DATA.groups[state.group] || state.group;
      badge.className   = 'group-badge active';
    } else {
      badge.textContent = 'No Group Selected';
      badge.className   = 'group-badge';
    }
  }
  function updateConfigHint() {
    const hint = el('configHint');
    if (!state.group)   { hint.textContent = 'Start by selecting a dealer group above'; return; }
    if (!state.type)    { hint.textContent = 'Choose Door Slab or Bifold'; return; }
    if (!state.style)   { hint.textContent = 'Select a door style'; return; }
    if (!state.size)    { hint.textContent = 'Select a size'; return; }
    if (!state.variant) { hint.textContent = 'Select a core / variant'; return; }
    hint.textContent = 'Add optional upgrades below';
  }
  function showFatalError(msg) {
    document.body.innerHTML = '<div style="font-family:system-ui;max-width:520px;margin:80px auto;padding:2rem;'
      + 'background:#fff;border-radius:12px;box-shadow:0 4px 24px rgba(0,0,0,.12);border-left:4px solid #c0392b;">'
      + '<h2 style="color:#c0392b;margin-bottom:12px">Data Load Error</h2>'
      + '<p style="color:#444;line-height:1.6">' + msg + '</p></div>';
  }

  document.addEventListener('DOMContentLoaded', init);
})();

/* ============================================================
 * Tab nav + Competitor Analysis module
 * ============================================================ */
(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const fmt = n => (n !== null && n !== undefined && !isNaN(n))
    ? '$' + Number(n).toFixed(2) : '\u2014';
  const escHtml = s => String(s ?? '').replace(/&/g, '&amp;')
    .replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  // ── Tab switching ──────────────────────────────────────────
  function setView(view) {
    document.querySelectorAll('.app-tab').forEach(t => {
      const on = t.dataset.view === view;
      t.classList.toggle('active', on);
      t.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    const q = $('viewQuote');
    const c = $('viewCompetitor');
    const hc = $('headerCenterQuote');
    if (q) q.style.display = view === 'quote' ? '' : 'none';
    if (c) c.style.display = view === 'competitor' ? '' : 'none';
    if (hc) hc.style.visibility = view === 'quote' ? '' : 'hidden';
  }

  // ── Competitor logic ───────────────────────────────────────
  const compState = {
    retail: null, margin: 30,
    type: '', style: '', size: '', group: '',
  };

  function computeCompetitor() {
    const retail = compState.retail;
    const marginPct = clampPct(compState.margin);

    const cost      = (retail !== null) ? retail * (1 - marginPct / 100) : null;
    const marginAmt = (retail !== null) ? retail - cost : null;

    $('compRetailDisp').textContent    = fmt(retail);
    $('compMarginPctLbl').textContent  = marginPct + '%';
    $('compMarginAmtDisp').textContent = (marginAmt !== null) ? '\u2212' + fmt(marginAmt) : '\u2014';
    $('compCostDisp').textContent      = fmt(cost);

    renderMatches(cost);
  }

  function clampPct(v) {
    const n = Number(v);
    if (!Number.isFinite(n) || n < 0) return 0;
    if (n >= 100) return 99.99;
    return n;
  }

  function getAllProducts() {
    if (!window.PRICING_DATA || !Array.isArray(window.PRICING_DATA.products)) return [];
    return window.PRICING_DATA.products;
  }

  function productEffectivePrice(p) {
    // Use lowest qty-tier price if present (best volume price) — that's the
    // most aggressive price we can quote against a competitor.
    if (Array.isArray(p.qty_tiers) && p.qty_tiers.length) {
      const tiered = p.qty_tiers
        .map(t => t.price_numeric)
        .filter(v => v !== null && v !== undefined);
      if (tiered.length) return Math.min(...tiered);
    }
    return (p.price !== null && p.price !== undefined) ? p.price : null;
  }

  function renderMatches(target) {
    const list  = $('compMatchesList');
    const badge = $('compMatchBadge');
    const cntLbl = $('compMatchCountLbl');

    if (target === null || !isFinite(target) || target <= 0) {
      list.innerHTML = '<p class="empty-addons">Enter a competitor retail price to see matches.</p>';
      badge.textContent = 'No retail entered';
      badge.className = 'group-badge';
      cntLbl.textContent = '';
      return;
    }

    const all = getAllProducts();
    const filtered = all.filter(p => {
      if (compState.type  && p.type  !== compState.type)  return false;
      if (compState.style && p.style !== compState.style) return false;
      if (compState.size  && p.size  !== compState.size)  return false;
      if (compState.group && p.group !== compState.group) return false;
      const eff = productEffectivePrice(p);
      return eff !== null && eff > 0;
    });

    // Score by absolute distance to target (dealer cost).
    const scored = filtered.map(p => {
      const price = productEffectivePrice(p);
      const delta = price - target;
      return { p, price, delta, absDelta: Math.abs(delta) };
    }).sort((a, b) => a.absDelta - b.absDelta);

    const top = scored.slice(0, 3);
    if (!top.length) {
      list.innerHTML = '<p class="empty-addons">No matches found with current filters.</p>';
      badge.textContent = 'No matches';
      badge.className = 'group-badge';
      cntLbl.textContent = '';
      return;
    }

    badge.textContent = 'Target: ' + fmt(target);
    badge.className = 'group-badge active';
    cntLbl.textContent = 'Top ' + top.length + ' of ' + scored.length;

    const groupsLabels = (window.PRICING_DATA && window.PRICING_DATA.groups) || {};
    list.innerHTML = top.map((m, i) => {
      const groupLabel = groupsLabels[m.p.group] || m.p.group;
      const dCls = m.delta < 0 ? 'under' : (m.delta > 0 ? 'over' : 'exact');
      const dSign = m.delta < 0 ? '\u2212' : (m.delta > 0 ? '+' : '');
      const dPct  = (m.delta / target) * 100;
      const dTxt  = m.delta === 0
        ? 'Match'
        : (dSign + '$' + Math.abs(m.delta).toFixed(2) + '  (' + dSign + Math.abs(dPct).toFixed(1) + '%)');
      const tierNote = (Array.isArray(m.p.qty_tiers) && m.p.qty_tiers.length > 1)
        ? ' \u00b7 volume price' : '';
      return '<div class="comp-match' + (i === 0 ? ' best' : '') + '">'
        + '<div class="comp-match-rank">' + (i + 1) + '</div>'
        + '<div class="comp-match-info">'
        +   '<div class="comp-match-style">'
        +     '<span class="comp-match-group">' + escHtml(m.p.group) + '</span>'
        +     escHtml(m.p.style) + ' \u00b7 ' + escHtml(m.p.type)
        +   '</div>'
        +   '<div class="comp-match-meta">'
        +     escHtml(m.p.size) + ' \u00b7 ' + escHtml(m.p.variant) + tierNote
        +     '<br>' + escHtml(groupLabel)
        +   '</div>'
        + '</div>'
        + '<div class="comp-match-prices">'
        +   '<div class="comp-match-price">' + fmt(m.price) + '</div>'
        +   '<div class="comp-match-delta ' + dCls + '">' + dTxt + '</div>'
        + '</div>'
        + '</div>';
    }).join('');
  }

  // Broad category labels that aren't specific door designs — hidden from
  // the style filter so users only see actual door styles (Carrara, Camden,
  // Birkdale, etc.).
  const COMP_STYLE_EXCLUDE = new Set([
    'Colonial Moulded',
    'Flat Moulded (Shaker)',
    'Primed Hardboard',
  ]);

  // Sort sizes “naturally” — leading numeric width first.
  function sizeSortKey(s) {
    const m = String(s).match(/(\d+)/);
    return [m ? parseInt(m[1], 10) : 9999, String(s)];
  }
  function compareSizes(a, b) {
    const ka = sizeSortKey(a), kb = sizeSortKey(b);
    if (ka[0] !== kb[0]) return ka[0] - kb[0];
    return ka[1].localeCompare(kb[1]);
  }

  function populateCompFilters() {
    const all = getAllProducts();

    const styles = [...new Set(all.map(p => p.style))]
      .filter(s => !COMP_STYLE_EXCLUDE.has(s))
      .sort();
    const styleSel = $('compStyleFilter');
    if (styleSel) {
      styles.forEach(s => {
        const o = document.createElement('option');
        o.value = s; o.textContent = s;
        styleSel.appendChild(o);
      });
    }

    const sizes = [...new Set(all.map(p => p.size).filter(Boolean))].sort(compareSizes);
    const sizeSel = $('compSizeFilter');
    if (sizeSel) {
      sizes.forEach(s => {
        const o = document.createElement('option');
        o.value = s; o.textContent = s;
        sizeSel.appendChild(o);
      });
    }

    const groupSel = $('compGroupFilter');
    const groups = (window.PRICING_DATA && window.PRICING_DATA.groups) || {};
    if (groupSel) {
      Object.entries(groups).forEach(([id, label]) => {
        const o = document.createElement('option');
        o.value = id; o.textContent = label;
        groupSel.appendChild(o);
      });
    }
  }

  function wireCompetitor() {
    const r  = $('compRetail');
    const m  = $('compMargin');
    const tf = $('compTypeFilter');
    const sf = $('compStyleFilter');
    const zf = $('compSizeFilter');
    const gf = $('compGroupFilter');
    const reset = $('compResetBtn');

    if (r)  r.addEventListener('input', () => {
      const v = parseFloat(r.value);
      compState.retail = (Number.isFinite(v) && v > 0) ? v : null;
      computeCompetitor();
    });
    if (m)  m.addEventListener('input', () => {
      compState.margin = parseFloat(m.value);
      computeCompetitor();
    });
    if (tf) tf.addEventListener('change', () => { compState.type  = tf.value; computeCompetitor(); });
    if (sf) sf.addEventListener('change', () => { compState.style = sf.value; computeCompetitor(); });
    if (zf) zf.addEventListener('change', () => { compState.size  = zf.value; computeCompetitor(); });
    if (gf) gf.addEventListener('change', () => { compState.group = gf.value; computeCompetitor(); });

    if (reset) reset.addEventListener('click', () => {
      compState.retail = null; compState.margin = 30;
      compState.type = ''; compState.style = ''; compState.size = ''; compState.group = '';
      if (r) r.value = '';
      if (m) m.value = 30;
      if (tf) tf.value = '';
      if (sf) sf.value = '';
      if (zf) zf.value = '';
      if (gf) gf.value = '';
      computeCompetitor();
    });
  }

  function init() {
    document.querySelectorAll('.app-tab').forEach(t => {
      t.addEventListener('click', () => setView(t.dataset.view));
    });
    populateCompFilters();
    wireCompetitor();
    computeCompetitor();
  }

  // Run after the main app initializes (PRICING_DATA must be loaded).
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
