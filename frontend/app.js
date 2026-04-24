// ================================
// Runtime config
// ================================
let API_URL = "";
let configLoaded = false;

async function loadConfig() {
  try {
    const res = await fetch("config.json");
    const config = await res.json();
    API_URL = config.api_url; // no /process here
    configLoaded = true;

    // enable button once ready (if you have one)
    const btn = document.getElementById("sendBtn");
    if (btn) btn.disabled = false;

  } catch (err) {
    console.error("Failed to load config:", err);
    const responseDiv = document.getElementById("response");
    if (responseDiv) {
      responseDiv.innerText = "Failed to load app configuration.";
    }
  }
}

// Disable button until config loads
document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("sendBtn");
  if (btn) btn.disabled = true;

  loadConfig();
});


// ================================
// UI State
// ================================
let history = [];

function toggleDarkMode() {
  document.body.classList.toggle("dark");
}


// ================================
// Main Request Handler
// ================================
async function sendRequest() {
  if (!configLoaded) {
    alert("App is still loading. Try again in a moment.");
    return;
  }

  const inputEl = document.getElementById("input");
  const responseDiv = document.getElementById("response");
  const spinner = document.getElementById("spinner");

  const input = inputEl.value;

  if (!input.trim()) {
    responseDiv.innerText = "Please enter a prompt.";
    return;
  }

  spinner.style.display = "block";
  responseDiv.innerText = "";

  try {
    const res = await fetch(`${API_URL}/process`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ input })
    });

    const data = await res.json();
    spinner.style.display = "none";

    const output = data.response || JSON.stringify(data);
    responseDiv.innerText = output;

    addToHistory(input, output);

    // Clear input
    inputEl.value = "";

  } catch (err) {
    spinner.style.display = "none";
    responseDiv.innerText = "Error: " + err.message;
  }
}


// ================================
// Clipboard
// ================================
function copyResponse() {
  const text = document.getElementById("response").innerText;
  navigator.clipboard.writeText(text);
}


// ================================
// History
// ================================
function addToHistory(input, output) {
  history.unshift({ input, output });

  const historyDiv = document.getElementById("history");
  historyDiv.innerHTML = "<h3>History</h3>";

  history.slice(0, 5).forEach(item => {
    const div = document.createElement("div");
    div.className = "history-item";
    div.innerText = `Q: ${item.input}\nA: ${item.output}`;
    historyDiv.appendChild(div);
  });
}