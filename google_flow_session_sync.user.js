// ==UserScript==
// @name         Google Flow Session Exporter & Sync
// @namespace    https://labs.google/fx/tools/flow
// @version      1.2.0
// @description  Export and sync Google Flow authenticated session cookies, localStorage, and OAuth token directly to local API server
// @author       Flow Automation Suite
// @match        https://labs.google/*
// @match        https://labs.google/fx/*
// @match        https://labs.google/fx/tools/flow*
// @match        https://*.google.com/*
// @grant        GM_cookie
// @grant        GM.cookie
// @grant        GM_xmlhttpRequest
// @grant        GM_setClipboard
// @grant        GM_notification
// @connect      127.0.0.1
// @connect      localhost
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  const LOCAL_API_URL = "http://127.0.0.1:8000/api/session/import";

  // Normalize SameSite values to Playwright/JSON schema
  function normalizeSameSite(sameSite) {
    if (!sameSite) return "Lax";
    const lower = String(sameSite).toLowerCase();
    if (lower.includes("strict")) return "Strict";
    if (lower.includes("none") || lower.includes("no_restriction")) return "None";
    return "Lax";
  }

  // Fetch all cookies via GM_cookie / GM.cookie or document.cookie fallback
  async function getAllCookies() {
    const cookieMap = new Map();

    function addCookies(list) {
      if (Array.isArray(list)) {
        for (const c of list) {
          if (c && c.name && !cookieMap.has(`${c.domain || ''}_${c.name}`)) {
            cookieMap.set(`${c.domain || ''}_${c.name}`, {
              name: c.name,
              value: c.value,
              domain: c.domain || "labs.google",
              path: c.path || "/",
              expires: c.expirationDate || c.expires || -1,
              httpOnly: Boolean(c.httpOnly),
              secure: Boolean(c.secure),
              sameSite: normalizeSameSite(c.sameSite),
            });
          }
        }
      }
    }

    // 1. Try GM_cookie.list with multiple scopes
    if (typeof GM_cookie !== "undefined" && typeof GM_cookie.list === "function") {
      const queries = [
        { url: "https://labs.google/fx/tools/flow" },
        { url: "https://labs.google/" },
        { domain: "labs.google" },
        { domain: ".labs.google" },
        { domain: ".google.com" },
        { domain: "google.com" },
        { domain: "accounts.google.com" },
        {}
      ];

      for (const q of queries) {
        await new Promise((resolve) => {
          try {
            GM_cookie.list(q, (cookies, error) => {
              if (!error && cookies) {
                addCookies(cookies);
              }
              resolve();
            });
          } catch (e) {
            resolve();
          }
        });
      }
    }

    // 2. Try async GM.cookie if available
    if (typeof GM !== "undefined" && GM.cookie && typeof GM.cookie.list === "function") {
      try {
        const c1 = await GM.cookie.list({ url: window.location.href });
        if (c1) addCookies(c1);
      } catch (e) {}
      try {
        const c2 = await GM.cookie.list({ domain: "labs.google" });
        if (c2) addCookies(c2);
      } catch (e) {}
      try {
        const c3 = await GM.cookie.list({ domain: ".google.com" });
        if (c3) addCookies(c3);
      } catch (e) {}
    }

    // 3. Fallback: Include document.cookie entries
    const raw = document.cookie.split(";");
    for (const pair of raw) {
      const trimmed = pair.trim();
      if (!trimmed) continue;
      const [name, ...valParts] = trimmed.split("=");
      const key = `labs.google_${name}`;
      if (name && !cookieMap.has(key)) {
        cookieMap.set(key, {
          name: name,
          value: valParts.join("="),
          domain: "labs.google",
          path: "/",
          expires: -1,
          httpOnly: false,
          secure: true,
          sameSite: "Lax",
        });
      }
    }

    return Array.from(cookieMap.values());
  }

  function getOriginsData() {
    const origins = [];
    try {
      const localStorageData = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        localStorageData.push({ name: key, value: localStorage.getItem(key) });
      }
      origins.push({
        origin: window.location.origin,
        localStorage: localStorageData
      });
    } catch (e) {}
    return origins;
  }

  async function getSessionPayload() {
    const cookies = await getAllCookies();
    const origins = getOriginsData();
    let authUser = null;
    let accessToken = null;

    try {
      const res = await fetch("/fx/api/auth/session");
      if (res.ok) {
        const sessionData = await res.json();
        authUser = sessionData.user || null;
        accessToken = sessionData.accessToken || sessionData.access_token || sessionData.token || null;
      }
    } catch (e) {
      console.warn("[Flow Sync] Could not fetch /fx/api/auth/session:", e);
    }

    return {
      cookies: cookies,
      access_token: accessToken,
      accessToken: accessToken,
      origins: origins,
      user: authUser,
      exportedAt: new Date().toISOString(),
    };
  }

  // Create UI Widget
  function injectWidget() {
    if (document.getElementById("flow-session-sync-widget")) return;

    const container = document.createElement("div");
    container.id = "flow-session-sync-widget";
    container.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      z-index: 999999;
      background: #18191c;
      color: #e3e3e3;
      border: 1px solid #333539;
      border-radius: 10px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      font-size: 13px;
      padding: 14px 16px;
      width: 290px;
      transition: all 0.2s ease;
    `;

    container.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
        <div style="font-weight: 600; display: flex; align-items: center; gap: 6px; font-size: 13px;">
          <span>⚡</span> Flow API Session Sync
        </div>
        <button id="flow-sync-min-btn" style="background: none; border: none; color: #888; cursor: pointer; font-size: 14px; padding: 2px;">−</button>
      </div>
      <div id="flow-sync-body">
        <div id="flow-sync-status" style="font-size: 11px; color: #9aa0a6; margin-bottom: 12px; line-height: 1.4;">
          Checking authentication status...
        </div>
        <div style="display: flex; flex-direction: column; gap: 8px;">
          <button id="flow-sync-post-btn" style="
            background: #2563eb;
            color: #ffffff;
            border: none;
            border-radius: 6px;
            padding: 8px 12px;
            font-weight: 500;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            font-size: 12px;
          ">
            <span>⚡</span> Sync to Local Server (:8000)
          </button>
          <button id="flow-sync-copy-btn" style="
            background: #27272a;
            color: #d4d4d8;
            border: 1px solid #3f3f46;
            border-radius: 6px;
            padding: 7px 12px;
            font-weight: 500;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            font-size: 12px;
          ">
            <span>📋</span> Copy session_state.json
          </button>
        </div>
        <div id="flow-sync-msg" style="margin-top: 10px; font-size: 11px; display: none; line-height: 1.3;"></div>
      </div>
    `;

    document.body.appendChild(container);

    const minBtn = container.querySelector("#flow-sync-min-btn");
    const body = container.querySelector("#flow-sync-body");
    let minimized = false;

    minBtn.onclick = () => {
      minimized = !minimized;
      body.style.display = minimized ? "none" : "block";
      minBtn.textContent = minimized ? "+" : "−";
    };

    const statusEl = container.querySelector("#flow-sync-status");
    const msgEl = container.querySelector("#flow-sync-msg");
    const postBtn = container.querySelector("#flow-sync-post-btn");
    const copyBtn = container.querySelector("#flow-sync-copy-btn");

    function showMessage(text, color) {
      msgEl.style.display = "block";
      msgEl.style.color = color;
      msgEl.textContent = text;
      setTimeout(() => {
        if (msgEl) msgEl.style.display = "none";
      }, 6000);
    }

    // Check auth status on load
    fetch("/fx/api/auth/session")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && data.user && data.user.email) {
          statusEl.innerHTML = `👤 Active: <strong style="color:#e2e8f0;">${data.user.email}</strong>`;
        } else {
          statusEl.innerHTML = `<span style="color:#f59e0b;">⚠️ Not logged in to Google Flow</span>`;
        }
      })
      .catch(() => {
        statusEl.textContent = "Ready to export session.";
      });

    // Handle Direct Post
    postBtn.onclick = async () => {
      postBtn.disabled = true;
      postBtn.textContent = "Syncing...";
      try {
        const payload = await getSessionPayload();

        if (typeof GM_xmlhttpRequest !== "undefined") {
          GM_xmlhttpRequest({
            method: "POST",
            url: LOCAL_API_URL,
            headers: { "Content-Type": "application/json" },
            data: JSON.stringify(payload),
            onload: function (response) {
              postBtn.disabled = false;
              postBtn.innerHTML = "<span>⚡</span> Sync to Local Server (:8000)";
              if (response.status >= 200 && response.status < 300) {
                const resData = JSON.parse(response.responseText || "{}");
                const email = (resData.user && resData.user.email) || (payload.user && payload.user.email) || "Active User";
                const tokenState = resData.token_active ? "Token Attached" : "Cookies Attached";
                showMessage(`✅ Synced! (${email} - ${tokenState})`, "#4ade80");
              } else {
                showMessage(`❌ Server error: HTTP ${response.status}`, "#f87171");
              }
            },
            onerror: function () {
              postBtn.disabled = false;
              postBtn.innerHTML = "<span>⚡</span> Sync to Local Server (:8000)";
              showMessage("❌ Could not connect to http://127.0.0.1:8000. Is the server running?", "#f87171");
            },
          });
        } else {
          const res = await fetch(LOCAL_API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          postBtn.disabled = false;
          postBtn.innerHTML = "<span>⚡</span> Sync to Local Server (:8000)";
          if (res.ok) {
            const resData = await res.json();
            const email = (resData.user && resData.user.email) || "Active User";
            showMessage(`✅ Synced! (${email})`, "#4ade80");
          } else {
            showMessage(`❌ Server returned HTTP ${res.status}`, "#f87171");
          }
        }
      } catch (err) {
        postBtn.disabled = false;
        postBtn.innerHTML = "<span>⚡</span> Sync to Local Server (:8000)";
        showMessage(`❌ Sync failed: ${err.message}`, "#f87171");
      }
    };

    // Handle Copy to Clipboard
    copyBtn.onclick = async () => {
      copyBtn.disabled = true;
      copyBtn.textContent = "Copying...";
      try {
        const payload = await getSessionPayload();
        const jsonStr = JSON.stringify(payload, null, 2);

        if (typeof GM_setClipboard !== "undefined") {
          GM_setClipboard(jsonStr, "text");
        } else if (navigator.clipboard) {
          await navigator.clipboard.writeText(jsonStr);
        }

        copyBtn.disabled = false;
        copyBtn.innerHTML = "<span>📋</span> Copy session_state.json";
        showMessage(`📋 Copied session (${payload.cookies.length} cookies + Bearer token) to clipboard!`, "#60a5fa");
      } catch (err) {
        copyBtn.disabled = false;
        copyBtn.innerHTML = "<span>📋</span> Copy session_state.json";
        showMessage(`❌ Copy failed: ${err.message}`, "#f87171");
      }
    };
  }

  // Inject UI once page is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", injectWidget);
  } else {
    injectWidget();
  }
})();
