export async function apiRequest(path, options = {}, retry401 = true) {
  const init = {
    method: options.method || "GET",
    headers: {},
  };

  if (options.body !== undefined) {
    init.headers["content-type"] = "application/json";
    init.body = JSON.stringify(options.body);
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
