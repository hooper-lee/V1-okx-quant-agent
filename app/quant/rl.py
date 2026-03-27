class ReinforcementLearningService:
    def recommend(self, state: dict) -> dict:
        return {
            "enabled": False,
            "message": "RL module is a reserved extension point. Plug PPO/DQN policy training here later.",
            "state_features": list(state.keys()),
        }
