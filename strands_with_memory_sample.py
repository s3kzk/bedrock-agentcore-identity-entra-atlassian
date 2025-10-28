from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent

app = BedrockAgentCoreApp()

agent = Agent(model="us.anthropic.claude-3-7-sonnet-20250219-v1:0")


@app.entrypoint
def strands_agent_bedrock(payload, context):
    prompt = payload.get("prompt", "こんにちは")
    response = agent(prompt)
    return response


if __name__ == "__main__":
    app.run()
