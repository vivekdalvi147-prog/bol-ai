from openai import OpenAI

client = OpenAI(
  api_key="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"
)

response = client.responses.create(
  model="gpt-5-nano",
  input="write a haiku about ai",
  store=True,
)

print(response.output_text);
