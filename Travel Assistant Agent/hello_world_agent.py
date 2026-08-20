from strands import Agent
from strands.models.bedrock import BedrockModel
from config import NOVA_LITE

# Nova Lite: Amazon's cheapest model — ideal for a first run.
model = BedrockModel(
    model_id=NOVA_LITE,
    region_name="us-east-1"
)

agent = Agent(model=model)

response = agent("Hello! Tell me a fun fact about AI agents.")
print(response)