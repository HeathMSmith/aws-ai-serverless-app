let API_URL = "";
let configLoaded = false;

async function loadConfig() {
  const response = await fetch("config.json");
  const config = await response.json();
  API_URL = config.api_url;
  configLoaded = true;
}

loadConfig();

async function sendRequest() {
  if (!configLoaded) {
    alert("App is still loading. Try again in a moment.");
    return;
  }

  const input = document.getElementById("input").value;
  const responseDiv = document.getElementById("response");
  const spinner = document.getElementById("spinner");

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
    document.getElementById("input").value = "";

  } catch (err) {
    spinner.style.display = "none";
    responseDiv.innerText = "Error: " + err.message;
  }
}