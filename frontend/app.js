const API_URL = "https://f1p9igzl60.execute-api.us-east-1.amazonaws.com";

let history = [];

function toggleDarkMode() {
  document.body.classList.toggle("dark");
}

async function sendRequest() {
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

    // Clear input after successful response
    document.getElementById("input").value = "";

  } catch (err) {
    spinner.style.display = "none";
    responseDiv.innerText = "Error: " + err.message;
  }
}

function copyResponse() {
  const text = document.getElementById("response").innerText;
  navigator.clipboard.writeText(text);
}

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