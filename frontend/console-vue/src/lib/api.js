function readCookie(name) {
  const key = `${name}=`;
  const rows = document.cookie ? document.cookie.split(";") : [];
  for (const row of rows) {
    const item = row.trim();
    if (!item.startsWith(key)) continue;
    try {
      return decodeURIComponent(item.slice(key.length));
    } catch {
      return item.slice(key.length);
    }
  }
  return "";
}

export async function apiRequest(path, options = {}, retry401 = true) {
  const init = {
    method: options.method || "GET",
    headers: { ...(options.headers || {}) },
    credentials: "same-origin",
  };

  if (options.body !== undefined) {
    init.headers["content-type"] = "application/json";
    init.body = JSON.stringify(options.body);
  }

  const cookieName = options.cookieName || "openclaw_control_token";
  const token = readCookie(cookieName);
  if (token && !init.headers.authorization) {
    init.headers.authorization = `Bearer ${token}`;
  }

  const response = await fetch(path, init);
  let payload = {};
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }

  if (response.status === 401 && retry401) {
    return apiRequest(path, options, false);
  }

  if (!response.ok || payload.ok === false) {
    const msg = payload.error || `request failed: ${response.status}`;
    throw new Error(msg);
  }

  return payload;
}
