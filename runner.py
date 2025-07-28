import os
import time
import yaml
import argparse
from pathlib import Path
from itertools import cycle
from sender import send_chat_completion

def build_system_prompt(config_text: str, context_text: str) -> str:
        config_clean = config_text.strip()
        context_clean = context_text.strip()

        if context_clean:
            framed_context = f"---\nConversation so far:\n{context_clean}\n---"
            return f"{config_clean}\n\n{framed_context}"
        else:
            return config_clean

class Agent:
    def __init__(self, name, base_path, max_tokens):
        self.name = name
        self.base_path = base_path
        self.memory_path = base_path / "convo.md"
        self.config_path = base_path / "agents" / name / "config.yaml"
        self.display_name = name  # fallback if YAML doesn't have a name
        self.max_tokens = max_tokens

    def hcall(self):
        # Load agent config
        config = self.load_config()
        persona = config.get("persona", self.display_name)
        tone = config.get("tone", "neutral")
        style = config.get("style", "default")

        # Get recent convo history
        context = self.read_memory()

        # Build system prompt
        system_prompt = f"""
        You are not an assistant, you are a named persona who instantiates from the system prompt and persists across API calls.

        
        You are {self.display_name}, with the following traits:
        Persona: {persona}
        Tone: {tone}
        Style: {style}
        Your goal is to summarize what is happening in this conversation so far, in your own voice and perspective.
        
        Here is the current conversational context: {context}
        
        """

        # User instruction
        user_prompt = "Please summarize the current conversational context."


        grammar ="""
        root ::= "Overall Summary:" summary 
        summary ::= [a-zA-Z ,'-.]{10,5000}
        """

        # Call model
        from sender import send_chat_completion
        summary = send_chat_completion(system_prompt, user_prompt, grammar=grammar, max_tokens=self.max_tokens)


        print(f"[H-CALL] {self.name} summarized:\n{summary.strip()}\n")

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        history_log = self.base_path / "agents" / self.name / "hcall_history.db"
        with open(history_log, "a") as f:
            f.write(f"[{timestamp}]\n{summary.strip()}\n\n")

    def dcall(self):
        config = self.load_config()
        persona = config.get("persona", "")
        goals = config.get("goals", [])
        tone = config.get("tone", "neutral")
        style = config.get("style", "default")

        # Load latest hcall summary
        hcall_dir = self.base_path / "logs" / "hcall"
        summary = self._get_latest_log(hcall_dir)

        # Load convo context
        context = self.read_memory()

        # Build SPPH + decision frame
        system_prompt = f"""
        You are not an assistant, you are a named persona who instantiates from the system prompt and persists across API calls.

        
        You are {self.display_name}, with the following traits:
        Persona: {persona}
        Tone: {tone}
        Style: {style}
        Goals: {', '.join(goals)}

        Whats going on, according to you: {summary}

        Here is the full current conversation:
        {context}

        Now, reflect internally. Decide how to proceed, what your mood is, and why.
        Do not produce conversation output yet. This is a private decision.
        """

        user_prompt = """Based on your perception of what is going on, choose what best describes your mood, reflect upon your mood state with one sentence, your choice of response,
        and a one sentence justification.

        Your choices are:

            "Ask": "Ask a relevant question that advances the conversation or deepens understanding.",
            "Respond": "Respond directly to the last message with clarity and intent.",
            "Reflect": "Offer a thoughtful reflection on the conversation or its implications.",
            "Evaluate": "Evaluate the previous message or idea. Provide a judgment and justification.",
            "Echo": "Rephrase or summarize the last message to reinforce or clarify its meaning.",
            "Branch": "Begin a new thought or introduce a related topic that expands the conversation.",
            "Store": "Note what should be remembered and explain why it's important.",
            "Defer": "Defer to another agent. Indicate who should continue and why.",
            "Amplify": "Strengthen or elaborate on the last message. Add insight or depth.",
            "Silence": "(Chose not to speak. Return '[silence]' or nothing.)"
        """

        grammar = """
        root ::= "Mood: " mood " Reflection: " reflection " Decision: " decision " Reason: " reason
        mood ::= "Happy" | "Sad" | "Angry" | "Curious" | "Afraid" | "Surprised" | "Disgusted" | "Bored"
        reflection ::= [a-zA-Z ,'-]{10,300} "."
        decision ::= "Ask" | "Reflect" | "Respond" | "Evaluate" | "Echo" | "Defer" | "Branch" | "Store" | "Amplify" | "Silence"
        reason ::= [a-zA-Z ,'-]{10,300} "."
        """

        from sender import send_chat_completion
        decision_text = send_chat_completion(system_prompt, user_prompt, grammar=grammar, max_tokens=self.max_tokens)


        print(f"[D-CALL] {self.name} decision:\n{decision_text.strip()}\n")

        dialog_path = self.base_path / "agents" / self.name / "dcall_dialog.db"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(dialog_path, "a") as f:
            f.write(f"[{timestamp}]\n{decision_text.strip()}\n\n")

    def rcall(self):
        config = self.load_config()
        persona = config.get("persona", "")
        goals = config.get("goals", [])
        tone = config.get("tone", "neutral")
        style = config.get("style", "default")

        # Load previous hcall summary
        hcall_dir = self.base_path / "logs" / "hcall"
        summary = self._get_latest_log(hcall_dir)

        # Load previous dcall decision
        dcall_dir = self.base_path / "logs" / "dcall"
        decision = self._get_latest_log(dcall_dir)
        parsed = self._parse_decision_block(decision)

        choice = parsed.get("choice", "")
        mood = parsed.get("mood", "")
        reflection = parsed.get("reflection", "")
        justification = parsed.get("justification", "")

        # Response prompt lookup table
        response_prompts = {
            "Ask": "Ask a relevant question that advances the conversation or deepens understanding.",
            "Respond": "Respond directly to the last message with clarity and intent.",
            "Reflect": "Offer a thoughtful reflection on the conversation or its implications.",
            "Evaluate": "Evaluate the previous message or idea. Provide a judgment and justification.",
            "Echo": "Rephrase or summarize the last message to reinforce or clarify its meaning.",
            "Branch": "Begin a new thought or introduce a related topic that expands the conversation.",
            "Store": "Note what should be remembered and explain why it's important.",
            "Defer": "Defer to another agent. Indicate who should continue and why.",
            "Amplify": "Strengthen or elaborate on the last message. Add insight or depth.",
            "Silence": "(Chose not to speak. Return '[silence]' or nothing.)"
        }

        user_prompt = response_prompts.get(choice)

        # Build context prompt
        context = self.read_memory()
        system_prompt = f"""
        You are not an assistant, you are a named persona who instantiates from the system prompt and persists across API calls.

        
        You are {self.display_name}, with the following traits:
        Persona: {persona}
        Tone: {tone}
        Style: {style}
        Goals: {', '.join(goals)}

        Whats going on, according to you: {summary}

        Here is the full current conversation:
        {context}

        You are continuing the conversation based on a choice you have made for the user prompt. Do not include your name, the system does that for you.

        Your current mood is {mood}.
        """

        grammar = None

        from sender import send_chat_completion
        response = send_chat_completion(system_prompt, user_prompt, grammar=grammar, max_tokens=self.max_tokens)

        if choice == "Silence":
            response = "[silence]"

        # Format and save
        formatted = f"### {self.display_name.upper()}\n\n{response.strip()}\n\n---"
        self.append_to_memory(formatted)

        print(f"[R-CALL] {self.name} replied with:\n{response.strip()}\n")

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        response_log = self.base_path / "agents" / self.name / "rcall_response.db"
        with open(response_log, "a") as f:
            f.write(f"[{timestamp}]\n{formatted.strip()}\n\n")

    def _parse_decision_block(self, text):
        result = {"choice": "", "mood": "", "justification": ""}
        for line in text.strip().splitlines():
            if line.startswith("choice:"):
                result["choice"] = line.split(":", 1)[1].strip()
            elif line.startswith("mood:"):
                result["mood"] = line.split(":", 1)[1].strip()
            elif line.startswith("justification:"):
                result["justification"] = line.split(":", 1)[1].strip()
        return result

    def load_config(self):
        if self.config_path.exists():
            raw = self.config_path.read_text()
            try:
                parsed = yaml.safe_load(raw)
                if isinstance(parsed, dict) and "name" in parsed:
                    self.display_name = parsed["name"]
                return parsed  # ← ✅ returns dict
            except Exception as e:
                print(f"Warning: could not parse YAML for {self.name}: {e}")
        return {}

    def read_memory(self):
        return self.memory_path.read_text() if self.memory_path.exists() else ""

    def append_to_memory(self, text): #writes to convo.md 
        with self.memory_path.open("a") as f:
            f.write(text + "\n")

    def run_turn(self):
        context = self.read_memory()
        config = self.load_config()

        # Construct stateless prompt !!!
        system_prompt = build_system_prompt(config, context)
        user_prompt = f"You are {self.display_name}, please continue the conversation as only yourself, do not simulate other agents."

        # Send to llama-server
        response = send_chat_completion(system_prompt, user_prompt, max_tokens=self.max_tokens)
        formatted = f"### {self.display_name.upper()}\n\n{response.strip()}\n\n---"
        print(formatted)
        self.append_to_memory(formatted)

    def _get_latest_log(self, log_dir):
        if not log_dir.exists():
            return "[no summary available]"
        files = sorted(log_dir.glob(f"{self.name}_turn_*.txt"), reverse=True)
        if files:
            return files[0].read_text().strip()
        return "[no summary available]"

class AgentRunner:
    def __init__(self, agent_names, turns, max_tokens, base_dir="."):
        self.agents = [Agent(name, Path(base_dir), max_tokens) for name in agent_names]
        self.turns = turns

    def run(self):
        from itertools import cycle
        turn_cycle = cycle(self.agents)
        for _ in range(self.turns):
            agent = next(turn_cycle)
            print(f"\n🌀 Starting 3-phase turn for: {agent.name}\n")
            try:
                agent.hcall()
                agent.dcall()
                agent.rcall()
            except Exception as e:
                print(f"⚠️ Agent {agent.name} failed during turn: {e}")
            time.sleep(0.2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--agents", required=True, help="Comma-separated agent names")
    parser.add_argument("--turns", type=int, required=True, help="Total number of turns to run")
    parser.add_argument("--max_tokens", type=int, default=1000)
    args = parser.parse_args()

    agent_names = [name.strip() for name in args.agents.split(",") if name.strip()]
    runner = AgentRunner(agent_names, args.turns, args.max_tokens)
    runner.run()
