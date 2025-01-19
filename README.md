

# Aim of the project 
<p><b> Develop an AI-driven platform that generates personalized spiritual guidance through astrology and numerology. 
The system will provide insights, recommendations, and rituals based on user birth details, along with an interactive chatbot
 for spiritual advice.</b></p>

# Our solution
<p> We used an LLM integrated with openai to create personalized user outputs for users whose information would be stored in an astra database as backend.</p>

# How

## Dev Setup

Clone the repository and install dependencies to a virtual environment:

```console
cd voice-pipeline-agent-python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Set up the environment by copying `.env.example` to `.env.local` and filling in the required values:

- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `OPENAI_API_KEY`
- `DEEPGRAM_API_KEY`

You can also do this automatically using the LiveKit CLI:

```console
lk app env
```

Run the agent:

```console
python3 agent.py dev
```

This agent requires a frontend application to communicate with. You can use one of our example frontends in [livekit-examples](https://github.com/livekit-examples/), create your own following one of our [client quickstarts](https://docs.livekit.io/realtime/quickstarts/), or test instantly against one of our hosted [Sandbox](https://cloud.livekit.io/projects/p_/sandbox) frontends.
