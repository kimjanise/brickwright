import {
  createIcons,
  PanelLeft,
  SquarePen,
  Search,
  ArrowUp,
  Square,
  ChevronDown,
  Box,
  ArrowUpRight,
  X,
  Trash2,
  Download,
  RotateCcw,
  Sun,
  Moon,
  Check,
  Copy,
  LoaderCircle,
  Blocks,
  Sparkles,
  SlidersHorizontal,
} from "lucide";
import "./style.css";
const icons = {
  PanelLeft,
  SquarePen,
  Search,
  ArrowUp,
  Square,
  ChevronDown,
  Box,
  ArrowUpRight,
  X,
  Trash2,
  Download,
  RotateCcw,
  Sun,
  Moon,
  Check,
  Copy,
  LoaderCircle,
  Blocks,
  Sparkles,
  SlidersHorizontal,
};
const state = {
  chat: null,
  chats: [],
  pending: false,
  search: "",
  locale: localStorage.getItem("bw-locale") || "en-us",
  rendered: "",
  viewers: [],
};
const $ = (s, root = document) => root.querySelector(s);
const icon = (name, cls = "") => `<i data-lucide="${name}" class="${cls}"></i>`;
const refreshIcons = () =>
  createIcons({ icons, attrs: { "stroke-width": 1.7 } });
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};
const button = (label, name, click, cls = "icon-button") => {
  const b = el("button", cls);
  b.type = "button";
  b.title = label;
  b.setAttribute("aria-label", label);
  b.innerHTML = icon(name);
  b.onclick = click;
  return b;
};
const busy = () => ["queued", "building"].includes(state.chat?.status);
async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : "Something went wrong. Please try again.",
    );
  }
  return res.status === 204 ? null : res.json();
}
function toast(message) {
  const n = $("#toast");
  n.textContent = message;
  n.classList.add("visible");
  clearTimeout(n.timer);
  n.timer = setTimeout(() => n.classList.remove("visible"), 6500);
}
const savedTheme = localStorage.getItem("bw-theme");
if (savedTheme === "dark") document.documentElement.dataset.theme = "dark";
$("#app").innerHTML = `
<div class="scrim"></div>
<aside class="sidebar" aria-label="Conversations">
  <div class="sidebar-top"><a class="brand-mark" href="/" aria-label="Brickwright home">${icon("blocks")}</a><button class="icon-button sidebar-toggle" title="Close sidebar" aria-label="Close sidebar">${icon("panel-left")}</button></div>
  <button class="nav-action" id="new-chat">${icon("square-pen")}<span>New build</span><kbd>⌘ K</kbd></button>
  <button class="nav-action" id="search-button">${icon("search")}<span>Search chats</span></button>
  <div class="search-wrap" hidden><input id="search" placeholder="Search your builds…" aria-label="Search conversations"/><button class="icon-button" id="close-search" aria-label="Close search">${icon("x")}</button></div>
  <div class="history-label">Your builds</div><nav id="history" aria-label="Build history"></nav>
  <div class="sidebar-footer"><div class="avatar">B</div><div><strong>Your workspace</strong><span>Local studio</span></div><button class="icon-button" id="theme-toggle" aria-label="Toggle dark mode" title="Toggle dark mode">${icon("moon")}</button></div>
</aside>
<main>
  <header><div class="header-left"><button class="icon-button sidebar-toggle open-sidebar" aria-label="Open sidebar" title="Open sidebar">${icon("panel-left")}</button><button class="icon-button header-new" id="header-new" aria-label="New build" title="New build">${icon("square-pen")}</button><span class="wordmark">Brickwright <span class="version">Studio</span></span></div><div class="header-right"><span class="status-dot"></span><span>Build with AI</span></div></header>
  <div class="conversation-scroll" id="scroll"><section class="welcome" id="welcome"><div class="welcome-mark">${icon("blocks")}</div><h1>What do you want to build?</h1><p>A little idea. A world of bricks.</p></section><section id="messages" aria-label="Conversation"></section></div>
  <div class="composer-area" id="composer-area"><form id="composer" class="composer"><textarea id="prompt" rows="1" maxlength="8000" placeholder="Describe your next LEGO build" aria-label="Describe your build"></textarea><div class="composer-bottom"><div class="composer-tools"><label class="market" title="Pick a Brick market">${icon("sliders-horizontal")}<select id="locale" aria-label="LEGO pricing market"><option value="en-us">United States · USD</option><option value="en-gb">United Kingdom · GBP</option><option value="en-ca">Canada · CAD</option><option value="en-au">Australia · AUD</option><option value="de-de">Germany · EUR</option><option value="fr-fr">France · EUR</option><option value="nl-nl">Netherlands · EUR</option></select></label></div><button id="send" class="send" type="submit" aria-label="Send message" disabled>${icon("arrow-up")}</button></div></form><div class="suggestions" id="suggestions"></div><p class="disclaimer">AI designs, real bricks. Check build details before ordering.</p></div>
</main><div id="toast" role="status"></div>`;
const suggestions = [
  [
    "A tiny city café",
    "Build a cozy corner café with a striped awning, outdoor seating, and a little plant. Keep it under 150 bricks.",
    "box",
  ],
  [
    "My dream cabin",
    "Create a small woodland cabin with a pitched roof, chimney, and a tree beside it. Use warm earthy colors.",
    "blocks",
  ],
  [
    "A retro spaceship",
    "Build a retro spaceship with a white body, blue cockpit, and two red engines. Make it compact and sturdy.",
    "sparkles",
  ],
  [
    "Surprise me",
    "Create a charming miniature robot with a big personality, colorful details, and a stable base. Keep it under 80 pieces.",
    "rotate-ccw",
  ],
];
for (const [title, prompt, symbol] of suggestions) {
  const b = button(
    title,
    symbol,
    () => {
      $("#prompt").value = prompt;
      resizeInput();
      $("#prompt").focus();
    },
    "suggestion",
  );
  b.append(el("span", "", title));
  $("#suggestions").append(b);
}
function toggleSidebar() {
  document.body.classList.toggle("sidebar-hidden");
  document.body.classList.toggle("sidebar-open");
}
for (const b of document.querySelectorAll(".sidebar-toggle"))
  b.onclick = toggleSidebar;
$(".scrim").onclick = () => document.body.classList.remove("sidebar-open");
function newChat() {
  state.chat = null;
  state.rendered = "";
  localStorage.removeItem("bw-chat");
  render();
  $("#prompt").focus();
  document.body.classList.remove("sidebar-open");
}
$("#new-chat").onclick = newChat;
$("#header-new").onclick = newChat;
$("#theme-toggle").onclick = () => {
  const dark = document.documentElement.dataset.theme !== "dark";
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  localStorage.setItem("bw-theme", dark ? "dark" : "light");
};
$("#search-button").onclick = () => {
  $(".search-wrap").hidden = false;
  $("#search").focus();
};
$("#close-search").onclick = () => {
  $(".search-wrap").hidden = true;
  $("#search").value = "";
  state.search = "";
  renderHistory();
};
$("#search").oninput = (event) => {
  state.search = event.target.value;
  renderHistory();
};
$("#locale").value = state.locale;
$("#locale").onchange = (event) => {
  state.locale = event.target.value;
  localStorage.setItem("bw-locale", state.locale);
  toast("Market updated. Refresh a build’s price to use this market.");
};
document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    newChat();
  }
  if (e.key === "Escape") document.body.classList.remove("sidebar-open");
});
function resizeInput() {
  const input = $("#prompt");
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
  $("#send").disabled = state.pending || (!busy() && !input.value.trim());
}
$("#prompt").oninput = resizeInput;
$("#prompt").onkeydown = (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    $("#composer").requestSubmit();
  }
};
$("#composer").onsubmit = async (e) => {
  e.preventDefault();
  if (state.pending) return;
  if (busy()) {
    try {
      state.chat = await api(`/api/chats/${state.chat.id}/stop`, {
        method: "POST",
      });
      render();
    } catch (err) {
      toast(err.message);
    }
    return;
  }
  const prompt = $("#prompt").value.trim();
  if (!prompt) return;
  state.pending = true;
  resizeInput();
  try {
    if (!state.chat)
      state.chat = await api("/api/chats", { method: "POST", body: "{}" });
    const id = state.chat.id;
    state.chat = await api(`/api/chats/${id}/messages`, {
      method: "POST",
      body: JSON.stringify({ prompt }),
    });
    localStorage.setItem("bw-chat", id);
    $("#prompt").value = "";
    await loadHistory();
    render(true);
  } catch (err) {
    toast(err.message);
  } finally {
    state.pending = false;
    resizeInput();
  }
};
async function loadHistory() {
  state.chats = await api("/api/chats");
  renderHistory();
}
function renderHistory() {
  const history = $("#history");
  history.replaceChildren();
  const chats = state.chats.filter((c) =>
    c.title.toLowerCase().includes(state.search.toLowerCase()),
  );
  if (!chats.length)
    history.append(
      el(
        "p",
        "empty-history",
        state.search ? "No matching builds" : "Your ideas will live here.",
      ),
    );
  for (const chat of chats) {
    const row = el(
      "div",
      `history-row ${state.chat?.id === chat.id ? "active" : ""}`,
    );
    const b = el("button", "history-chat", chat.title);
    b.title = chat.title;
    b.onclick = async () => {
      try {
        state.chat = await api(`/api/chats/${chat.id}`);
        state.rendered = "";
        localStorage.setItem("bw-chat", chat.id);
        render(true);
        document.body.classList.remove("sidebar-open");
      } catch (err) {
        toast(err.message);
      }
    };
    row.append(
      b,
      button(
        "Delete conversation",
        "trash-2",
        async () => {
          if (!confirm("Delete this conversation?")) return;
          try {
            await api(`/api/chats/${chat.id}`, { method: "DELETE" });
            if (state.chat?.id === chat.id) newChat();
            await loadHistory();
          } catch (err) {
            toast(err.message);
          }
        },
        "icon-button delete-chat",
      ),
    );
    history.append(row);
  }
  refreshIcons();
}
function render(scroll = false) {
  const hasMessages = !!state.chat?.messages.length;
  document.body.classList.toggle("has-messages", hasMessages);
  $("#welcome").hidden = hasMessages;
  $("#suggestions").hidden = hasMessages;
  $("#prompt").placeholder = hasMessages
    ? "Ask for a change, or imagine something new…"
    : "Describe your next LEGO build";
  const signature = JSON.stringify(state.chat?.messages || []);
  if (state.rendered !== signature) {
    state.viewers.forEach((dispose) => dispose());
    state.viewers = [];
    $("#messages").replaceChildren();
    state.rendered = signature;
    for (const message of state.chat?.messages || []) {
      const article = el("article", `message ${message.role}`);
      if (message.role === "assistant") {
        const badge = el("div", "assistant-badge");
        badge.innerHTML = icon("blocks");
        article.append(badge);
      }
      const content = el("div", "message-content");
      content.append(el("div", "message-text", message.content));
      if (message.record_id) content.append(buildCard(state.chat.id, message));
      if (message.role === "assistant")
        content.append(
          button(
            "Copy response",
            "copy",
            async () => {
              await navigator.clipboard.writeText(message.content);
              toast("Copied response");
            },
            "icon-button copy-response",
          ),
        );
      article.append(content);
      $("#messages").append(article);
    }
  }
  $("#progress")?.remove();
  if (busy() || ["error", "cancelled"].includes(state.chat?.status)) {
    const p = el("div", `progress ${busy() ? "" : "notice"}`);
    p.id = "progress";
    p.setAttribute("role", "status");
    if (busy()) p.innerHTML = `<span class="working-dot"></span>`;
    p.append(el("span", "", state.chat.progress));
    $("#messages").append(p);
  }
  const send = $("#send");
  send.innerHTML = icon(busy() ? "square" : "arrow-up");
  send.setAttribute("aria-label", busy() ? "Stop generation" : "Send message");
  resizeInput();
  renderHistory();
  refreshIcons();
  if (scroll)
    requestAnimationFrame(() =>
      $("#scroll").scrollTo({
        top: $("#scroll").scrollHeight,
        behavior: "smooth",
      }),
    );
}
function buildCard(chatId, message) {
  const base = `/api/chats/${chatId}/builds/${message.record_id}`;
  const card = el("div", "build-card");
  const head = el("div", "build-card-head");
  head.innerHTML = `${icon("box")}<strong>Your custom build</strong>`;
  head.append(el("span", "piece-count", `${message.brick_count} pieces`));
  card.append(head);
  const viewer = el("div", "viewer");
  viewer.append(el("span", "viewer-loading", "Loading 3D preview…"));
  card.append(viewer);
  const viewerFoot = el("div", "viewer-foot");
  viewerFoot.append(el("span", "", "Drag to rotate · Scroll to zoom"));
  const reset = button("Reset view", "rotate-ccw", () => {}, "icon-button");
  viewerFoot.append(reset);
  card.append(viewerFoot);
  const price = el("div", "price-row");
  const priceText = el("div");
  priceText.append(
    el("strong", "", "Price your build"),
    el("span", "", "Live LEGO Pick a Brick prices"),
  );
  const priceButton = el("button", "secondary-button", "Check price");
  price.append(priceText, priceButton);
  card.append(price);
  priceButton.onclick = async () => {
    priceButton.disabled = true;
    priceButton.textContent = "Checking…";
    try {
      const body = await api(`${base}/ldraw`);
      const quote = await api(
        `/api/pick-a-brick/quote/ldraw?locale=${state.locale}`,
        { method: "POST", body: JSON.stringify(body) },
      );
      const amount = new Intl.NumberFormat(undefined, {
        style: "currency",
        currency: quote.currency,
      }).format((quote.total_cents ?? quote.known_subtotal_cents) / 100);
      priceText.replaceChildren(
        el(
          "strong",
          "",
          `${amount}${quote.complete ? "" : " · partial price"}`,
        ),
        el(
          "span",
          "",
          `Parts subtotal · ${quote.priced_quantity}/${quote.total_quantity} pieces · ${quote.locale.toUpperCase()}${quote.purchasable ? "" : " · Some pieces unavailable"}`,
        ),
      );
      card.querySelector(".quote-detail")?.remove();
      const detail = el("details", "quote-detail");
      detail.append(el("summary", "", "Price breakdown"));
      detail.append(el("p", "price-notice", quote.notice));
      for (const line of quote.lines) {
        const row = el("div", "part-row");
        row.append(
          el("span", "", `${line.quantity} × ${line.name || line.ldraw_id}`),
          el(
            "span",
            "",
            line.line_total_cents == null
              ? line.status.replaceAll("_", " ")
              : new Intl.NumberFormat(undefined, {
                  style: "currency",
                  currency: quote.currency,
                }).format(line.line_total_cents / 100),
          ),
        );
        detail.append(row);
      }
      card.insertBefore(detail, card.querySelector(".card-actions"));
      priceButton.textContent = "Refresh";
    } catch (err) {
      toast(err.message);
      priceButton.textContent = "Try again";
    } finally {
      priceButton.disabled = false;
    }
  };
  const actions = el("div", "card-actions");
  const download = el("a", "download-button");
  download.href = `${base}/model`;
  download.innerHTML = `${icon("download")}<span>Download LDraw</span>`;
  const edit = el("button", "text-button", "Refine this build");
  edit.onclick = () => {
    $("#prompt").focus();
    $("#prompt").value = "Update the build to ";
    resizeInput();
  };
  actions.append(download, edit);
  card.append(actions);
  api(`${base}/preview`)
    .then(async (data) => {
      if (!card.isConnected) return;
      const { mountViewer } = await import("./viewer.js");
      if (!card.isConnected) return;
      const controls = mountViewer(viewer, data);
      reset.onclick = controls.reset;
      state.viewers.push(controls.dispose);
    })
    .catch(() => {
      viewer.replaceChildren(
        el(
          "span",
          "viewer-loading",
          "3D preview unavailable. You can still download your build.",
        ),
      );
    });
  return card;
}
async function poll() {
  try {
    if (state.chat && busy()) {
      const id = state.chat.id;
      const next = await api(`/api/chats/${id}`);
      if (state.chat?.id === id) {
        const done = !["queued", "building"].includes(next.status);
        state.chat = next;
        render(done);
        if (done) await loadHistory();
      }
    }
  } catch (err) {
    toast("Connection lost. Reconnecting…");
  } finally {
    setTimeout(poll, 2000);
  }
}
async function init() {
  try {
    await loadHistory();
    const id = localStorage.getItem("bw-chat");
    if (id && state.chats.some((c) => c.id === id))
      state.chat = await api(`/api/chats/${id}`);
    const status = await api("/api/status");
    if (!status.generator_available)
      toast("Install Codex CLI and sign in with codex login to create builds.");
  } catch (err) {
    toast(err.message);
  }
  render(true);
  poll();
}
init();
