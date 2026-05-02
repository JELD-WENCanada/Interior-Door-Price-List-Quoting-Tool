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
  };

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
    ['step-type', 'step-style', 'step-size', 'step-variant', 'step-addons'].forEach(s => setStepEnabled(s, false));
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
  }

  // ── Handlers ─────────────────────────────────────────────────
  function onGroupChange() {
    state.group = el('groupSelect').value;
    state.type = ''; state.style = ''; state.size = ''; state.variant = '';
    state.activeAddons.clear();
    resetTypeButtons();
    ['step-type','step-style','step-size','step-variant','step-addons'].forEach(s => setStepEnabled(s, false));
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
    resetTypeButtons();
    disableAndClear(['styleSelect', 'sizeSelect', 'variantSelect']);
    ['step-style', 'step-size', 'step-variant', 'step-addons'].forEach(s => setStepEnabled(s, false));
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
    const basePrice  = state.variant ? getBasePrice() : null;
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

    const total = basePrice !== null ? basePrice + addonTotal : null;
    el('totalDisplay').textContent = fmt(total);
    el('totalDisplay').className   = total === null ? 'pr-value grand na' : 'pr-value grand';
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
