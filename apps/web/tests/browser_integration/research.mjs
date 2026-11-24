import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const origin = "http://127.0.0.1:18767";
const debuggerOrigin = "http://127.0.0.1:9229";

const sessions = JSON.parse(
  readFileSync(
    "/tmp/agentops-s03-browser-sessions.json",
    "utf8",
  ),
);

const question = "Compare synthetic competitors in Europe";

const pause = (ms) =>
  new Promise((resolve) => setTimeout(resolve, ms));

async function eventually(action, timeout = 15000) {
  const deadline = Date.now() + timeout;

  while (Date.now() < deadline) {
    const value = await action();

    if (value) return value;

    await pause(150);
  }

  throw new Error("Browser assertion timed out");
}

const pages = await eventually(async () => {
  try {
    const response = await fetch(`${debuggerOrigin}/json/list`);
    return await response.json();
  } catch {
    return null;
  }
});

const page = pages.find((item) => item.type === "page");

assert.ok(page?.webSocketDebuggerUrl);

const socket = new WebSocket(page.webSocketDebuggerUrl);

await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", reject, { once: true });
});

let sequence = 0;

const pending = new Map();
const responses = [];
const requests = [];

socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);

  if (message.id && pending.has(message.id)) {
    const { resolve, reject, timer } = pending.get(message.id);

    clearTimeout(timer);
    pending.delete(message.id);

    if (message.error) {
      reject(new Error("Chrome command failed"));
    } else {
      resolve(message.result);
    }
  }

  if (message.method === "Network.responseReceived") {
    const response = message.params.response;

    responses.push({
      url: response.url,
      status: response.status,
    });
  }

  if (message.method === "Network.requestWillBeSent") {
    const request = message.params.request;

    requests.push({
      url: request.url,
      method: request.method,
    });
  }
});

function command(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;

    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error("Chrome command timed out"));
    }, 15000);

    pending.set(id, { resolve, reject, timer });

    socket.send(JSON.stringify({ id, method, params }));
  });
}

async function evaluate(expression) {
  const result = await command("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });

  assert.ok(!result.exceptionDetails, "Browser evaluation failed");

  return result.result.value;
}

async function waitForText(value) {
  return eventually(() =>
    evaluate(
      `document.body?.innerText.includes(${JSON.stringify(value)})`,
    ),
  );
}

async function navigate(path) {
  await command("Page.navigate", {
    url: `${origin}${path}`,
  });

  await eventually(() =>
    evaluate(
      `location.pathname === ${JSON.stringify(path)}
       && document.readyState === "complete"`,
    ),
  );
}

async function setSession(token) {
  await command("Network.clearBrowserCookies");

  const result = await command("Network.setCookie", {
    name: "agentops_dev_session",
    value: token,
    url: origin,
    httpOnly: true,
    secure: false,
    sameSite: "Lax",
    path: "/",
  });

  assert.equal(result.success, true);
}

async function typeInto(selector, value) {
  await evaluate(
    `document.querySelector(${JSON.stringify(selector)}).focus()`,
  );

  await command("Input.insertText", {
    text: value,
  });

  assert.equal(
    await evaluate(
      `document.querySelector(${JSON.stringify(selector)}).value`,
    ),
    value,
  );
}

async function clickButton(label) {
  const clicked = await evaluate(`
    (() => {
      const button = [...document.querySelectorAll("button")]
        .find(item => item.innerText.trim() === ${JSON.stringify(label)});

      if (!button || button.disabled) return false;

      button.click();
      return true;
    })()
  `);

  assert.equal(clicked, true);
}

try {
  await command("Page.enable");
  await command("Runtime.enable");
  await command("Network.enable");

  // Unauthenticated browser must not receive research records.
  await command("Network.clearBrowserCookies");
  await navigate("/research/history");
  await waitForText("Authentication required");

  console.log("BROWSER_UNAUTHENTICATED_PASS");

  // Authenticate only through a synthetic test fixture.
  await setSession(sessions.token_a);

  await navigate("/research/new");
  await waitForText("Submit research");

  await typeInto("#research-question", question);
  await typeInto("#geography", "Europe");
  await typeInto("#category", "Synthetic software");
  await typeInto("#competitors", "Company A\nCompany B");

  await clickButton("Submit research");

  const taskPath = await eventually(async () => {
    const path = await evaluate("location.pathname");

    return /^\/research\/tasks\/[0-9a-f-]{36}$/i.test(path)
      ? path
      : null;
  });

  await waitForText(question);
  await waitForText("Queued");

  const taskId = taskPath.split("/").pop();

  assert.ok(responses.some(
    (response) =>
      response.url === `${origin}/api/v1/auth/csrf`
      && response.status === 200,
  ));

  assert.ok(responses.some(
    (response) =>
      response.url === `${origin}/api/v1/research/tasks`
      && response.status === 202,
  ));

  assert.equal(requests.filter(
    (request) =>
      request.url === `${origin}/api/v1/research/tasks`
      && request.method === "POST",
  ).length, 1);

  console.log("BROWSER_CSRF_PASS");
  console.log("BROWSER_SUBMISSION_202_PASS");
  console.log("BROWSER_SINGLE_POST_PASS");
  console.log("BROWSER_TASK_DETAIL_PASS");

  const detailUrl = `${origin}/api/v1/research/tasks/${taskId}`;

  const detailCount = () => responses.filter(
    (response) =>
      response.url === detailUrl
      && response.status === 200,
  ).length;

  const previousCount = detailCount();

  await eventually(
    () => detailCount() > previousCount,
    12000,
  );

  await waitForText("Queued");

  console.log("BROWSER_REAL_STATUS_POLLING_PASS");

  await navigate("/research/history");
  await waitForText(question);

  assert.ok(await evaluate(`
    [...document.querySelectorAll("a")]
      .some(link => link.getAttribute("href") ===
        ${JSON.stringify(taskPath)})
  `));

  console.log("BROWSER_OWNER_HISTORY_PASS");

  const afterNavigationCount = detailCount();

  await pause(6500);

  assert.equal(detailCount(), afterNavigationCount);

  console.log("BROWSER_POLLING_CANCELLED_PASS");

  // Account B must never see account A's research.
  await setSession(sessions.token_b);

  await navigate("/research/history");
  await waitForText("No research history yet");

  assert.equal(
    await evaluate(
      `document.body.innerText.includes(${JSON.stringify(question)})`,
    ),
    false,
  );

  await navigate(taskPath);
  await waitForText("The requested research resource is unavailable.");

  assert.ok(responses.some(
    (response) =>
      response.url === detailUrl
      && response.status === 404,
  ));

  assert.equal(
    await evaluate(
      `document.body.innerText.includes(${JSON.stringify(question)})`,
    ),
    false,
  );

  console.log("BROWSER_FOREIGN_HISTORY_ISOLATION_PASS");
  console.log("BROWSER_FOREIGN_DETAIL_404_PASS");

  await setSession(sessions.token_a);
  await navigate(taskPath);
  await waitForText(question);
  await waitForText("Queued");

  console.log("BROWSER_OWNER_ACCESS_RESTORED_PASS");
  console.log(`SYNTHETIC_TASK_ID=${taskId}`);

  console.log("WP04_BROWSER_E2E_PASS");
} finally {
  await command("Network.clearBrowserCookies");
  socket.close();
}
