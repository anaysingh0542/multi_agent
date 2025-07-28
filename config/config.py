"""
Centralized configuration management for the multi-agent system.
"""
import os
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class Config:
    """Configuration class for the multi-agent system."""
    
    # API Configuration
    openai_api_key: str
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.0
    
    # File Paths
    agent_knowledge_path: str = "./data/agent_routing_knowledge.xlsx"
    
    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "%(asctime)s [%(levelname)s] [%(name)s] - %(message)s"
    
    # Application Settings
    max_retries: int = 3
    timeout_seconds: int = 30
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables."""
        load_dotenv()
        
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        return cls(
            openai_api_key=openai_api_key,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            openai_temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.0")),
            agent_knowledge_path=os.getenv("AGENT_KNOWLEDGE_PATH", "./data/agent_routing_knowledge.xlsx"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_format=os.getenv("LOG_FORMAT", "%(asctime)s [%(levelname)s] [%(name)s] - %(message)s"),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            timeout_seconds=int(os.getenv("TIMEOUT_SECONDS", "30")),
        )
    
    def validate(self) -> None:
        """Validate configuration values."""
        if not self.openai_api_key:
            raise ValueError("OpenAI API key cannot be empty")
        
        if self.openai_temperature < 0 or self.openai_temperature > 2:
            raise ValueError("OpenAI temperature must be between 0 and 2")
        
        if self.max_retries < 0:
            raise ValueError("Max retries must be non-negative")
        
        if self.timeout_seconds <= 0:
            raise ValueError("Timeout seconds must be positive")


# Global configuration instance
config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global config
    if config is None:
        config = Config.from_env()
        config.validate()
    return config


def reset_config() -> None:
    """Reset the global configuration instance (useful for testing)."""
    global config
    config = None