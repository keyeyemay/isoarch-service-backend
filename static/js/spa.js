"use strict";
const view = document.querySelector("#view");
const notice = document.querySelector("#notice");
let user = null;
let renderVersion = 0;
let returnAfterLogin = "#/list";
let previewUrls = [];
const escapeHTML = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
}[c]));
const isotope = (value) => value == null ? "—" : `${Number(value).toFixed(1)} ‰`;

// Keep the LR3 placeholders when a legacy MinIO object is missing.
document.addEventListener("error", (event) => {
  const media = event.target;
  if (!(media instanceof HTMLImageElement || media instanceof HTMLVideoElement)) return;
  if (media.closest(".media-preview")) return;
  const fallback = media instanceof HTMLVideoElement
    ? "/static/videos/default_signature.mp4" : "/static/images/default_signature.png";
  if (media.getAttribute("src") === fallback) return;
  media.src = fallback;
  if (media instanceof HTMLImageElement && media.hasAttribute("data-video-poster")) {
    const video = view.querySelector(".feed__video");
    if (video) video.poster = fallback;
  }
}, true);

async function api(path, options = {}) {
  const response = await fetch(path, {credentials: "same-origin", ...options});
  const data = response.status === 204 ? null : await response.json();
  if (!response.ok) {
    const detail = data?.detail;
    const error = new Error(Array.isArray(detail) ? detail.map((e) => e.msg).join("; ") : detail || "Ошибка запроса");
    error.code = response.status;
    throw error;
  }
  return data;
}
const jsonRequest = (method, data) => ({method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)});
function showError(error) { notice.textContent = error.message; notice.hidden = false; }
function navigate(hash) {
  if (location.hash === hash) render();
  else location.hash = hash;
}
function account() {
  document.querySelector("#account").innerHTML = user
    ? `<span>${escapeHTML(user.username)}</span><button type="button" class="btn btn--secondary" data-logout>Выйти</button>`
    : '<a class="btn btn--secondary" href="#/auth">Войти</a>';
}
async function refreshUser() {
  try { user = await api("/auth/me"); }
  catch (error) { if (error.code !== 401) throw error; user = null; }
  account();
}
function field(label, name, type = "text", value = "", extra = "") {
  return `<label class="field"><span class="field__label">${label}</span><input class="field__input" name="${name}" type="${type}" value="${escapeHTML(value)}" ${extra}></label>`;
}
function unavailable() {
  return '<h1 class="page-title">Запись недоступна</h1><p class="helper">Публикация удалена, ещё не опубликована или не существует.</p><a class="btn btn--primary" href="#/list">В каталог</a>';
}
function authPage(register = false) {
  return `<h1 class="page-title">${register ? "Регистрация" : "Вход"}</h1>
    <p class="helper">Войдите, чтобы публиковать исследования и ставить лайки.</p>
    <div class="auth-switch"><a class="btn btn--secondary" href="#/auth">Вход</a><a class="btn btn--secondary" href="#/auth/register">Регистрация</a></div>
    <form class="form-stack" data-auth="${register ? "register" : "login"}">
      ${field("Логин", "username", "text", "", 'required maxlength="100" autocomplete="username"')}
      ${field("Пароль", "password", "password", "", `required maxlength="255" autocomplete="${register ? "new-password" : "current-password"}"`)}
      ${register ? field("Полное имя (необязательно)", "full_name", "text", "", 'maxlength="255" autocomplete="name"') + field("Email (необязательно)", "email", "email", "", 'maxlength="255" autocomplete="email"') : ""}
      <button class="btn btn--primary" type="submit">${register ? "Зарегистрироваться" : "Войти"}</button>
    </form>`;
}
async function catalog(query) {
  const params = new URLSearchParams(query);
  const records = await api(`/services?${params}`);
  return `<h1 class="page-title">Исследования</h1>
    <form class="filter-box" data-filter>
      ${field("Название", "filter", "search", params.get("filter") || "", 'maxlength="255"')}
      ${field("δ¹³C не более (‰)", "c13_max", "number", params.get("c13_max") || "", 'step="any"')}
      <div><button class="btn btn--primary" type="submit">Применить</button> <a class="btn btn--secondary" href="#/list">Сбросить</a></div>
    </form>
    <div class="grid">${records.length ? records.map((s) => `<article class="tile">
      <a class="tile__link" href="#/feed/${s.id}"><div class="tile__image-wrap"><img src="${escapeHTML(s.image_url)}" alt="${escapeHTML(s.title)}" loading="lazy"></div>
      <h2 class="tile__title">${escapeHTML(s.title)}</h2></a>
      <div class="tile__params"><span class="tile__param-badge tile__param-badge--c13">δ¹³C ${isotope(s.delta_c13)}</span><span class="tile__param-badge tile__param-badge--n15">δ¹⁵N ${isotope(s.delta_n15)}</span></div>
      <div class="tile__footer"><span class="tile__likes">♥ ${s.likes_count}</span>${s.is_creator ? `<a class="btn btn--secondary btn--compact" href="#/edit/${s.id}">Изменить</a><button type="button" class="btn btn--secondary btn--compact" data-delete="${s.id}">Удалить</button>` : ""}</div>
    </article>`).join("") : '<p class="empty-state">Публикаций не найдено.</p>'}</div>`;
}
async function feed(id) {
  const s = await api(id ? `/services/feed/${id}` : "/services/feed");
  return `<video class="feed__video" src="${escapeHTML(s.video_url)}" poster="${escapeHTML(s.image_url)}" autoplay muted loop playsinline controls></video>
    <img hidden data-video-poster src="${escapeHTML(s.image_url)}" alt="">
    <div class="feed__gradient"></div><div class="feed__overlay"><div class="feed__row">
      <div class="feed__info"><h1 class="feed__title">${escapeHTML(s.title)}</h1>
      <input type="checkbox" id="desc-toggle" class="desc-toggle__checkbox"><p class="feed__description">${escapeHTML(s.description)}</p>
      <label for="desc-toggle" class="desc-toggle__label"><span class="label-more">Ещё</span><span class="label-less">Свернуть</span></label></div>
      <div class="feed__actions">
        <div class="feed__param-chip"><span class="feed__param-name">δ¹³C</span><span class="feed__param-val">${isotope(s.delta_c13)}</span></div>
        <div class="feed__param-chip"><span class="feed__param-name">δ¹⁵N</span><span class="feed__param-val">${isotope(s.delta_n15)}</span></div>
        <button type="button" class="feed-icon-btn__circle" data-like="${s.id}" data-liked="${s.is_liked}" aria-pressed="${Boolean(s.is_liked)}" aria-label="${user ? "Нравится" : "Войти, чтобы поставить лайк"}">♥</button><span class="like-action__count" data-like-count>${s.likes_count}</span>
        <button type="button" class="btn btn--primary" data-next="${s.id}">Далее →</button>
      </div></div></div>`;
}
async function draftPage() {
  const draft = await api("/services/draft");
  const media = `<div class="media-upload">
    <div class="upload-card"><div class="upload-card__preview">
      <img ${draft ? "" : 'data-preview="image"'} src="${escapeHTML(draft?.image_url || '/static/images/default_signature.png')}" alt="Фото образца">
    </div><span class="upload-card__label">Фото образца</span></div>
    <div class="upload-card"><div class="upload-card__preview">
      <video ${draft ? "" : 'data-preview="video"'} src="${escapeHTML(draft?.video_url || '/static/videos/default_signature.mp4')}" controls muted loop autoplay playsinline></video>
    </div><span class="upload-card__label">Видео анализа</span></div>
  </div>`;
  if (draft) return `<h1 class="page-title">Публикация</h1><h2>${escapeHTML(draft.title)}</h2>
    ${media}
    <form class="form-stack" data-publish="${draft.id}">
      <label class="field"><span class="field__label">Описание рациона</span><textarea class="field__textarea" name="description" required maxlength="10000">${escapeHTML(draft.description)}</textarea></label>
      ${field("δ¹⁵N (‰)", "delta_n15", "number", draft.delta_n15 ?? "", 'required step="any"')}
      ${field("δ¹³C (‰)", "delta_c13", "number", draft.delta_c13 ?? "", 'required step="any"')}
      <button class="btn btn--primary" type="submit">Опубликовать</button>
    </form><p><button type="button" class="btn btn--secondary" data-delete="${draft.id}">Удалить черновик</button></p>`;
  return `<h1 class="page-title">Новое исследование</h1><p class="helper">Сначала загрузите фото и короткое видео, затем заполните результаты анализа.</p>
    ${media}
    <form class="form-stack" data-create>
      ${field("Название", "title", "text", "", 'required maxlength="255"')}
      ${field("Фото: PNG, JPEG, WebP до 10 МиБ", "image", "file", "", 'required accept="image/png,image/jpeg,image/webp"')}
      ${field("Видео: MP4 до 64 МиБ и 60 секунд", "video", "file", "", 'required accept="video/mp4"')}
      <button class="btn btn--primary" type="submit">Сохранить черновик</button>
    </form>`;
}
async function editPage(id) {
  const record = await api(`/services/feed/${id}`);
  if (!record.is_creator) {
    const error = new Error("Изменять исследование может только автор.");
    error.code = 403;
    throw error;
  }
  return `<h1 class="page-title">Редактирование исследования</h1>
    <form class="form-stack" data-publish="${record.id}">
      ${field("Название", "title", "text", record.title, 'required maxlength="255"')}
      <label class="field"><span class="field__label">Описание рациона</span><textarea class="field__textarea" name="description" required maxlength="10000">${escapeHTML(record.description)}</textarea></label>
      ${field("δ¹⁵N (‰)", "delta_n15", "number", record.delta_n15, 'required step="any"')}
      ${field("δ¹³C (‰)", "delta_c13", "number", record.delta_c13, 'required step="any"')}
      <button class="btn btn--primary" type="submit">Сохранить изменения</button>
      <a class="btn btn--secondary" href="#/feed/${record.id}">Отмена</a>
    </form>`;
}
async function render() {
  const version = ++renderVersion;
  for (const url of previewUrls) URL.revokeObjectURL(url);
  previewUrls = [];
  notice.hidden = true;
  const route = location.hash.slice(1) || "/list";
  const [path, query = ""] = route.split("?");
  view.className = "page-main";
  view.setAttribute("aria-busy", "true");
  view.innerHTML = "<p>Загрузка…</p>";
  document.querySelectorAll(".tab").forEach((tab) => {
    const active = tab.hash === `#/${path.split("/")[1]}`;
    tab.classList.toggle("tab--active", active);
    if (active) tab.setAttribute("aria-current", "page"); else tab.removeAttribute("aria-current");
  });
  try {
    let html;
    if (path === "/list") html = await catalog(query);
    else if (/^\/feed(?:\/\d+)?$/.test(path)) html = await feed(path.split("/")[2]);
    else if (path === "/draft") {
      if (!user) { returnAfterLogin = "#/draft"; navigate("#/auth"); return; }
      html = await draftPage();
    } else if (/^\/edit\/\d+$/.test(path)) {
      if (!user) { returnAfterLogin = location.hash; navigate("#/auth"); return; }
      html = await editPage(path.split("/")[2]);
    } else if (path === "/auth" || path === "/auth/register") html = authPage(path.endsWith("register"));
    else html = unavailable();
    if (version !== renderVersion) return;
    view.innerHTML = html;
    if (path.startsWith("/feed")) view.className = "feed";
    document.title = `${view.querySelector("h1")?.textContent || "Исследования"} — IsoArch`;
  } catch (error) {
    if (version !== renderVersion) return;
    if (error.code === 401) { user = null; account(); returnAfterLogin = location.hash; navigate("#/auth"); }
    else if (error.code === 404) view.innerHTML = unavailable();
    else { view.innerHTML = '<p>Не удалось загрузить данные.</p><button type="button" class="btn btn--secondary" data-retry>Повторить</button>'; showError(error); }
  } finally {
    if (version === renderVersion) view.removeAttribute("aria-busy");
  }
}

document.addEventListener("submit", async (event) => {
  const form = event.target;
  event.preventDefault();
  notice.hidden = true;
  const button = form.querySelector('[type="submit"]');
  button.disabled = true;
  try {
    const fields = new FormData(form);
    if (form.hasAttribute("data-filter")) {
      const params = new URLSearchParams();
      for (const [key, value] of fields) if (value !== "") params.set(key, value);
      navigate(`#/list?${params}`);
    } else if (form.dataset.auth) {
      const data = Object.fromEntries(fields);
      if (form.dataset.auth === "register") {
        data.full_name ||= null; data.email ||= null;
        await api("/auth/register", jsonRequest("POST", data));
      }
      await api("/auth/login", jsonRequest("POST", {username: data.username, password: data.password}));
      await refreshUser();
      const target = returnAfterLogin; returnAfterLogin = "#/list";
      navigate(target);
    } else if (form.hasAttribute("data-create")) {
      await api("/services", {method: "POST", body: fields});
      await render();
    } else if (form.dataset.publish) {
      const s = await api(`/services/${form.dataset.publish}`, jsonRequest("PUT", {
        ...(fields.has("title") ? {title: fields.get("title")} : {}),
        description: fields.get("description"), delta_n15: Number(fields.get("delta_n15")), delta_c13: Number(fields.get("delta_c13"))
      }));
      navigate(`#/feed/${s.id}`);
    }
  } catch (error) { handleActionError(error); }
  finally { button.disabled = false; }
});
function handleActionError(error) {
  if (error.code === 401 && !location.hash.startsWith("#/auth")) {
    user = null; account(); returnAfterLogin = location.hash; navigate("#/auth");
  } else showError(error);
}
document.addEventListener("click", async (event) => {
  const button = event.target.closest("button");
  if (!button || button.type === "submit") return;
  button.disabled = true;
  try {
    if (button.hasAttribute("data-logout")) {
      await api("/auth/logout", {method: "POST"});
      user = null; account(); navigate("#/list");
    } else if (button.dataset.delete) {
      await api(`/services/${button.dataset.delete}`, {method: "DELETE"}); await render();
    } else if (button.dataset.like) {
      if (!user) { returnAfterLogin = location.hash; navigate("#/auth"); return; }
      const data = await api(`/services/${button.dataset.like}/like`, jsonRequest("POST", {like: Number(button.dataset.liked) ? 0 : 1}));
      button.dataset.liked = data.like;
      button.setAttribute("aria-pressed", String(Boolean(data.like)));
      view.querySelector("[data-like-count]").textContent = data.likes_count;
    } else if (button.dataset.next) {
      const data = await api(`/services/feed/${button.dataset.next}?next=true`); navigate(`#/feed/${data.id}`);
    } else if (button.hasAttribute("data-retry")) await render();
  } catch (error) { handleActionError(error); }
  finally { button.disabled = false; }
});
document.addEventListener("change", (event) => {
  const input = event.target;
  if (input.type !== "file") return;
  const preview = view.querySelector(`[data-preview="${input.name}"]`);
  if (!preview) return;
  if (preview.src.startsWith("blob:")) URL.revokeObjectURL(preview.src);
  if (input.files[0]) {
    const url = URL.createObjectURL(input.files[0]); previewUrls.push(url);
    preview.src = url; preview.hidden = false;
  } else {
    preview.src = input.name === "video" ? "/static/videos/default_signature.mp4" : "/static/images/default_signature.png";
  }
});
window.addEventListener("hashchange", render);
(async () => {
  if (!location.hash) {
    const legacy = location.pathname.split("/isotopic_signatures/")[1];
    history.replaceState(null, "", `#/${legacy || (location.pathname === "/login" ? "auth" : "list")}`);
  }
  try { await refreshUser(); } catch (error) { showError(error); }
  await render();
})();
