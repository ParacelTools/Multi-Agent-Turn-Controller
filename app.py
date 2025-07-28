from flask import Flask, request, jsonify, render_template
import os
import json
import subprocess
from pathlib import Path

# Initialize Flask app and specify the templates folder
app = Flask(__name__, template_folder="templates")

# Define path to the agents directory and convo.md file
AGENTS_DIR = os.path.join(os.path.dirname(__file__), "agents")
MEMORY_PATH = os.path.join(os.path.dirname(__file__), "convo.md")

# Ensure the agents directory exists
os.makedirs(AGENTS_DIR, exist_ok=True)

# Route: main dashboard page (serves dashboard.html from templates folder)
@app.route("/")
def index():
    return render_template("index.html")

# Route: returns a list of agent names based on subdirectories in ./agents
@app.route("/api/agents")
def get_agents():
    agents = [name for name in os.listdir(AGENTS_DIR)
              if os.path.isdir(os.path.join(AGENTS_DIR, name))]
    return jsonify({"agents": agents})

# Route: accepts a JSON payload with {"agents": [...], "turns": N}
# Launches runner.py subprocess with arguments
@app.route("/api/queue_turns", methods=["POST"])
def queue_turns():
    data = request.get_json()
    agents = data.get("agents", [])
    turns = int(data.get("turns", 0))
    max_tokens = int(data.get("max_tokens", 1000))

    if not agents or turns < 1:
        return jsonify({"status": "No agents or invalid turn count"}), 400

    try:
        subprocess.Popen([
            "python3", "runner.py",
            "--turns", str(turns),
            "--agents", ",".join(agents),
            "--max_tokens", str(max_tokens)
        ])
        return jsonify({"status": f"Running agent runner with {turns} turns for: {', '.join(agents)}"})
    except Exception as e:
        return jsonify({"status": f"Failed to launch runner: {e}"}), 500

# Route: reads and returns the contents of convo.md so the controller can display it
@app.route("/api/view_memory")
def view_memory():
    if os.path.exists(MEMORY_PATH):
        with open(MEMORY_PATH, "r") as f:
            return jsonify({"content": f.read()})
    return jsonify({"content": ""})

@app.route("/api/post_message", methods=["POST"])
def post_message():
    data = request.get_json()
    text = data.get("text", "").strip()
    if text:
        with open("convo.md", "a") as f:
            f.write("##### USER SAYS:   " + text + "\n\n")
    return jsonify({"status": "ok"})

@app.route("/api/clear_convo", methods=["POST"])
def clear_convo():
    with open("convo.md", "w") as f:
        f.write("")  # erase content
    return jsonify({"status": "cleared"})

def tail_blocks(path, n=5):
    if not path.exists():
        return []
    try:
        text = path.read_text().strip()
        blocks = text.split("\n\n")
        return blocks[-n:]
    except Exception as e:
        return [f"[Error reading {path.name}: {e}]"]


def tail_blocks(path, n=5):
    if not path.exists():
        return []
    try:
        text = path.read_text().strip()
        blocks = text.split("\n\n")
        return blocks[-n:]
    except Exception as e:
        return [f"[Error reading {path.name}: {e}]"]

@app.route("/api/view_turn/<agent>")
def view_turn(agent):
    base = Path("agents") / agent

    logs = {
        "hcall": tail_blocks(base / "hcall_history.db", 5),
        "dcall": tail_blocks(base / "dcall_dialog.db", 5),
        "rcall": tail_blocks(base / "rcall_response.db", 5)
    }

    # Tail the llama_payload.log as a whole (last 100 lines)
    try:
        payload_lines = Path("llama_payload.log").read_text().splitlines()
        payload_tail = "\n".join(payload_lines[-100:])
    except Exception as e:
        payload_tail = f"[Error reading llama_payload.log: {e}]"

    return jsonify({
        "logs": logs,
        "payloads": {
            "tail": payload_tail
        }
    })

# Start the Flask server on port 5009, accessible on all interfaces
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5009)

