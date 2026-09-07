export type AIProviderTaskStatus = {
  task: "extraction" | "explanation";
  mode: "mock" | "openai_compatible";
  configured: boolean;
  provider_name: "deterministic_mock" | "openai_compatible" | "deepseek";
  configured_model: string | null;
  arbitrary_input_supported: boolean;
};

export type AIProviderStatus = {
  extraction: AIProviderTaskStatus;
  explanation: AIProviderTaskStatus;
};
