const state = {
  models: [],
  favorites: [],
  filter: "all",
  query: "",
  lastFetch: null,
  lastCredential: null,
  probe: {},
};

const els = {
  form: document.getElementById("fetchForm"),
  baseUrl: document.getElementById("baseUrl"),
  apiKey: document.getElementById("apiKey"),
  fetchBtn: document.getElementById("fetchBtn"),
  saveFavoriteBtn: document.getElementById("saveFavoriteBtn"),
  refreshCatalogBtn: document.getElementById("refreshCatalogBtn"),
  statusLine: document.getElementById("statusLine"),
  apiHint: document.getElementById("apiHint"),
  resultPanel: document.getElementById("resultPanel"),
  modelRows: document.getElementById("modelRows"),
  favoriteRows: document.getElementById("favoriteRows"),
  search: document.getElementById("search"),
  toast: document.getElementById("toast"),
  nameDialog: document.getElementById("nameDialog"),
  nameForm: document.getElementById("nameForm"),
  favoriteName: document.getElementById("favoriteName"),
  nameCancelBtn: document.getElementById("nameCancelBtn"),
  opencodeBtn: document.getElementById("opencodeBtn"),
  zenVerifyBtn: document.getElementById("zenVerifyBtn"),
  opencodeDialog: document.getElementById("opencodeDialog"),
  opencodePaths: document.getElementById("opencodePaths"),
  opencodeCancelBtn: document.getElementById("opencodeCancelBtn"),
  opencodeDownloadBtn: document.getElementById("opencodeDownloadBtn"),
};

let toastTimer = 0;
let opencodeConfig = null;

function formatNumber(value) {
  return typeof value === "number" ? value.toLocaleString("en-US") : "—";
}

function inputsHtml(inputs) {
  if (!inputs || !inputs.length) return "—";
  return inputs.map((item) => `<span class="badge">${escapeHtml(item)}</span>`).join("");
}

function reasoningHtml(row) {
  const levels = row.reasoning_levels || [];
  if (levels.length) {
    const extras = [];
    if (row.reasoning_budget_min) extras.push(`budget_tokens ≥ ${row.reasoning_budget_min}`);
    if (row.interleaved_field) extras.push(`interleaved: ${row.interleaved_field}`);
    const extraLine = extras.length ? `<div class="kind">${escapeHtml(extras.join(" · "))}</div>` : "";
    return `<div class="levels">${escapeHtml(levels.join(" → "))}</div>${extraLine}`;
  }
  if (row.reasoning_capable === false) return `<span class="muted-cell">不支持</span>`;
  return "—";
}

function structuredHtml(row) {
  if (row.structured_output === true) return `<span class="yes">✓</span>`;
  if (row.structured_output === false) return `<span class="no">✗</span>`;
  return "—";
}

function renderSkeleton() {
  els.resultPanel.classList.remove("hidden");
  els.modelRows.innerHTML = Array.from({ length: 6 }, () => `
    <tr>
      <td class="id-cell"><div class="skel"></div></td>
      <td><div class="skel"></div></td>
      <td><div class="skel"></div></td>
      <td><div class="skel"></div></td>
      <td><div class="skel"></div></td>
      <td><div class="skel"></div></td>
      <td><div class="skel"></div></td>
    </tr>
  `).join("");
}

function kindLabel(kind) {
  if (kind === "image") return "生图";
  if (kind === "video") return "生视频";
  return "对话";
}

function setStatus(text) {
  els.statusLine.textContent = text;
}

function hideToast() {
  window.clearTimeout(toastTimer);
  els.toast.classList.add("hidden");
  els.toast.innerHTML = "";
}

function showSaveToast() {
  els.toast.innerHTML = `
    <strong>检测到新的凭据组合</strong>
    <p>建议收藏并命名这组 Base URL + API Key，供应商更新模型后可再查最新名单。</p>
    <div class="toast-actions">
      <button type="button" id="toastSaveBtn">命名并收藏</button>
      <button type="button" id="toastDismissBtn" class="ghost">稍后</button>
    </div>
  `;
  els.toast.classList.remove("hidden");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(hideToast, 12000);
}

function currentCredential() {
  return {
    base_url: els.baseUrl.value.trim(),
    api_key: els.apiKey.value.trim(),
  };
}

function credentialToSave() {
  if (state.lastCredential?.base_url && state.lastCredential?.api_key) {
    return state.lastCredential;
  }
  return currentCredential();
}

function canSaveFavorite() {
  const cred = credentialToSave();
  return Boolean(state.lastFetch && cred.base_url && cred.api_key);
}

function defaultFavoriteName() {
  const cred = credentialToSave();
  try {
    return new URL(cred.base_url).host;
  } catch {
    return cred.base_url || "未命名凭据";
  }
}

async function api(path, options) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `HTTP_${response.status}`);
  }
  return data;
}

const SPEC_PARTS = {
  context: "上下文窗口",
  output: "最大输出",
  reasoning: "推理档位",
  tool_call: "工具调用",
  modalities: "多模态输入",
  structured: "结构化输出",
};
const SPEC_MAX = { context: 40, output: 20, reasoning: 15, tool_call: 15, modalities: 6, structured: 4 };

function specScoreHtml(row) {
  if (typeof row.spec_score !== "number") return "—";
  const parts = row.spec_breakdown || {};
  const detail = Object.keys(SPEC_PARTS)
    .map((key) => `${SPEC_PARTS[key]} ${parts[key] ?? 0}/${SPEC_MAX[key]}`)
    .join(" · ");
  return `<span title="${escapeAttr(detail)}">${row.spec_score}</span>`;
}

function sortRows(rows) {
  const kindRank = { chat: 0, image: 1, video: 2 };
  return [...rows].sort(
    (a, b) =>
      kindRank[a.kind] - kindRank[b.kind] ||
      Number(b.free) - Number(a.free) ||
      (b.spec_score || 0) - (a.spec_score || 0) ||
      a.id.toLowerCase().localeCompare(b.id.toLowerCase()),
  );
}

function probeHtml(row) {
  const result = state.probe[row.id];
  if (!result) return row.free ? `<span class="muted-cell">未实测</span>` : `<span class="muted-cell">—</span>`;
  const tone = result.status === "ok" ? "yes" : result.status === "unknown" ? "muted-cell" : "bad";
  const detail = result.message ? ` title="${escapeAttr(result.message)}"` : "";
  return `<span class="${tone}"${detail}>${escapeHtml(result.label)}</span>`;
}

function renderModels() {
  els.opencodeBtn.disabled = !state.models.length;
  els.zenVerifyBtn.disabled = !state.models.some((row) => row.free);
  const rows = sortRows(state.models.filter((row) => {
    if (state.filter !== "all" && row.kind !== state.filter) return false;
    if (state.query && !row.id.toLowerCase().includes(state.query)) return false;
    return true;
  }));
  if (!rows.length) {
    els.modelRows.innerHTML = `<tr><td colspan="9" class="empty">没有匹配的模型。</td></tr>`;
    return;
  }
  els.modelRows.innerHTML = rows.map((row) => `
    <tr${row.free ? ' class="row-free"' : ""}>
      <td class="id-cell">
        <div>${escapeHtml(row.id)}${row.free ? ' <span class="free-badge">免费</span>' : ""}</div>
        <div class="kind">${kindLabel(row.kind)}</div>
        ${row.notes?.length ? `<div class="note">${escapeHtml(row.notes.join("；"))}</div>` : ""}
      </td>
      <td class="num">${formatNumber(row.context)}</td>
      <td class="num">${formatNumber(row.max_output)}</td>
      <td>${inputsHtml(row.inputs)}</td>
      <td>${reasoningHtml(row)}</td>
      <td>${structuredHtml(row)}</td>
      <td class="num">${specScoreHtml(row)}</td>
      <td>${probeHtml(row)}</td>
      <td>${escapeHtml(row.source)}</td>
    </tr>
  `).join("");
}

function countsText(counts) {
  if (!counts || !counts.all) return "尚未再次拉取";
  return `${counts.all} 个模型（对话 ${counts.chat || 0} / 生图 ${counts.image || 0} / 生视频 ${counts.video || 0}）`;
}

function renderFavorites() {
  if (!state.favorites.length) {
    els.favoriteRows.innerHTML = `<p class="empty">还没有收藏凭据。</p>`;
    return;
  }
  els.favoriteRows.innerHTML = state.favorites.map((row) => `
    <article class="fav-card">
      <div class="fav-head">
        <span class="fav-name">${escapeHtml(row.label || row.host || "")}</span>
        <span class="badge">${escapeHtml(row.api_key_masked || "")}</span>
      </div>
      <div class="fav-url">${escapeHtml(row.base_url || "")}</div>
      <div class="fav-meta">
        <div>${escapeHtml(row.last_fetched_at || row.saved_at || "")}</div>
        <div class="kind">${escapeHtml(countsText(row.last_counts))}</div>
      </div>
      <div class="fav-actions">
        <button type="button" data-refetch="${escapeAttr(row.id)}">再查最新</button>
        <button type="button" class="ghost" data-unfav="${escapeAttr(row.id)}">移除</button>
      </div>
    </article>
  `).join("");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll('"', "&quot;");
}

function applyFavorites(items) {
  state.favorites = items || [];
  renderFavorites();
}

function openNameDialog() {
  if (!canSaveFavorite()) return;
  els.favoriteName.value = defaultFavoriteName();
  els.nameDialog.classList.remove("hidden");
  els.favoriteName.focus();
  els.favoriteName.select();
}

function closeNameDialog() {
  els.nameDialog.classList.add("hidden");
}

function applyFetchResult(data, options = {}) {
  state.models = data.models || [];
  state.lastFetch = data;
  if (options.credential) state.lastCredential = options.credential;
  els.resultPanel.classList.remove("hidden");
  if (data.api_format_hint) els.apiHint.textContent = data.api_format_hint;
  if (data.base_url) els.baseUrl.value = data.base_url;
  if (options.clearKey) els.apiKey.value = "";
  els.saveFavoriteBtn.disabled = !canSaveFavorite();
  const counts = data.counts || {};
  const alreadySaved = data.already_saved === true;
  const suggestSave = options.suggestSave && data.suggest_save === true && !alreadySaved && canSaveFavorite();
  if (alreadySaved) {
    setStatus(`拉到 ${counts.all || 0} 个模型，知识库命中 ${counts.matched || 0} 个。这组凭据已收藏，可在下方直接再查最新。`);
  } else {
    setStatus(`拉到 ${counts.all || 0} 个模型，知识库命中 ${counts.matched || 0} 个。对话 ${counts.chat || 0} / 生图 ${counts.image || 0} / 生视频 ${counts.video || 0}。`);
  }
  renderModels();
  if (data.favorites) applyFavorites(data.favorites);
  if (suggestSave) showSaveToast();
  else hideToast();
}

function renderOpencodePaths(paths) {
  const items = paths.items.map((item) => `
    <div class="path-item">
      <div class="path-label">${escapeHtml(item.label)}</div>
      <div class="path-value">${escapeHtml(item.value)}</div>
      <div class="kind">${escapeHtml(item.note)}</div>
    </div>
  `).join("");
  const tips = paths.tips.map((tip) => `<div class="kind">${escapeHtml(tip)}</div>`).join("");
  els.opencodePaths.innerHTML = items + tips;
}

async function generateOpencodeConfig() {
  const cred = credentialToSave();
  const data = await api("/api/export/opencode", {
    method: "POST",
    body: JSON.stringify({ base_url: cred.base_url, api_key: cred.api_key, models: state.models }),
  });
  renderOpencodePaths(data.paths);
  els.opencodeDialog.dataset.filename = data.filename || "opencode.json";
  opencodeConfig = data.config;
  els.opencodeDialog.classList.remove("hidden");
}

function downloadOpencodeConfig() {
  if (!opencodeConfig) return;
  const blob = new Blob([JSON.stringify(opencodeConfig, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = els.opencodeDialog.dataset.filename || "opencode.json";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  els.opencodeDialog.classList.add("hidden");
  setStatus("opencode.json 已下载。放到弹窗里列出的任一路径，重启 opencode 生效。");
}

async function saveFavorite(label) {
  const cred = credentialToSave();
  const data = await api("/api/favorites", {
    method: "POST",
    body: JSON.stringify({
      ...cred,
      label,
      last_counts: state.lastFetch?.counts || {},
    }),
  });
  applyFavorites(data.items);
  if (state.lastFetch) {
    state.lastFetch.already_saved = true;
    state.lastFetch.suggest_save = false;
  }
  hideToast();
  closeNameDialog();
  setStatus(`已收藏「${label}」。下次可直接点「再查最新」，向供应商拉取当前模型名单。`);
}

async function fetchModels({ suggestSave = true } = {}) {
  els.fetchBtn.disabled = true;
  els.fetchBtn.classList.add("loading");
  setStatus("正在向供应商拉取模型列表…");
  renderSkeleton();
  const credential = currentCredential();
  try {
    const data = await api("/api/fetch", {
      method: "POST",
      body: JSON.stringify(credential),
    });
    applyFetchResult(data, { suggestSave, credential });
  } catch (error) {
    setStatus(`获取失败：${error.message}`);
    if (!state.models.length) {
      els.resultPanel.classList.add("hidden");
    } else {
      renderModels();
    }
  } finally {
    els.fetchBtn.disabled = false;
    els.fetchBtn.classList.remove("loading");
    els.saveFavoriteBtn.disabled = !canSaveFavorite();
  }
}

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await fetchModels({ suggestSave: true });
});

els.saveFavoriteBtn.addEventListener("click", () => {
  openNameDialog();
});

els.refreshCatalogBtn.addEventListener("click", async () => {
  els.refreshCatalogBtn.disabled = true;
  els.refreshCatalogBtn.classList.add("loading");
  setStatus("正在更新 models.dev 知识库…");
  try {
    const data = await api("/api/catalog/refresh", { method: "POST", body: "{}" });
    setStatus(`知识库已更新：${data.catalog_fetched_at || "完成"}`);
  } catch (error) {
    setStatus(`知识库更新失败：${error.message}`);
  } finally {
    els.refreshCatalogBtn.disabled = false;
    els.refreshCatalogBtn.classList.remove("loading");
  }
});

document.getElementById("filters").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-filter]");
  if (!button) return;
  state.filter = button.dataset.filter;
  document.querySelectorAll("#filters .chip").forEach((chip) => chip.classList.toggle("active", chip === button));
  renderModels();
});

els.search.addEventListener("input", () => {
  state.query = els.search.value.trim().toLowerCase();
  renderModels();
});

els.baseUrl.addEventListener("input", () => {
  els.saveFavoriteBtn.disabled = !canSaveFavorite();
});
els.apiKey.addEventListener("input", () => {
  els.saveFavoriteBtn.disabled = !canSaveFavorite();
});

els.toast.addEventListener("click", (event) => {
  if (event.target.id === "toastSaveBtn") {
    hideToast();
    openNameDialog();
  }
  if (event.target.id === "toastDismissBtn") hideToast();
});

els.nameCancelBtn.addEventListener("click", () => closeNameDialog());
els.nameDialog.addEventListener("click", (event) => {
  if (event.target === els.nameDialog) closeNameDialog();
});
els.nameForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const label = els.favoriteName.value.trim();
  if (!label) return;
  try {
    await saveFavorite(label);
  } catch (error) {
    setStatus(`收藏失败：${error.message}`);
  }
});

els.zenVerifyBtn.addEventListener("click", async () => {
  const targets = state.models.filter((row) => row.free).map((row) => row.id);
  if (!targets.length) return;
  const cred = credentialToSave();
  els.zenVerifyBtn.disabled = true;
  els.zenVerifyBtn.classList.add("loading");
  setStatus(`正在实测 ${targets.length} 个免费模型能否在本工具外部直接调用，每个模型发一次 1-token 请求…`);
  try {
    const data = await api("/api/zen/verify", {
      method: "POST",
      body: JSON.stringify({ base_url: cred.base_url, api_key: cred.api_key, models: targets }),
    });
    state.probe = data.results || {};
    const direct = Object.values(state.probe).filter((item) => item.usable).length;
    const clientOnly = Object.values(state.probe).filter((item) => item.status === "client_only").length;
    setStatus(`实测完成：${data.probed} 个免费模型中，${direct} 个外部可调用、${clientOnly} 个仅限在 OpenCode 客户端内使用。结果存在本机。`);
    renderModels();
  } catch (error) {
    setStatus(`实测失败：${error.message}`);
  } finally {
    els.zenVerifyBtn.classList.remove("loading");
    els.zenVerifyBtn.disabled = !state.models.some((row) => row.free);
  }
});

els.opencodeBtn.addEventListener("click", () => {
  generateOpencodeConfig().catch((error) => setStatus(`生成失败：${error.message}`));
});
els.opencodeCancelBtn.addEventListener("click", () => els.opencodeDialog.classList.add("hidden"));
els.opencodeDialog.addEventListener("click", (event) => {
  if (event.target === els.opencodeDialog) els.opencodeDialog.classList.add("hidden");
});
els.opencodeDownloadBtn.addEventListener("click", downloadOpencodeConfig);

els.favoriteRows.addEventListener("click", async (event) => {
  const refetch = event.target.closest("button[data-refetch]");
  if (refetch) {
    refetch.disabled = true;
    setStatus("正在用收藏的凭据向供应商拉取最新模型…");
    try {
      const favorite = state.favorites.find((item) => item.id === refetch.dataset.refetch);
      const data = await api("/api/favorites/refetch", {
        method: "POST",
        body: JSON.stringify({ id: refetch.dataset.refetch }),
      });
      applyFetchResult(data, {
        clearKey: true,
        suggestSave: false,
        credential: favorite ? { base_url: favorite.base_url, api_key: "" } : null,
      });
    } catch (error) {
      setStatus(`再查失败：${error.message}`);
    } finally {
      refetch.disabled = false;
    }
    return;
  }
  const unfav = event.target.closest("button[data-unfav]");
  if (!unfav) return;
  const data = await api("/api/favorites/remove", {
    method: "POST",
    body: JSON.stringify({ id: unfav.dataset.unfav }),
  });
  applyFavorites(data.items);
});

(async function boot() {
  try {
    const data = await api("/api/state");
    els.apiHint.textContent = data.api_format_hint || els.apiHint.textContent;
    applyFavorites(data.favorites || []);
    if (data.zen_probe?.results) state.probe = data.zen_probe.results;
    if (data.last_fetch?.models) {
      // 先把上次的模型秒显出来，随后自动查询会被新结果覆盖
      state.models = data.last_fetch.models;
      state.lastFetch = data.last_fetch;
      els.resultPanel.classList.remove("hidden");
      renderModels();
    }
    els.saveFavoriteBtn.disabled = !canSaveFavorite();
    const catalog = data.catalog_fetched_at ? `知识库缓存于 ${data.catalog_fetched_at}` : "本地还没有知识库缓存，可先获取模型，或点更新知识库。";
    setStatus(catalog);
  } catch (error) {
    setStatus(`启动失败：${error.message}`);
  }
  // 启动即用默认凭据（OpenCode Zen + public）查询一次；不做实测探勘、不弹收藏建议
  await fetchModels({ suggestSave: false });
})();
