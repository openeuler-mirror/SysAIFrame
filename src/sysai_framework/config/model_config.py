"""
Copyright (C) 2025 CTyunOS. All Rights Reserved.
File: model_config.py
Desc: Model configuration management for SysAIFrame
     Handles model configuration loading, validation and management
Date: 2025-10-28
Author: Liu Mingran
"""

import yaml
import logging
import os
import hashlib
import uuid
import fcntl
import time
import threading
from enum import Enum
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from contextlib import contextmanager
from ruamel.yaml import YAML  # type: ignore
from ruamel.yaml.comments import CommentedMap, CommentedSeq  # type: ignore

from sysai_framework.utils.provider_utils import SUPPORTED_PROVIDERS

if TYPE_CHECKING:
    from sysai_framework.core.status_codes import OperationResult

logger = logging.getLogger(__name__)

# Timeout constants - single source of truth
DEFAULT_ROUTING_TIMEOUT = 300  # Default timeout for routing (fallback chain budget)


# Predefined capability constants (recommended for common use cases)
# Note: Users can define custom capabilities in YAML - these are just standard suggestions
CAPABILITY_GENERAL = "general"      # General chat capability
CAPABILITY_CODE = "code"           # Code-related capability
CAPABILITY_ANALYSIS = "analysis"   # Analysis task capability
CAPABILITY_CREATIVE = "creative"   # Creative writing capability

# Capability prefix for requests (e.g., "capability-code")
CAPABILITY_PREFIX = "capability-"

# Special model names
SPECIAL_MODEL_DEFAULT = "default"  # Use default model
SPECIAL_MODEL_MOCK = "mock"        # Use built-in Mock model


class UnhealthyReason(Enum):
    """Model unhealthy reason enumeration"""
    NONE = "none"                          # Healthy status
    LIGHTWEIGHT_CHECK_FAILED = "lightweight"  # Lightweight check failed
    ACTUAL_REQUEST_FAILED = "actual_request"  # Actual request failed


@dataclass
class ValidationMessage:
    """Validation message with level (error or warning)"""
    level: str  # "error" or "warning"
    message: str
    
    def __str__(self) -> str:
        return self.message


@dataclass
class HealthCheckConfig:
    """Health check configuration"""
    lightweight_enabled: bool = True
    lightweight_interval: int = 300  # seconds
    actual_request_enabled: bool = False  # Default disabled to avoid API costs
    actual_request_interval: int = 1200  # seconds
    timeout: int = 10  # seconds


@dataclass
class RetryPolicyConfig:
    """Retry policy configuration"""
    max_attempts: int = 3
    backoff_factor: int = 2
    base_delay: int = 1  # seconds
    max_delay: int = 30  # seconds


@dataclass
class LoadBalanceOptionsConfig:
    """Load balance strategy options configuration"""
    latency_buffer: float = 0.1  # lowest-latency: latency buffer ratio (0.0-1.0)
    latency_window: int = 10  # lowest-latency: latency sampling window size
    usage_window: int = 60  # usage-based: usage statistics window in seconds


@dataclass
class LoadBalanceConfig:
    """Load balance configuration"""
    strategy: str = "weighted"  # round-robin | weighted | least-busy | lowest-latency | usage-based
    options: LoadBalanceOptionsConfig = field(default_factory=LoadBalanceOptionsConfig)


@dataclass
class RuntimeConfig:
    """Runtime mode configuration"""
    mode: str = "default"  # default | load-balance
    load_balance: LoadBalanceConfig = field(default_factory=LoadBalanceConfig)


@dataclass
class RoutingConfig:
    """Routing configuration"""
    default_model: Optional[str] = None
    default_model_instance_id: Optional[str] = None
    health_check: HealthCheckConfig = field(default_factory=HealthCheckConfig)
    retry_policy: RetryPolicyConfig = field(default_factory=RetryPolicyConfig)
    timeout: int = DEFAULT_ROUTING_TIMEOUT  # Default timeout for LLM requests
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)  # Runtime mode configuration


@dataclass
class ModelConfig:
    """
    Model configuration data structure for SysAIFrame
    
    Fields:
        name: Model logical name (can be shared by multiple instances)
        instance_id: Unique instance identifier (auto-generated if not provided)
        provider: Provider type (openai, deepseek, dashscope, moonshot, volcengine, zai, minimax, ollama, etc.)
        api_base: API base URL
        api_key: API key for authentication
        endpoint: Legacy field, use api_base instead
        priority: Model priority (higher value = higher priority)
        capabilities: List of capability names. Can use predefined constants
                      (CAPABILITY_GENERAL, CAPABILITY_CODE, etc.) or custom strings.
                      Examples: ["general", "code"], ["medical", "legal"], ["custom-task"]
        supports_streaming: Whether the model supports streaming responses
        timeout: Non-streaming request timeout in seconds. None means inherit from routing_config.timeout
        stream_timeout: Streaming inter-chunk timeout in seconds. None means inherit from timeout
        max_retries: Maximum retry attempts
        is_healthy: Whether the model is currently healthy and available
        
        Health-related fields (managed by HealthChecker):
        connection_health: Whether lightweight check (HTTP HEAD) is healthy
        last_health_check: Timestamp of last health check
        consecutive_failures: Count of consecutive failures (for statistics)
        consecutive_successes: Count of consecutive successes (for statistics)
        health_check_enabled: Whether health check is enabled for this model
        unhealthy_reason: Reason why model is unhealthy
    """
    name: str
    instance_id: Optional[str] = None  # Unique instance identifier
    provider: Optional[str] = None  # Provider type (dashscope, moonshot, etc.)
    api_base: Optional[str] = None  # API base URL
    api_key: Optional[str] = None   # API key
    endpoint: Optional[str] = None  # Legacy field, use api_base instead
    priority: int = 1
    weight: int = 1  # Load balance weight (used in weighted strategy)
    capabilities: List[str] = None
    supports_streaming: bool = True
    timeout: Optional[int] = None  # Non-streaming: full response timeout. None means inherit from routing_config.timeout
    stream_timeout: Optional[int] = None  # Streaming: inter-chunk timeout. None means inherit from timeout
    max_retries: int = 3
    is_healthy: bool = True
    
    # Health status fields (managed by HealthChecker)
    connection_health: bool = True  # Lightweight check (HTTP HEAD) health status
    last_health_check: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    health_check_enabled: bool = True
    unhealthy_reason: UnhealthyReason = field(default=UnhealthyReason.NONE)
    
    # Fine-grained lock for thread safety
    _health_lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = [CAPABILITY_GENERAL]  # Default to general capability
        # Support legacy 'endpoint' field by mapping it to 'api_base'
        if self.endpoint and not self.api_base:
            self.api_base = self.endpoint
        # Generate instance_id if not provided
        if not self.instance_id:
            self.instance_id = self._generate_instance_id()
        # Ensure unhealthy_reason is proper enum
        if not isinstance(self.unhealthy_reason, UnhealthyReason):
            self.unhealthy_reason = UnhealthyReason.NONE
    
    def _generate_instance_id(self) -> str:
        """
        Generate instance_id based on name + api_base + api_key (similar to litellm)
        This ensures the same configuration always generates the same instance_id
        """
        parts = [self.name]
        if self.api_base:
            parts.append(self.api_base)
        if self.api_key:
            parts.append(self.api_key)
        
        concat_str = "".join(parts)
        hash_object = hashlib.sha256(concat_str.encode())
        return hash_object.hexdigest()[:16]  # Use first 16 chars for readability


class ModelConfigManager:
    """Manages model configurations"""
    
    def __init__(self, config_path: str = "config/models.yaml", allow_create_default: bool = True):
        """
        Initialize the model configuration manager
        
        Args:
            config_path: Path to configuration file
            allow_create_default: If True, create default config file when it doesn't exist.
                                 If False, use in-memory empty config when file doesn't exist.
                                 This is useful for CLI offline mode to avoid reading default configs.
        """
        self.config_path = config_path
        self.allow_create_default = allow_create_default
        self.models: Dict[str, ModelConfig] = {}  # instance_id -> ModelConfig
        self.model_name_index: Dict[str, List[str]] = {}  # model_name -> [instance_id, ...]
        self.default_model: Optional[str] = None  # model_name or instance_id
        self.default_model_instance_id: Optional[str] = None  # specific instance_id for default
        self.routing_config: RoutingConfig = RoutingConfig()  # Structured routing config
        self._raw_config: Dict[str, Any] = {}  # Raw parsed config dict from YAML

        # Thread lock for in-process concurrency control
        self._thread_lock = threading.Lock()
        
        # Load configuration during initialization
        self.load_config()
        logger.debug(f"ModelConfigManager initialized with {len(self.models)} model instances")
    
    @property
    def runtime_config(self) -> RuntimeConfig:
        """Get runtime configuration"""
        return self.routing_config.runtime

    def get_gateway_config(self) -> Dict[str, Any]:
        """
        Get gateway configuration from YAML config

        Returns:
            Dict containing gateway configuration with keys:
            - remote_access: bool (default: False)
            - port: int (default: 6000)
        """
        gateway = self._raw_config.get('gateway', {})
        remote_access = gateway.get('remote_access', False)
        port = gateway.get('port', 6000)
        # Fallback to defaults when values are invalid types
        if not isinstance(remote_access, bool):
            remote_access = False
        if not isinstance(port, int) or not (1 <= port <= 65535):
            port = 6000
        return {
            'remote_access': remote_access,
            'port': port
        }

    def load_config(self) -> None:
        """
        Load YAML configuration file (initialization scenario)
        
        This method handles the framework initialization scenario:
        1. Try to load configuration from file
        2. If file doesn't exist, create default configuration
        3. Validate configuration using _parse_and_validate_yaml()
        4. Process models using _process_models_config()
        5. Write back missing instance_ids
        6. On failure, use minimal configuration to keep service running
        """
        try:
            yaml_content: Optional[str] = None
            use_default_config = False
            
            # Step 1: Try to read config file
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    yaml_content = f.read()
                logger.debug(f"Read config file: {self.config_path}")
            except FileNotFoundError:
                if self.allow_create_default:
                    logger.warning(f"Config file {self.config_path} not found, attempting to create default config")
                    try:
                        self._create_default_config_file()
                        # Read the newly created file
                        with open(self.config_path, 'r', encoding='utf-8') as f:
                            yaml_content = f.read()
                        logger.info(f"Created and loaded default config: {self.config_path}")
                    except (PermissionError, OSError) as e:
                        if self._is_production_path(self.config_path):
                            raise PermissionError(
                                f"Cannot create config file {self.config_path}: Permission denied. "
                                f"Please create it manually or ensure the service runs with appropriate permissions."
                            ) from e
                        else:
                            logger.warning(f"Cannot create config file {self.config_path}: {e}. Using in-memory default config.")
                            use_default_config = True
                    except Exception as e:
                        logger.error(f"Failed to create config file {self.config_path}: {e}. Using in-memory default config.")
                        use_default_config = True
                else:
                    # CLI offline mode: don't create default config, use in-memory empty config
                    logger.info(f"Config file {self.config_path} not found. Using in-memory empty config (CLI offline mode).")
                    use_default_config = True
            except Exception as e:
                logger.error(f"Failed to read config file {self.config_path}: {e}. Using in-memory default config.")
                use_default_config = True
            
            # Step 2: Parse and validate YAML content
            if use_default_config:
                # Use default configuration directly
                config = self._get_default_config()
                errors = []
                logger.info("Using in-memory default configuration")
            else:
                # Parse and validate YAML content
                config, messages = self._parse_and_validate_yaml(yaml_content, self.config_path)
            
            # Log any errors/warnings from validation
            for msg in messages:
                if msg.level == "warning":
                    logger.warning(msg.message)
                else:
                    logger.error(msg.message)
            
            # Step 3: Handle validation failure
            if config is None:
                logger.error(
                    f"Configuration validation failed for {self.config_path}. "
                    f"Using minimal default configuration."
                )
                self._create_minimal_config(config=None)
                return

            # Step 4: Process model configurations
            self.models, self.model_name_index, models_to_write_back = self._process_models_config(config)
            
            # Step 5: Handle empty models list
            # In CLI offline mode (allow_create_default=False), empty configs are valid
            # In service mode (allow_create_default=True), empty configs should use minimal default
            if not self.models and self.allow_create_default:
                logger.warning(
                    f"No valid models found in {self.config_path}. "
                    f"Using minimal default configuration."
                )
                self._create_minimal_config(config=config)
                return
            
            # Step 6: Write back instance_id if needed (only for initialization)
            if models_to_write_back and os.path.exists(self.config_path):
                try:
                    self._write_back_instance_ids(models_to_write_back)
                except Exception as e:
                    logger.warning(
                        f"Failed to write back instance_id to {self.config_path}: {e}. "
                        f"Configuration will work, but instance_id won't be persisted."
                    )
            
            # Step 7: Parse routing configuration
            routing_dict = config.get('routing', {})
            self.routing_config = self._parse_routing_config(routing_dict)
            self.default_model = self.routing_config.default_model
            self.default_model_instance_id = self.routing_config.default_model_instance_id

            # Step 7.5: Save raw config for gateway config access
            self._raw_config = config

            # Step 8: Set default model if not specified
            if not self.default_model and self.model_name_index:
                self.default_model = self._get_highest_priority_model_name()
                logger.info(f"No default_model specified, using highest priority model: {self.default_model}")
            
            # Step 9: Validate default model exists
            if self.default_model and self.default_model not in self.model_name_index:
                logger.warning(
                    f"Specified default_model '{self.default_model}' not found in models. "
                    f"Using highest priority available model."
                )
                if self.model_name_index:
                    self.default_model = self._get_highest_priority_model_name()
            
            logger.debug(
                f"Configuration loaded: {len(self.models)} model instances, "
                f"{len(self.model_name_index)} unique model names, "
                f"default: {self.default_model}"
            )
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            # Create minimal default configuration
            self._create_minimal_config(config=None)
    
    def _parse_routing_config(self, routing_dict: Dict[str, Any]) -> RoutingConfig:
        """
        Parse routing configuration from dictionary
        
        Args:
            routing_dict: Routing configuration dictionary from YAML
            
        Returns:
            RoutingConfig object with parsed values
        """
        # Parse health_check config
        health_check_dict = routing_dict.get('health_check', {})
        health_check = HealthCheckConfig(
            lightweight_enabled=health_check_dict.get('lightweight_enabled', True),
            lightweight_interval=health_check_dict.get('lightweight_interval', 300),
            actual_request_enabled=health_check_dict.get('actual_request_enabled', False),
            actual_request_interval=health_check_dict.get('actual_request_interval', 1200),
            timeout=health_check_dict.get('timeout', 10)
        )
        
        # Parse retry_policy config
        retry_policy_dict = routing_dict.get('retry_policy', {})
        retry_policy = RetryPolicyConfig(
            max_attempts=retry_policy_dict.get('max_attempts', 3),
            backoff_factor=retry_policy_dict.get('backoff_factor', 2),
            base_delay=retry_policy_dict.get('base_delay', 1),
            max_delay=retry_policy_dict.get('max_delay', 30)
        )
        
        # Parse runtime config
        runtime_dict = routing_dict.get('runtime', {})
        load_balance_dict = runtime_dict.get('load_balance', {})
        options_dict = load_balance_dict.get('options', {})
        
        load_balance_options = LoadBalanceOptionsConfig(
            latency_buffer=options_dict.get('latency_buffer', 0.1),
            latency_window=options_dict.get('latency_window', 10),
            usage_window=options_dict.get('usage_window', 60)
        )
        
        load_balance = LoadBalanceConfig(
            strategy=load_balance_dict.get('strategy', 'weighted'),
            options=load_balance_options
        )
        
        runtime = RuntimeConfig(
            mode=runtime_dict.get('mode', 'default'),
            load_balance=load_balance
        )
        
        # Create RoutingConfig
        return RoutingConfig(
            default_model=routing_dict.get('default_model'),
            default_model_instance_id=routing_dict.get('default_model_instance_id'),
            health_check=health_check,
            retry_policy=retry_policy,
            timeout=routing_dict.get('timeout', DEFAULT_ROUTING_TIMEOUT),
            runtime=runtime
        )
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default empty configuration"""
        return {
            "models": [],
            "routing": {
                "default_model": None,
                "timeout": DEFAULT_ROUTING_TIMEOUT,
                "health_check": {
                    "lightweight_enabled": True,
                    "lightweight_interval": 300,
                    "actual_request_enabled": False,
                    "actual_request_interval": 1200,
                    "timeout": 10
                },
                "retry_policy": {
                    "max_attempts": 3,
                    "backoff_factor": 2,
                    "base_delay": 1,
                    "max_delay": 30
                },
                "runtime": {
                    "mode": "default",
                    "load_balance": {
                        "strategy": "weighted",
                        "options": {
                            "latency_buffer": 0.1,
                            "latency_window": 10,
                            "usage_window": 60
                        }
                    }
                }
            }
        }
    
    def _create_minimal_config(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Create minimal configuration when loading fails

        Args:
            config: Parsed config dict from file, if available. Used to preserve
                    gateway and routing sections so they aren't lost when models
                    list is empty or validation fails.
        """
        logger.warning(
            "No models configured. Service will run in degraded state. "
            "Use 'ai-config model add' to add models."
        )
        self.models = {}  # Empty model dictionary
        self.model_name_index = {}
        self.default_model = None
        self.default_model_instance_id = None

        # Preserve gateway and routing data from parsed config so that
        # get_gateway_config() and routing settings remain accessible
        if config and isinstance(config, dict):
            self._raw_config = {k: v for k, v in config.items()
                                if k in ('gateway', 'routing')}
            # Parse routing config from available data
            routing_dict = config.get('routing', {})
            self.routing_config = self._parse_routing_config(routing_dict)
        else:
            self._raw_config = {}
            self.routing_config = RoutingConfig()  # Default routing config
    
    def _is_production_path(self, path: str) -> bool:
        """Check if path is production path (/etc/sysaiframe/models.yaml)"""
        return path == os.environ.get('SYSAIFRAME_CONFIG_PATH', '/etc/sysaiframe/models.yaml')
    
    def _parse_and_validate_yaml(
        self, 
        yaml_content: str, 
        source: str = "unknown"
    ) -> Tuple[Optional[Dict[str, Any]], List[ValidationMessage]]:
        """
        Parse and validate YAML content (core parsing and validation function)
        
        This is the core function for YAML processing, used by both:
        - load_config(): Framework initialization
        - validate_config_file(): Runtime validation (future)
        
        Args:
            yaml_content: YAML string content
            source: Source description for error messages (e.g., file path)
            
        Returns:
            Tuple of (parsed_config, messages):
            - parsed_config: Parsed configuration dict, or None if parsing failed
            - messages: List of ValidationMessage objects (errors and warnings)
        """
        messages: List[ValidationMessage] = []
        config: Optional[Dict[str, Any]] = None
        
        # Step 1: Parse YAML syntax
        try:
            config = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            error_msg = f"YAML syntax error in {source}"
            if hasattr(e, 'problem_mark'):
                mark = e.problem_mark
                error_msg += f" at line {mark.line + 1}, column {mark.column + 1}"
            if hasattr(e, 'problem'):
                error_msg += f": {e.problem}"
            messages.append(ValidationMessage(level="error", message=error_msg))
            return None, messages
        
        # Step 2: Check if config is None (empty file)
        if config is None:
            messages.append(ValidationMessage(
                level="error",
                message=f"Configuration file {source} is empty. "
                        f"Please refer to models.yaml.example for configuration format."
            ))
            return None, messages
        
        # Step 3: Validate config structure
        if not isinstance(config, dict):
            messages.append(ValidationMessage(
                level="error",
                message=f"Configuration in {source} must be a YAML dictionary/mapping, "
                        f"got {type(config).__name__} instead."
            ))
            return None, messages
        
        # Step 4: Validate 'models' field
        if 'models' not in config:
            messages.append(ValidationMessage(
                level="error",
                message=f"Configuration in {source} missing required 'models' field. "
                        f"Please refer to models.yaml.example for configuration format."
            ))
            return None, messages
        
        models = config.get('models')
        if not isinstance(models, list):
            messages.append(ValidationMessage(
                level="error",
                message=f"'models' field in {source} must be a list, "
                        f"got {type(models).__name__} instead."
            ))
            return None, messages
        
        if len(models) == 0:
            messages.append(ValidationMessage(
                level="warning",
                message=f"'models' list in {source} is empty. "
                        f"At least one model configuration is required."
            ))
            # This is a warning, not a fatal error - we can continue
        
        # Step 5: Validate each model configuration
        seen_instance_ids: Dict[str, int] = {}  # instance_id -> model_index for duplicate detection
        
        for idx, model_data in enumerate(models):
            model_messages = self._validate_model_data(model_data, idx, source)
            messages.extend(model_messages)
            
            # Check for duplicate instance_id (if explicitly provided)
            instance_id = model_data.get('instance_id')
            if instance_id:
                if instance_id in seen_instance_ids:
                    messages.append(ValidationMessage(
                        level="error",
                        message=f"Duplicate instance_id '{instance_id}' found in {source}: "
                                f"model[{seen_instance_ids[instance_id]}] and model[{idx}]. "
                                f"Each instance_id must be unique."
                    ))
                else:
                    seen_instance_ids[instance_id] = idx
        
        # Step 6: Validate routing configuration (optional)
        routing = config.get('routing', {})
        if routing:
            routing_messages = self._validate_routing_config(routing, models, source)
            messages.extend(routing_messages)

        # Step 7: Validate gateway configuration (optional)
        gateway = config.get('gateway')
        if gateway:
            gateway_messages = self._validate_gateway_config(gateway, source)
            messages.extend(gateway_messages)

        return config, messages
    
    def _validate_model_data(
        self, 
        model_data: Any, 
        index: int, 
        source: str
    ) -> List[ValidationMessage]:
        """
        Validate a single model configuration
        
        Args:
            model_data: Model configuration data
            index: Index in the models list
            source: Source description for error messages
            
        Returns:
            List of ValidationMessage objects
        """
        messages: List[ValidationMessage] = []
        model_ref = f"model[{index}] in {source}"
        
        # Check if model_data is a dict
        if not isinstance(model_data, dict):
            messages.append(ValidationMessage(
                level="error",
                message=f"{model_ref}: Expected a dictionary, got {type(model_data).__name__}."
            ))
            return messages
        
        # Check required field: name
        name = model_data.get('name')
        if not name:
            messages.append(ValidationMessage(
                level="error",
                message=f"{model_ref}: Missing required field 'name'."
            ))
        elif not isinstance(name, str):
            messages.append(ValidationMessage(
                level="error",
                message=f"{model_ref}: 'name' must be a string, got {type(name).__name__}."
            ))
        
        # Validate optional fields with type checking
        # priority
        priority = model_data.get('priority')
        if priority is not None:
            if not isinstance(priority, int):
                messages.append(ValidationMessage(
                    level="error",
                    message=f"{model_ref}: 'priority' must be an integer, got {type(priority).__name__}."
                ))
            elif priority < 1:
                messages.append(ValidationMessage(
                    level="error",
                    message=f"{model_ref}: 'priority' must be >= 1, got {priority}."
                ))
            elif priority > 100:
                messages.append(ValidationMessage(
                    level="error",
                    message=f"{model_ref}: 'priority' must be <= 100, got {priority}."
                ))
        
        # weight
        weight = model_data.get('weight')
        if weight is not None:
            if not isinstance(weight, int):
                messages.append(ValidationMessage(
                    level="error",
                    message=f"{model_ref}: 'weight' must be an integer, got {type(weight).__name__}."
                ))
            elif weight < 1:
                messages.append(ValidationMessage(
                    level="error",
                    message=f"{model_ref}: 'weight' must be >= 1, got {weight}."
                ))
            elif weight > 100:
                messages.append(ValidationMessage(
                    level="error",
                    message=f"{model_ref}: 'weight' must be <= 100, got {weight}."
                ))
        
        # capabilities
        capabilities = model_data.get('capabilities')
        if capabilities is not None:
            if not isinstance(capabilities, list):
                messages.append(ValidationMessage(
                    level="error",
                    message=f"{model_ref}: 'capabilities' must be a list, got {type(capabilities).__name__}."
                ))
            elif not all(isinstance(c, str) for c in capabilities):
                messages.append(ValidationMessage(
                    level="error",
                    message=f"{model_ref}: All items in 'capabilities' must be strings."
                ))
        
        # timeout
        timeout = model_data.get('timeout')
        if timeout is not None:
            if not isinstance(timeout, int):
                messages.append(ValidationMessage(
                    level="error",
                    message=f"{model_ref}: 'timeout' must be an integer, got {type(timeout).__name__}."
                ))
            elif timeout < 3:
                messages.append(ValidationMessage(
                    level="error",
                    message=f"{model_ref}: 'timeout' must be >= 3 seconds, got {timeout}."
                ))
            elif timeout > 3600:
                messages.append(ValidationMessage(
                    level="error",
                    message=f"{model_ref}: 'timeout' must be <= 3600 seconds (1 hour), got {timeout}."
                ))

        # stream_timeout
        stream_timeout = model_data.get('stream_timeout')
        if stream_timeout is not None:
            if not isinstance(stream_timeout, int):
                messages.append(ValidationMessage(
                    level="error",
                    message=f"{model_ref}: 'stream_timeout' must be an integer, got {type(stream_timeout).__name__}."
                ))
            elif stream_timeout < 3:
                messages.append(ValidationMessage(
                    level="error",
                    message=f"{model_ref}: 'stream_timeout' must be >= 3 seconds, got {stream_timeout}."
                ))
            elif stream_timeout > 3600:
                messages.append(ValidationMessage(
                    level="error",
                    message=f"{model_ref}: 'stream_timeout' must be <= 3600 seconds (1 hour), got {stream_timeout}."
                ))

        # max_retries
        max_retries = model_data.get('max_retries')
        if max_retries is not None:
            if not isinstance(max_retries, int):
                messages.append(ValidationMessage(
                    level="error",
                    message=f"{model_ref}: 'max_retries' must be an integer, got {type(max_retries).__name__}."
                ))
            elif max_retries < 0:
                messages.append(ValidationMessage(
                    level="error",
                    message=f"{model_ref}: 'max_retries' must be >= 0, got {max_retries}."
                ))
            elif max_retries > 10:
                messages.append(ValidationMessage(
                    level="error",
                    message=f"{model_ref}: 'max_retries' must be <= 10, got {max_retries}."
                ))
        
        # supports_streaming
        supports_streaming = model_data.get('supports_streaming')
        if supports_streaming is not None and not isinstance(supports_streaming, bool):
            messages.append(ValidationMessage(
                level="error",
                message=f"{model_ref}: 'supports_streaming' must be a boolean, got {type(supports_streaming).__name__}."
            ))
        
        # is_healthy
        is_healthy = model_data.get('is_healthy')
        if is_healthy is not None and not isinstance(is_healthy, bool):
            messages.append(ValidationMessage(
                level="error",
                message=f"{model_ref}: 'is_healthy' must be a boolean, got {type(is_healthy).__name__}."
            ))
        
        # Warn about mock API key
        api_key = model_data.get('api_key')
        if api_key == 'sk-mock-key':
            messages.append(ValidationMessage(
                level="warning",
                message=f"{model_ref} (name='{name}'): Using mock API key 'sk-mock-key'. "
                        f"This will cause authentication errors. Please configure a valid API key."
            ))
        
        return messages
    
    def _validate_routing_config(
        self, 
        routing: Dict[str, Any], 
        models: List[Dict[str, Any]], 
        source: str
    ) -> List[ValidationMessage]:
        """
        Validate routing configuration
        
        Args:
            routing: Routing configuration dict
            models: List of model configurations
            source: Source description for error messages
            
        Returns:
            List of ValidationMessage objects
        """
        messages: List[ValidationMessage] = []
        
        # Collect all model names and instance_ids
        model_names = set()
        instance_ids = set()
        for model_data in models:
            if isinstance(model_data, dict):
                name = model_data.get('name')
                if name:
                    model_names.add(name)
                instance_id = model_data.get('instance_id')
                if instance_id:
                    instance_ids.add(instance_id)
        
        # Validate default_model
        default_model = routing.get('default_model')
        if default_model and default_model not in model_names and default_model not in instance_ids:
            messages.append(ValidationMessage(
                level="warning",
                message=f"'routing.default_model' in {source} references "
                        f"'{default_model}' which does not exist in models list. "
                        f"Available models: {list(model_names)}"
            ))
        
        # Validate default_model_instance_id
        default_instance_id = routing.get('default_model_instance_id')
        if default_instance_id and default_instance_id not in instance_ids:
            messages.append(ValidationMessage(
                level="warning",
                message=f"'routing.default_model_instance_id' in {source} references "
                        f"'{default_instance_id}' which does not exist. "
                        f"Available instance_ids: {list(instance_ids)}"
            ))
        
        return messages

    def _validate_gateway_config(
        self,
        gateway: Dict[str, Any],
        source: str
    ) -> List[ValidationMessage]:
        """
        Validate gateway configuration

        Args:
            gateway: Gateway configuration dict
            source: Source description for error messages

        Returns:
            List of ValidationMessage objects
        """
        messages: List[ValidationMessage] = []

        # Validate remote_access (must be boolean if present)
        remote_access = gateway.get('remote_access')
        if remote_access is not None and not isinstance(remote_access, bool):
            messages.append(ValidationMessage(
                level="error",
                message=f"'gateway.remote_access' in {source} must be a boolean (true/false), "
                        f"got {type(remote_access).__name__}."
            ))

        # Validate port (must be integer 1-65535 if present)
        port = gateway.get('port')
        if port is not None:
            if not isinstance(port, int):
                messages.append(ValidationMessage(
                    level="error",
                    message=f"'gateway.port' in {source} must be an integer, got {type(port).__name__}."
                ))
            elif port < 1 or port > 65535:
                messages.append(ValidationMessage(
                    level="error",
                    message=f"'gateway.port' in {source} must be between 1 and 65535, got {port}."
                ))

        return messages

    def _process_single_model(
        self,
        model_data: Dict[str, Any],
        index: int
    ) -> Tuple[Optional[ModelConfig], Optional[str], bool]:
        """
        Process a single model configuration
        
        This method handles the logic for processing a single model:
        - Creates ModelConfig object
        - Detects if instance_id needs to be written back
        - Returns processing results
        
        This method can be used independently for runtime model updates.
        
        Args:
            model_data: Single model configuration dictionary
            index: Index of the model in the models list (for logging/debugging)
            
        Returns:
            Tuple of (model_config, instance_id_to_write_back, has_instance_id):
            - model_config: Created ModelConfig object, or None if processing failed
            - instance_id_to_write_back: instance_id to write back if needed, or None
            - has_instance_id: Whether the original config had instance_id
        """
        try:
            # Check if instance_id is missing
            original_instance_id = model_data.get('instance_id')
            has_instance_id = original_instance_id is not None and original_instance_id != ''
            
            # Create ModelConfig (will auto-generate instance_id if missing)
            model_config = ModelConfig(**model_data)
            
            # Determine if we need to write back instance_id
            instance_id_to_write_back = None
            if not has_instance_id:
                instance_id_to_write_back = model_config.instance_id
                logger.debug(
                    f"Model '{model_config.name}' (index {index}) missing instance_id, "
                    f"generated: {model_config.instance_id}"
                )
            
            logger.debug(
                f"Processed model config: {model_config.name} "
                f"(instance_id={model_config.instance_id}, index={index})"
            )
            
            return model_config, instance_id_to_write_back, has_instance_id
            
        except Exception as e:
            logger.error(f"Failed to process model config at index {index}: {e}")
            return None, None, False
    
    def _process_models_config(
        self, 
        config: Dict[str, Any]
    ) -> Tuple[Dict[str, ModelConfig], Dict[str, List[str]], List[Tuple[int, str]]]:
        """
        Process all model configurations, generate internal data structures
        
        This method handles the framework logic for processing all models:
        - Iterates through all models
        - Calls _process_single_model() for each model
        - Builds models and model_name_index mappings
        - Collects instance_ids that need to be written back
        
        Args:
            config: Validated configuration dict
            
        Returns:
            Tuple of (models, model_name_index, models_to_write_back):
            - models: instance_id -> ModelConfig mapping
            - model_name_index: model_name -> [instance_id, ...] mapping
            - models_to_write_back: List of (index, instance_id) for models needing write-back
        """
        models: Dict[str, ModelConfig] = {}
        model_name_index: Dict[str, List[str]] = {}
        models_to_write_back: List[Tuple[int, str]] = []
        
        for idx, model_data in enumerate(config.get('models', [])):
            # Process single model using the dedicated method
            model_config, instance_id_to_write_back, has_instance_id = self._process_single_model(
                model_data, idx
            )
            
            # Skip if processing failed
            if model_config is None:
                continue
            
            # Record if we need to write back instance_id
            if instance_id_to_write_back:
                models_to_write_back.append((idx, instance_id_to_write_back))
            
            # Use instance_id as key for unique identification
            models[model_config.instance_id] = model_config
            
            # Build model_name_index: model_name -> [instance_id, ...]
            if model_config.name not in model_name_index:
                model_name_index[model_config.name] = []
            model_name_index[model_config.name].append(model_config.instance_id)
        
        return models, model_name_index, models_to_write_back
    
    def validate_config_file(self, file_path: str) -> Tuple[bool, List[str], Optional[Dict[str, Any]]]:
        """
        Validate a configuration file without modifying internal state
        
        This method is intended for runtime validation of user-provided config files.
        It validates the file but does not apply the configuration.
        
        Args:
            file_path: Path to the YAML configuration file
            
        Returns:
            Tuple of (is_valid, errors, parsed_config):
            - is_valid: True if validation passed (no fatal errors)
            - errors: List of error/warning messages
            - parsed_config: Parsed configuration dict (if valid)
        """
        errors: List[str] = []
        
        # Check if file exists
        if not os.path.exists(file_path):
            errors.append(f"Configuration file not found: {file_path}")
            return False, errors, None
        
        # Check if file is readable
        if not os.access(file_path, os.R_OK):
            errors.append(f"Configuration file is not readable: {file_path}")
            return False, errors, None
        
        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                yaml_content = f.read()
        except Exception as e:
            errors.append(f"Failed to read configuration file {file_path}: {e}")
            return False, errors, None
        
        # Parse and validate
        config, validation_messages = self._parse_and_validate_yaml(yaml_content, file_path)
        
        # Separate errors and warnings
        validation_errors = [msg.message for msg in validation_messages if msg.level == "error"]
        validation_warnings = [msg.message for msg in validation_messages if msg.level == "warning"]
        errors.extend(validation_errors)
        
        # Add warnings to errors list for backward compatibility (or return separately)
        for warning in validation_warnings:
            errors.append(f"WARNING: {warning}")
        
        # Determine if valid (no fatal errors - warnings are OK)
        is_valid = config is not None and len(validation_errors) == 0
        
        return is_valid, errors, config
    
    def _write_back_instance_ids(self, models_to_write_back: List[Tuple[int, str]]) -> None:
        """
        Write back instance_id to YAML file for models that are missing it
        Uses ruamel.yaml to preserve comments and formatting.
        
        Args:
            models_to_write_back: List of (model_index, instance_id) tuples
        """
        if not models_to_write_back:
            return
        
        if not os.path.exists(self.config_path):
            logger.warning(f"Config file {self.config_path} does not exist, cannot write back instance_id")
            return
        
        # Check if file is writable
        if not os.access(self.config_path, os.W_OK):
            logger.warning(
                f"Config file {self.config_path} is not writable, "
                f"cannot write back instance_id"
            )
            return
        
        try:
            # Configure ruamel.yaml to preserve comments and formatting
            yaml_loader = YAML()
            yaml_loader.preserve_quotes = True
            yaml_loader.width = 4096  # Prevent line wrapping
            yaml_loader.indent(mapping=2, sequence=4, offset=2)  # Preserve indentation
            
            # Read the file
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml_loader.load(f)
            
            if not data or 'models' not in data:
                logger.warning("Config file structure invalid, cannot write back instance_id")
                return
            
            # Add instance_id to each model that needs it
            models = data['models']
            for model_idx, instance_id in models_to_write_back:
                if 0 <= model_idx < len(models):
                    model = models[model_idx]
                    # Only add if it doesn't already exist
                    if 'instance_id' not in model or not model.get('instance_id'):
                        # Simply add the instance_id field
                        # ruamel.yaml will preserve the order as much as possible
                        model['instance_id'] = instance_id
            
            # Atomic write: write to temporary file first, then rename
            temp_path = f"{self.config_path}.tmp"
            try:
                # Write to temporary file
                with open(temp_path, 'w', encoding='utf-8') as f:
                    yaml_loader.dump(data, f)
                    # Ensure data is flushed to disk
                    f.flush()
                    os.fsync(f.fileno())
                
                # Atomically replace original file with temporary file
                os.replace(temp_path, self.config_path)
                
                # Ensure directory entry is synced
                try:
                    dir_fd = os.open(os.path.dirname(self.config_path), os.O_RDONLY)
                    try:
                        os.fsync(dir_fd)
                    finally:
                        os.close(dir_fd)
                except (OSError, IOError):
                    pass
                
                logger.info(
                    f"Successfully wrote back {len(models_to_write_back)} instance_id(s) "
                    f"to {self.config_path}"
                )
            except Exception as e:
                # Clean up temporary file on error
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            logger.error(f"Error writing back instance_id: {e}")
            raise
    
    def _create_default_config_file(self) -> None:
        """Create default configuration file if it doesn't exist"""
        # Check if file already exists (should not happen, but double-check)
        if os.path.exists(self.config_path):
            logger.warning(f"Config file {self.config_path} already exists, skipping creation")
            return
        
        # Check directory exists, create if needed
        config_dir = os.path.dirname(self.config_path)
        if config_dir and not os.path.exists(config_dir):
            try:
                os.makedirs(config_dir, mode=0o755, exist_ok=True)
                logger.info(f"Created config directory: {config_dir}")
            except (PermissionError, OSError) as e:
                logger.error(f"Cannot create config directory {config_dir}: {e}")
                raise
        
        # Get default configuration
        default_config = self._get_default_config()
        
        # Write to file with comments
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                # Write header comments
                f.write("# SysAIFrame Configuration File\n")
                f.write("# \n")
                f.write("# This file is empty on initial startup. Use 'ai-config model add' to add models.\n")
                f.write("# \n")
                f.write("# If no models are configured, the service will run in degraded state and return\n")
                f.write("# appropriate errors for chat completion requests.\n")
                f.write("# \n")
                f.write("# Example: Add a model using CLI\n")
                f.write("#   ai-config model add my-model \\\n")
                f.write("#     --api https://api.example.com/v1 \\\n")
                f.write("#     --api_key your-api-key \\\n")
                f.write("#     --provider openai_like\n")
                f.write("# \n")
                f.write("# See models.yaml.example for more configuration examples.\n")
                f.write("#\n\n")
                # Write configuration
                yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            os.chmod(self.config_path, 0o644)
            logger.info(
                f"Created empty configuration file: {self.config_path}\n"
                f"ℹ️  No models configured. Use 'ai-config model add' to add models.\n"
                f"ℹ️  Service will run in degraded state until models are added."
            )
        except (PermissionError, OSError) as e:
            logger.error(f"Cannot create config file {self.config_path}: {e}")
            raise
    
    def get_available_models(self) -> List[str]:
        """Get list of available model names (unique names, not instances)"""
        return list(self.model_name_index.keys())
    
    def get_model_config(self, identifier: str) -> Optional[ModelConfig]:
        """
        Get model configuration by identifier
        
        Supports multiple formats:
        1. instance_id: Direct instance ID lookup
        2. model_name: Returns best instance (healthy + highest priority)
        3. model_name:instance_id: Specific instance selection
        
        Args:
            identifier: Model identifier (name, instance_id, or name:instance_id)
            
        Returns:
            ModelConfig or None if not found
        """
        # Check if it's a specific instance_id
        if identifier in self.models:
            return self.models[identifier]
        
        # Check if it's model_name:instance_id format
        if ':' in identifier:
            parts = identifier.split(':', 1)
            if len(parts) == 2:
                model_name, instance_id = parts
                if instance_id in self.models:
                    config = self.models[instance_id]
                    if config.name == model_name:
                        return config
        
        # Check if it's a model_name (return best instance)
        if identifier in self.model_name_index:
            return self.select_best_instance(identifier)
        
        return None
    
    def get_models_by_name(self, model_name: str) -> List[ModelConfig]:
        """
        Get all model instances with the same name
        
        Args:
            model_name: The model name
            
        Returns:
            List of ModelConfig objects with the given name
        """
        if model_name not in self.model_name_index:
            return []
        
        instances = []
        for instance_id in self.model_name_index[model_name]:
            if instance_id in self.models:
                instances.append(self.models[instance_id])
        return instances
    
    def get_model_by_instance_id(self, instance_id: str) -> Optional[ModelConfig]:
        """
        Get model configuration by instance_id
        
        Args:
            instance_id: The unique instance identifier
            
        Returns:
            ModelConfig or None if not found
        """
        return self.models.get(instance_id)
    
    def select_best_instance(self, model_name: str) -> Optional[ModelConfig]:
        """
        Select the best instance for a given model name
        
        Selection criteria (in order):
        1. is_healthy (True first)
        2. priority (higher first)
        
        Args:
            model_name: The model name
            
        Returns:
            Best ModelConfig instance or None if no instances found
        """
        instances = self.get_models_by_name(model_name)
        if not instances:
            return None
        
        # Sort by is_healthy (True first), then by priority (higher first)
        instances.sort(key=lambda m: (m.is_healthy, m.priority), reverse=True)
        return instances[0]
    
    def get_default_model(self) -> Optional[str]:
        """Get default model name"""
        return self.default_model
    
    def get_routing_config(self) -> Dict[str, Any]:
        """Get routing configuration"""
        return self.routing_config.copy()
    
    def reload_config(self) -> bool:
        """Reload configuration from file"""
        try:
            self.load_config()
            logger.info("Configuration reloaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            return False
    
    def set_default_model(
        self,
        model_name: str,
        instance_id: Optional[str] = None,
        persist: bool = True,
        require_file_lock: bool = True
    ) -> 'OperationResult':
        """
        Set default model in configuration
        
        Args:
            model_name: Model name to set as default
            instance_id: Optional specific instance ID
            persist: Whether to persist to file
            require_file_lock: Whether to acquire file lock (False for D-Bus calls)
            
        Returns:
            OperationResult indicating success or failure
        """
        from sysai_framework.core.status_codes import (
            OperationResult, SUCCESS, MODEL_NOT_FOUND,
            VALIDATION_ERROR, CONFIG_WRITE_FAILED, INTERNAL_ERROR
        )
        
        try:
            # Validate model name exists
            if model_name not in self.model_name_index:
                return OperationResult.error_result(
                    MODEL_NOT_FOUND,
                    details={
                        "model": model_name,
                        "available_models": list(self.model_name_index.keys())
                    }
                )
            
            # If instance_id is specified, validate it exists
            if instance_id:
                if instance_id not in self.models:
                    return OperationResult.error_result(
                        VALIDATION_ERROR,
                        details={
                            "message": f"Instance ID '{instance_id}' not found",
                            "available_instances": list(self.models.keys())
                        }
                    )
                
                # Validate instance belongs to the specified model
                model_config = self.models[instance_id]
                if model_config.name != model_name:
                    return OperationResult.error_result(
                        VALIDATION_ERROR,
                        details={
                            "message": f"Instance '{instance_id}' belongs to model '{model_config.name}', not '{model_name}'",
                            "specified_model": model_name,
                            "actual_model": model_config.name,
                            "instance_id": instance_id
                        }
                    )
            
            # Update in-memory configuration
            with self._config_lock(require_file_lock=require_file_lock):
                old_default = self.default_model
                old_instance = self.default_model_instance_id
                
                self.default_model = model_name
                self.default_model_instance_id = instance_id
                
                logger.info(
                    f"Set default model to '{model_name}'"
                    + (f" (instance_id={instance_id})" if instance_id else "")
                )
                
                # Persist to file if requested
                if persist:
                    try:
                        self._persist_default_model()
                        return OperationResult.success_result(
                            data={
                                "default_model": model_name,
                                "default_model_instance_id": instance_id,
                                "previous_default_model": old_default,
                                "previous_default_instance_id": old_instance
                            },
                            details={
                                "message": f"Default model set to '{model_name}'"
                                          + (f" (instance_id={instance_id})" if instance_id else "")
                            }
                        )
                    except Exception as e:
                        # Revert in-memory changes
                        self.default_model = old_default
                        self.default_model_instance_id = old_instance
                        logger.error(f"Failed to persist default model: {e}")
                        return OperationResult.error_result(
                            CONFIG_WRITE_FAILED,
                            details={
                                "details": f"Failed to persist default model: {str(e)}",
                                "exception": str(e)
                            }
                        )
                else:
                    return OperationResult.success_result(
                        data={
                            "default_model": model_name,
                            "default_model_instance_id": instance_id
                        },
                        details={
                            "message": f"Default model set to '{model_name}' (in-memory only)"
                                      + (f" (instance_id={instance_id})" if instance_id else "")
                        }
                    )
                    
        except Exception as e:
            logger.error(f"Failed to set default model: {e}")
            return OperationResult.error_result(
                INTERNAL_ERROR,
                details={
                    "details": f"Failed to set default model: {str(e)}",
                    "exception": str(e)
                }
            )
    
    # File lock configuration
    _LOCK_TIMEOUT = 10  # seconds
    _LOCK_RETRY_INTERVAL = 0.1  # seconds
    _ZOMBIE_LOCK_MAX_AGE = 60  # seconds - consider lock file older than this as zombie
    
    def _is_zombie_lock(self, lock_path: str) -> bool:
        """
        Check if lock file is a zombie (not actually held by any process)
        
        Args:
            lock_path: Path to lock file
            
        Returns:
            True if lock appears to be zombie, False otherwise
        """
        if not os.path.exists(lock_path):
            return False
        
        try:
            # Check lock file age
            lock_age = time.time() - os.path.getmtime(lock_path)
            if lock_age > self._ZOMBIE_LOCK_MAX_AGE:
                # Lock file is old, likely a zombie
                logger.warning(f"Found old lock file {lock_path} (age: {lock_age:.1f}s), attempting cleanup")
                return True
            
            # Try to open and lock the file in non-blocking mode
            # If we can lock it, it means no process is holding it (zombie)
            test_fd = os.open(lock_path, os.O_RDWR)
            try:
                fcntl.flock(test_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # If we got here, the lock is not held - it's a zombie
                fcntl.flock(test_fd, fcntl.LOCK_UN)
                os.close(test_fd)
                logger.warning(f"Lock file {lock_path} is not held by any process, cleaning up")
                return True
            except BlockingIOError:
                # Lock is actually held by another process
                os.close(test_fd)
                return False
        except (OSError, IOError) as e:
            logger.debug(f"Error checking zombie lock {lock_path}: {e}")
            return False
    
    def _cleanup_zombie_lock(self, lock_path: str) -> bool:
        """
        Attempt to clean up a zombie lock file
        
        Args:
            lock_path: Path to lock file
            
        Returns:
            True if cleanup succeeded, False otherwise
        """
        try:
            if os.path.exists(lock_path):
                os.unlink(lock_path)
                logger.info(f"Cleaned up zombie lock file: {lock_path}")
                return True
        except OSError as e:
            logger.warning(f"Failed to cleanup zombie lock {lock_path}: {e}")
        return False
    
    @contextmanager
    def _file_lock(self, timeout: int = None, require_file_lock: bool = True):
        """
        Context manager for file locking to prevent concurrent writes
        
        Args:
            timeout: Lock timeout in seconds (default: _LOCK_TIMEOUT)
            require_file_lock: If False, skip file lock (for in-process only operations)
        """
        if timeout is None:
            timeout = self._LOCK_TIMEOUT
        
        lock_path = f"{self.config_path}.lock"
        lock_fd = None
        start_time = time.time()
        
        # If file lock is not required (in-process only), skip file locking
        if not require_file_lock:
            yield
            return
        
        try:
            while True:
                # Check for zombie lock before attempting to acquire
                if self._is_zombie_lock(lock_path):
                    self._cleanup_zombie_lock(lock_path)
                
                try:
                    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except (BlockingIOError, OSError) as e:
                    if lock_fd is not None:
                        os.close(lock_fd)
                        lock_fd = None
                    
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        # Provide detailed error message
                        error_msg = (
                            f"Failed to acquire lock on {self.config_path} "
                            f"after {timeout} seconds.\n"
                            f"Possible causes:\n"
                            f"  1. Another process is modifying the configuration file\n"
                            f"  2. A stale lock file exists: {lock_path}\n"
                            f"  3. The SysAIFrame service is running and holding the lock\n"
                            f"\n"
                            f"Solutions:\n"
                            f"  1. Wait for the other operation to complete\n"
                            f"  2. If service is running, use D-Bus (default) instead of --offline mode\n"
                            f"  3. Manually remove stale lock: rm -f {lock_path}\n"
                            f"  4. Restart the service: systemctl restart sysaiframe"
                        )
                        raise TimeoutError(error_msg)
                    
                    time.sleep(self._LOCK_RETRY_INTERVAL)
            
            yield
            
        finally:
            if lock_fd is not None:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                    os.close(lock_fd)
                except OSError:
                    pass
            
            # Clean up lock file
            try:
                if os.path.exists(lock_path):
                    os.unlink(lock_path)
            except OSError:
                pass
    
    @contextmanager
    def _config_lock(self, require_file_lock: bool = True, timeout: int = None):
        """
        Combined thread lock + file lock context manager
        
        This provides:
        - Thread lock: For in-process concurrency (service process with multiple D-Bus requests)
        - File lock: For cross-process concurrency (CLI offline mode vs service process)
        
        Args:
            require_file_lock: If True, acquire file lock (for cross-process protection)
                             If False, only use thread lock (for in-process only)
            timeout: File lock timeout in seconds (default: _LOCK_TIMEOUT)
        """
        # Always acquire thread lock first (for in-process protection)
        self._thread_lock.acquire()
        try:
            # Then acquire file lock if required (for cross-process protection)
            with self._file_lock(timeout=timeout, require_file_lock=require_file_lock):
                yield
        finally:
            # Release thread lock
            self._thread_lock.release()
    
    def add_model(
        self, 
        model_data: Dict[str, Any], 
        persist: bool = True,
        force: bool = False,
        require_file_lock: bool = True,
        set_as_default: bool = False
    ) -> 'OperationResult':
        """
        Add a new model configuration
        
        This method:
        1. Validates the model data
        2. Creates a ModelConfig object
        3. Adds to in-memory configuration
        4. Optionally persists to configuration file (with file locking)
        5. Optionally sets the model as default
        
        Args:
            model_data: Model configuration dictionary with fields:
                - name (required): Model name
                - api_base (required): API base URL
                - api_key: API key (required for cloud providers)
                - provider: Provider type (default: openai_like)
                - instance_id: Unique instance ID (auto-generated if not provided)
                - priority: Model priority (default: 1)
                - capabilities: List of capabilities (default: ["general"])
                - timeout: Per-model timeout in seconds (default: None, inherit from routing timeout)
                - max_retries: Maximum retry attempts (default: 3)
                - supports_streaming: Whether streaming is supported (default: True)
            persist: Whether to persist changes to config file
            force: Whether to overwrite existing model with same instance_id
            set_as_default: Whether to set this model as the default model
            
        Returns:
            OperationResult: Contains status, data (ModelConfig), and details
        """
        from sysai_framework.core.status_codes import (
            OperationResult, SUCCESS, CREATED, MODEL_ALREADY_EXISTS,
            MODEL_INVALID, VALIDATION_ERROR, CONFIG_LOCKED, CONFIG_WRITE_FAILED
        )
        
        try:
            # Step 1: Validate model data using comprehensive validation
            validation_messages = self._validate_model_data(model_data, 0, "add_model")
            
            # Check for validation errors
            error_messages = [msg for msg in validation_messages if msg.level == "error"]
            if error_messages:
                error_details = "; ".join([msg.message for msg in error_messages])
                return OperationResult.error_result(
                    VALIDATION_ERROR,
                    details={"details": error_details}
                )
            
            # Log warnings if any
            warning_messages = [msg for msg in validation_messages if msg.level == "warning"]
            for warning in warning_messages:
                logger.warning(warning.message)
            
            # Step 2: Check for duplicate instance_id
            instance_id = model_data.get('instance_id')
            existing_model = None
            if instance_id and instance_id in self.models:
                if force:
                    existing_model = self.models[instance_id]
                    logger.info(f"Force overwriting existing model: {instance_id}")
                else:
                    return OperationResult.error_result(
                        MODEL_ALREADY_EXISTS,
                        details={"instance_id": instance_id}
                    )
            
            # Step 3: Create ModelConfig object
            model_config, generated_id, _ = self._process_single_model(
                model_data, 
                index=len(self.models)
            )
            
            if model_config is None:
                return OperationResult.error_result(
                    MODEL_INVALID,
                    details={"details": "Failed to create model configuration"}
                )
            
            # Step 4: Check for duplicate generated instance_id (unless forcing)
            if not force and model_config.instance_id in self.models:
                return OperationResult.error_result(
                    MODEL_ALREADY_EXISTS,
                    details={"instance_id": model_config.instance_id}
                )
            
            # Step 5: Remove existing model if forcing
            if force and existing_model:
                self._remove_model_from_memory(existing_model.instance_id)
            
            # Step 6: Add to in-memory configuration
            self.models[model_config.instance_id] = model_config
            
            if model_config.name not in self.model_name_index:
                self.model_name_index[model_config.name] = []
            if model_config.instance_id not in self.model_name_index[model_config.name]:
                self.model_name_index[model_config.name].append(model_config.instance_id)
            
            # Step 7: Persist to file if requested (with combined thread + file locking)
            if persist:
                try:
                    # Use combined lock: thread lock for in-process, file lock for cross-process
                    with self._config_lock(require_file_lock=require_file_lock):
                        self._persist_add_model(
                            model_data, 
                            model_config.instance_id,
                            force=force
                        )
                        
                        # Step 8: Set as default model if requested
                        if set_as_default:
                            self.default_model = model_config.name
                            self.default_model_instance_id = model_config.instance_id
                            self._persist_default_model()
                            logger.info(
                                f"Set model '{model_config.name}' (instance_id={model_config.instance_id}) as default"
                            )
                except TimeoutError as e:
                    # Rollback in-memory changes
                    self._remove_model_from_memory(model_config.instance_id)
                    return OperationResult.error_result(
                        CONFIG_LOCKED,
                        details={"details": str(e)}
                    )
                except Exception as e:
                    # Rollback in-memory changes
                    self._remove_model_from_memory(model_config.instance_id)
                    return OperationResult.error_result(
                        CONFIG_WRITE_FAILED,
                        details={"details": str(e)}
                    )
            
            # If set_as_default but not persisting, still update in-memory
            if set_as_default and not persist:
                self.default_model = model_config.name
                self.default_model_instance_id = model_config.instance_id
                logger.info(
                    f"Set model '{model_config.name}' (instance_id={model_config.instance_id}) as default (in-memory only)"
                )
            
            logger.info(
                f"Added model: {model_config.name} "
                f"(instance_id={model_config.instance_id})"
            )

            # Re-evaluate default_model if not set
            if not set_as_default and not self.default_model:
                self._update_default_model_if_needed()
            
            # Return success with CREATED status if new, or SUCCESS if overwritten
            status_code = CREATED if not force else SUCCESS
            return OperationResult.success_result(
                data=model_config,
                status=status_code
            )
            
        except Exception as e:
            logger.error(f"Failed to add model: {e}")
            from sysai_framework.core.status_codes import INTERNAL_ERROR
            return OperationResult.error_result(
                INTERNAL_ERROR,
                details={"details": str(e)}
            )
    
    def _remove_model_from_memory(self, instance_id: str) -> bool:
        """
        Remove a model from in-memory configuration
        
        Args:
            instance_id: Instance ID of the model to remove
            
        Returns:
            bool: True if the removed model was the default model
        """
        if instance_id not in self.models:
            return False
        
        model = self.models[instance_id]
        is_default = False
        
        # Check if this is the default model
        if self.default_model_instance_id == instance_id:
            # Case 1: Specific instance is the default
            is_default = True
        elif self.default_model == model.name:
            # Case 2: Model name is the default
            is_default = True
        
        # Remove from models
        del self.models[instance_id]
        
        # Update name index
        if model.name in self.model_name_index:
            if instance_id in self.model_name_index[model.name]:
                self.model_name_index[model.name].remove(instance_id)
            if not self.model_name_index[model.name]:
                del self.model_name_index[model.name]
        
        # Clear default model settings if needed
        if is_default:
            self.default_model = None
            self.default_model_instance_id = None
            logger.info(f"Cleared default model settings after removing {instance_id}")
            self._update_default_model_if_needed()
        
        return is_default
    
    def _persist_add_model(
        self, 
        model_data: Dict[str, Any],
        instance_id: str,
        force: bool = False
    ) -> None:
        """
        Persist a new model to the configuration file
        
        Args:
            model_data: Model configuration dictionary
            instance_id: Generated or provided instance_id
            force: Whether to overwrite existing model with same instance_id
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        yaml_obj = YAML()
        yaml_obj.preserve_quotes = True
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml_obj.load(f)
        
        if config is None:
            config = CommentedMap()
        
        if 'models' not in config:
            config['models'] = CommentedSeq()
        
        # Initialize routing section if it doesn't exist
        if 'routing' not in config:
            config['routing'] = CommentedMap()
            # Initialize timeout with current routing_config value (default is 60)
            config['routing']['timeout'] = int(self.routing_config.timeout)
        
        # If routing section exists but timeout is missing, initialize it
        elif 'timeout' not in config['routing']:
            config['routing']['timeout'] = int(self.routing_config.timeout)
        
        # If force, remove existing model with same instance_id
        if force:
            models = config['models']
            for i in range(len(models) - 1, -1, -1):
                if models[i].get('instance_id') == instance_id:
                    del models[i]
        
        # Create new model entry
        new_model = CommentedMap()
        
        # Add fields in order
        field_order = [
            'name', 'instance_id', 'provider', 'api_base', 'api_key',
            'priority', 'capabilities', 'supports_streaming',
            'timeout', 'max_retries'
            # Note: 'is_healthy' is runtime state managed by HealthChecker,
            # should not be persisted to config file
        ]
        
        # Include instance_id in persisted data
        model_data_with_id = dict(model_data)
        model_data_with_id['instance_id'] = instance_id
        
        for field in field_order:
            if field in model_data_with_id and model_data_with_id[field] is not None:
                value = model_data_with_id[field]
                if field == 'capabilities' and isinstance(value, list):
                    new_model[field] = CommentedSeq(value)
                else:
                    new_model[field] = value
        
        config['models'].append(new_model)
        
        # Atomic write: write to temporary file first, then rename
        # This ensures file integrity even if write fails
        temp_path = f"{self.config_path}.tmp"
        try:
            # Write to temporary file (still within lock)
            with open(temp_path, 'w', encoding='utf-8') as f:
                yaml_obj.dump(config, f)
                # Ensure data is flushed to disk
                f.flush()
                os.fsync(f.fileno())
            
            # Atomically replace original file with temporary file
            # This operation is atomic on most filesystems
            os.replace(temp_path, self.config_path)
            
            # Ensure directory entry is synced (important for data integrity)
            try:
                dir_fd = os.open(os.path.dirname(self.config_path), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except (OSError, IOError):
                # If directory sync fails, it's not critical
                pass
                
        except Exception as e:
            # Clean up temporary file on error
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except OSError:
                pass
            raise
    
    # Fields that are not allowed to be updated via update_model()
    IMMUTABLE_FIELDS = {'name', 'instance_id', 'api_key', 'api_base', 'endpoint'}

    def update_model(
        self,
        instance_id: str,
        updates: Dict[str, Any],
        persist: bool = True,
        require_file_lock: bool = True
    ) -> 'OperationResult':
        """
        Update model configuration (partial update / patch).

        Args:
            instance_id: Instance ID of the model to update.
            updates: Dictionary of fields to update. Only mutable fields
                     (priority, capabilities, timeout, max_retries,
                      provider, supports_streaming) are allowed.
            persist: Whether to persist changes to config file.
            require_file_lock: Whether to acquire file lock before persisting.

        Returns:
            OperationResult with status and updated model data.
        """
        from sysai_framework.core.status_codes import (
            OperationResult, UPDATED, NO_CHANGE, MODEL_NOT_FOUND,
            VALIDATION_ERROR, CONFIG_LOCKED, CONFIG_WRITE_FAILED,
            INTERNAL_ERROR
        )

        try:
            # Step 1: Check model exists
            if instance_id not in self.models:
                return OperationResult.error_result(
                    MODEL_NOT_FOUND,
                    details={"model": instance_id}
                )

            # Step 2: Reject immutable fields
            for field in self.IMMUTABLE_FIELDS:
                if field in updates:
                    return OperationResult.error_result(
                        VALIDATION_ERROR,
                        details={"details": f"Field '{field}' is not updatable"}
                    )

            # Step 3: Filter out None values (not provided by user)
            actual_updates = {k: v for k, v in updates.items() if v is not None}
            if not actual_updates:
                return OperationResult(
                    status=NO_CHANGE,
                    details={"_formatted_message": "No fields to update (all values are unchanged)"}
                )

            # Step 4: Validate update values
            model = self.models[instance_id]
            validation_errors = self._validate_update_fields(actual_updates)
            if validation_errors:
                return OperationResult.error_result(
                    VALIDATION_ERROR,
                    details={"details": "; ".join(validation_errors)}
                )

            # Step 5: Detect actual changes
            changes = {}
            field_mapping = {
                'supports_streaming': 'supports_streaming',
            }
            for field, new_value in actual_updates.items():
                current_value = getattr(model, field, None)
                if field == 'capabilities' and isinstance(current_value, list):
                    if set(current_value) != set(new_value):
                        changes[field] = (current_value, new_value)
                elif current_value != new_value:
                    changes[field] = (current_value, new_value)

            if not changes:
                return OperationResult(
                    status=NO_CHANGE,
                    details={"_formatted_message": "No changes needed (all values are the same)"}
                )

            # Step 6: Apply changes to in-memory model
            for field, (_, new_value) in changes.items():
                setattr(model, field, new_value)

            # Step 7: Persist if requested
            if persist:
                try:
                    with self._config_lock(require_file_lock=require_file_lock):
                        self._persist_update_model(instance_id, changes)
                except Exception as e:
                    logger.error(f"Failed to persist model update: {e}")
                    # Reload from file to restore consistency
                    try:
                        self.load_config()
                    except Exception:
                        pass
                    return OperationResult.error_result(
                        CONFIG_WRITE_FAILED,
                        details={"details": str(e)}
                    )

            # Build result with updated model data
            model_dict = {
                'name': model.name,
                'instance_id': model.instance_id,
                'provider': model.provider,
                'api_base': model.api_base,
                'api_key': '***' if model.api_key else None,
                'priority': model.priority,
                'capabilities': model.capabilities,
                'supports_streaming': model.supports_streaming,
                'timeout': model.timeout,
                'stream_timeout': model.stream_timeout,
                'max_retries': model.max_retries,
                'is_healthy': model.is_healthy,
            }

            changed_fields = list(changes.keys())
            return OperationResult(
                status=UPDATED,
                details={
                    "_formatted_message": f"Model '{model.name}' updated successfully (fields: {', '.join(changed_fields)})",
                    "instance_id": model.instance_id,
                    "updated_fields": changed_fields,
                    "model": model_dict,
                }
            )

        except Exception as e:
            logger.error(f"Failed to update model: {e}")
            return OperationResult.error_result(
                INTERNAL_ERROR,
                details={"details": str(e)}
            )

    def _validate_update_fields(self, updates: Dict[str, Any]) -> List[str]:
        """
        Validate field values for model update.

        Args:
            updates: Dictionary of fields to validate.

        Returns:
            List of error messages (empty if valid).
        """
        errors = []

        if 'priority' in updates:
            val = updates['priority']
            if not isinstance(val, int) or val < 1 or val > 100:
                errors.append("Priority must be an integer between 1 and 100")

        if 'timeout' in updates:
            val = updates['timeout']
            if val is None:
                pass  # None means inherit from routing timeout
            elif not isinstance(val, int) or val < 1 or val > 3600:
                errors.append("Timeout must be None (inherit) or an integer between 1 and 3600")

        if 'max_retries' in updates:
            val = updates['max_retries']
            if not isinstance(val, int) or val < 0 or val > 10:
                errors.append("Max retries must be an integer between 0 and 10")

        if 'provider' in updates:
            val = updates['provider']
            if val not in SUPPORTED_PROVIDERS:
                errors.append(f"Provider must be one of: {', '.join(sorted(SUPPORTED_PROVIDERS))}")

        if 'capabilities' in updates:
            val = updates['capabilities']
            if not isinstance(val, list) or len(val) == 0:
                errors.append("Capabilities must be a non-empty list")

        if 'supports_streaming' in updates:
            val = updates['supports_streaming']
            if not isinstance(val, bool):
                errors.append("Streaming must be true or false")

        return errors

    def _persist_update_model(
        self,
        instance_id: str,
        changes: Dict[str, Any]
    ) -> None:
        """
        Persist model updates to the configuration file.

        Args:
            instance_id: Instance ID of the model to update.
            changes: Dictionary of {field: (old_value, new_value)}.
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        yaml_obj = YAML()
        yaml_obj.preserve_quotes = True

        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml_obj.load(f)

        if config is None or 'models' not in config:
            raise ValueError("Invalid configuration file: no models section")

        # Find and update the model entry
        models = config['models']
        found = False
        for model_entry in models:
            if model_entry.get('instance_id') == instance_id:
                # Apply only changed fields
                for field, (_, new_value) in changes.items():
                    if field == 'capabilities' and isinstance(new_value, list):
                        model_entry[field] = CommentedSeq(new_value)
                    else:
                        model_entry[field] = new_value
                found = True
                break

        if not found:
            raise ValueError(f"Model with instance_id '{instance_id}' not found in config file")

        # Atomic write
        temp_path = f"{self.config_path}.tmp"
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                yaml_obj.dump(config, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self.config_path)
            try:
                dir_fd = os.open(os.path.dirname(self.config_path), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except (OSError, IOError):
                pass
        except Exception:
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except OSError:
                pass
            raise

    def _persist_default_model(self) -> None:
        """
        Persist default model settings to configuration file

        Updates routing.default_model and routing.default_model_instance_id
        in the YAML configuration file using atomic write.
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        yaml_obj = YAML()
        yaml_obj.preserve_quotes = True
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml_obj.load(f)
        
        if config is None:
            config = CommentedMap()
        
        # Ensure routing section exists
        if 'routing' not in config:
            config['routing'] = CommentedMap()
        
        # Update default model settings
        # Ensure values are standard Python types (str), not YAML objects
        if self.default_model:
            config['routing']['default_model'] = str(self.default_model)
        else:
            # If default_model is None, remove the key
            if 'default_model' in config['routing']:
                del config['routing']['default_model']
        
        if self.default_model_instance_id:
            config['routing']['default_model_instance_id'] = str(self.default_model_instance_id)
        else:
            # If default_model_instance_id is None, remove the key
            if 'default_model_instance_id' in config['routing']:
                del config['routing']['default_model_instance_id']
        
        # Update runtime configuration
        runtime_config = self.routing_config.runtime
        if 'runtime' not in config['routing']:
            config['routing']['runtime'] = CommentedMap()
        
        config['routing']['runtime']['mode'] = runtime_config.mode
        
        # Update load_balance config
        if 'load_balance' not in config['routing']['runtime']:
            config['routing']['runtime']['load_balance'] = CommentedMap()
        
        config['routing']['runtime']['load_balance']['strategy'] = runtime_config.load_balance.strategy
        
        # Update options
        if 'options' not in config['routing']['runtime']['load_balance']:
            config['routing']['runtime']['load_balance']['options'] = CommentedMap()
        
        options = runtime_config.load_balance.options
        config['routing']['runtime']['load_balance']['options']['latency_buffer'] = options.latency_buffer
        config['routing']['runtime']['load_balance']['options']['latency_window'] = options.latency_window
        config['routing']['runtime']['load_balance']['options']['usage_window'] = options.usage_window
        
        # Atomic write: write to temporary file first, then rename
        temp_path = f"{self.config_path}.tmp"
        try:
            # Write to temporary file (still within lock)
            with open(temp_path, 'w', encoding='utf-8') as f:
                yaml_obj.dump(config, f)
                # Ensure data is flushed to disk
                f.flush()
                os.fsync(f.fileno())
            
            # Atomically replace original file with temporary file
            os.replace(temp_path, self.config_path)
            
            # Ensure directory entry is synced (important for data integrity)
            try:
                dir_fd = os.open(os.path.dirname(self.config_path), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except (OSError, IOError):
                # If directory sync fails, it's not critical
                pass
                
        except Exception as e:
            # Clean up temporary file on error
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except OSError:
                pass
            raise
    
    def _clear_default_model_in_file(self) -> None:
        """
        Clear default_model and default_model_instance_id in configuration file
        
        This is called after removing a model that was the default model.
        Sets both values to None (will be serialized as null in YAML).
        """
        if not os.path.exists(self.config_path):
            return
        
        yaml_obj = YAML()
        yaml_obj.preserve_quotes = True
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml_obj.load(f)
        
        if config is None:
            return
        
        # Ensure routing section exists
        if 'routing' not in config:
            return
        
        # Set to None (will be serialized as null in YAML)
        if 'default_model' in config['routing']:
            config['routing']['default_model'] = None
        if 'default_model_instance_id' in config['routing']:
            config['routing']['default_model_instance_id'] = None
        
        # Atomic write
        temp_path = f"{self.config_path}.tmp"
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                yaml_obj.dump(config, f)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomically replace original file
            os.replace(temp_path, self.config_path)
            
            # Ensure directory entry is synced
            try:
                dir_fd = os.open(os.path.dirname(self.config_path), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except (OSError, IOError):
                # If directory sync fails, it's not critical
                pass
        except Exception as e:
            # Clean up temporary file on error
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except OSError:
                pass
            raise
    
    def get_routing_config(self) -> RoutingConfig:
        """Get routing configuration"""
        return self.routing_config
    
    def persist_routing_config(self) -> None:
        """
        Persist routing configuration (health_check and retry_policy) to file.
        
        Updates the routing.health_check and routing.retry_policy sections
        in the YAML configuration file using atomic write.
        
        Raises:
            FileNotFoundError: If config file doesn't exist
            Exception: If write operation fails
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        yaml_obj = YAML()
        yaml_obj.preserve_quotes = True
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml_obj.load(f)
        
        if config is None:
            config = CommentedMap()
        
        # Ensure routing section exists
        if 'routing' not in config:
            config['routing'] = CommentedMap()
        
        # Update health_check section
        health_config = self.routing_config.health_check
        health_dict = CommentedMap()
        health_dict['lightweight_enabled'] = bool(health_config.lightweight_enabled)
        health_dict['lightweight_interval'] = int(health_config.lightweight_interval)
        health_dict['actual_request_enabled'] = bool(health_config.actual_request_enabled)
        health_dict['actual_request_interval'] = int(health_config.actual_request_interval)
        health_dict['timeout'] = int(health_config.timeout)
        config['routing']['health_check'] = health_dict
        
        # Update retry_policy section
        retry_config = self.routing_config.retry_policy
        retry_dict = CommentedMap()
        retry_dict['max_attempts'] = int(retry_config.max_attempts)
        retry_dict['backoff_factor'] = int(retry_config.backoff_factor)
        retry_dict['base_delay'] = int(retry_config.base_delay)
        retry_dict['max_delay'] = int(retry_config.max_delay)
        config['routing']['retry_policy'] = retry_dict
        
        # Update timeout
        config['routing']['timeout'] = int(self.routing_config.timeout)
        
        # Update runtime configuration
        runtime_config = self.routing_config.runtime
        if 'runtime' not in config['routing']:
            config['routing']['runtime'] = CommentedMap()
        
        config['routing']['runtime']['mode'] = str(runtime_config.mode)
        
        # Update load_balance config
        if 'load_balance' not in config['routing']['runtime']:
            config['routing']['runtime']['load_balance'] = CommentedMap()
        
        config['routing']['runtime']['load_balance']['strategy'] = str(runtime_config.load_balance.strategy)
        
        # Update options
        if 'options' not in config['routing']['runtime']['load_balance']:
            config['routing']['runtime']['load_balance']['options'] = CommentedMap()
        
        options = runtime_config.load_balance.options
        config['routing']['runtime']['load_balance']['options']['latency_buffer'] = float(options.latency_buffer)
        config['routing']['runtime']['load_balance']['options']['latency_window'] = int(options.latency_window)
        config['routing']['runtime']['load_balance']['options']['usage_window'] = int(options.usage_window)
        
        # Atomic write: write to temporary file first, then rename
        temp_path = f"{self.config_path}.tmp"
        try:
            # Write to temporary file
            with open(temp_path, 'w', encoding='utf-8') as f:
                yaml_obj.dump(config, f)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomically replace original file
            os.replace(temp_path, self.config_path)
            
            # Ensure directory entry is synced
            try:
                dir_fd = os.open(os.path.dirname(self.config_path), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except (OSError, IOError):
                # If directory sync fails, it's not critical
                pass
                
        except Exception as e:
            # Clean up temporary file on error
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except OSError:
                pass
            raise

    def update_gateway_config(
        self,
        updates: Dict[str, Any],
        persist: bool = False,
        require_file_lock: bool = False
    ) -> bool:
        """
        Update gateway configuration fields.

        Args:
            updates: Dict of gateway fields to update (e.g., {'remote_access': True, 'port': 8080})
            persist: Whether to persist changes to YAML file
            require_file_lock: Whether to acquire file lock before persisting

        Returns:
            True if update succeeded
        """
        # Validate updates
        valid_keys = {'remote_access', 'port'}
        invalid_keys = set(updates.keys()) - valid_keys
        if invalid_keys:
            logger.error(f"Invalid gateway config keys: {invalid_keys}")
            return False

        # Validate values
        if 'remote_access' in updates and not isinstance(updates['remote_access'], bool):
            logger.error(f"'remote_access' must be a boolean, got {type(updates['remote_access']).__name__}")
            return False
        if 'port' in updates:
            port = updates['port']
            if not isinstance(port, int) or port < 1 or port > 65535:
                logger.error(f"'port' must be an integer between 1 and 65535, got {port}")
                return False

        # Update raw config — save rollback state before mutation
        gateway_existed = 'gateway' in self._raw_config
        old_gateway = dict(self._raw_config.get('gateway', {}))
        if not gateway_existed:
            self._raw_config['gateway'] = {}
        self._raw_config['gateway'].update(updates)

        # Persist if requested
        if persist:
            try:
                if require_file_lock:
                    with self._config_lock():
                        self._persist_gateway_config()
                else:
                    self._persist_gateway_config()
            except Exception as e:
                logger.error(f"Failed to persist gateway config: {e}")
                # Rollback _raw_config on persist failure
                if gateway_existed:
                    self._raw_config['gateway'] = old_gateway
                else:
                    del self._raw_config['gateway']
                return False

        return True

    def _persist_gateway_config(self) -> None:
        """
        Persist gateway configuration to YAML file.

        Updates the gateway section in the YAML configuration file using atomic write.
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        yaml_obj = YAML()
        yaml_obj.preserve_quotes = True

        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml_obj.load(f)

        if config is None:
            config = CommentedMap()

        # Ensure gateway section exists
        if 'gateway' not in config:
            config['gateway'] = CommentedMap()

        gateway = self._raw_config.get('gateway', {})

        # Update fields
        for key, value in gateway.items():
            if key in ('remote_access', 'port'):
                config['gateway'][key] = value

        # Atomic write
        temp_path = f"{self.config_path}.tmp"
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                yaml_obj.dump(config, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self.config_path)
            try:
                dir_fd = os.open(os.path.dirname(self.config_path), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except (OSError, IOError):
                pass
        except Exception as e:
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except OSError:
                pass
            raise

    def get_all_instances(self, model_name: str) -> List[ModelConfig]:
        """
        Get all instances of a specific model name
        
        Args:
            model_name: Model name to search for
            
        Returns:
            List of ModelConfig instances with the given name
        """
        if model_name not in self.model_name_index:
            return []
        instance_ids = self.model_name_index[model_name]
        return [self.models[iid] for iid in instance_ids if iid in self.models]
    
    def get_all_healthy_models(self) -> List[ModelConfig]:
        """
        Get all healthy model instances

        Returns:
            List of all healthy ModelConfig instances
        """
        return [m for m in self.models.values() if m.is_healthy]

    def _get_highest_priority_model_name(self) -> Optional[str]:
        """Get the name of the model with the highest priority among healthy instances"""
        healthy_models = self.get_all_healthy_models()
        if not healthy_models:
            if not self.models:
                return None
            best = max(self.models.values(), key=lambda m: m.priority)
            return best.name
        best = max(healthy_models, key=lambda m: m.priority)
        return best.name

    def _update_default_model_if_needed(self):
        """Re-evaluate and update default_model if it's not set"""
        if not self.default_model:
            self.default_model = self._get_highest_priority_model_name()
            if self.default_model:
                logger.info(f"Auto-set default_model to highest priority: {self.default_model}")
    
    def get_model_status(self) -> Dict[str, Any]:
        """Get status of all models"""
        # Convert RoutingConfig to dict for JSON serialization
        routing_dict = {
            "default_model": self.routing_config.default_model,
            "default_model_instance_id": self.routing_config.default_model_instance_id,
            "timeout": self.routing_config.timeout,
            "health_check": {
                "lightweight_enabled": self.routing_config.health_check.lightweight_enabled,
                "lightweight_interval": self.routing_config.health_check.lightweight_interval,
                "actual_request_enabled": self.routing_config.health_check.actual_request_enabled,
                "actual_request_interval": self.routing_config.health_check.actual_request_interval,
                "timeout": self.routing_config.health_check.timeout
            },
            "retry_policy": {
                "max_attempts": self.routing_config.retry_policy.max_attempts,
                "backoff_factor": self.routing_config.retry_policy.backoff_factor,
                "base_delay": self.routing_config.retry_policy.base_delay,
                "max_delay": self.routing_config.retry_policy.max_delay
            }
        }
        
        return {
            "total_instances": len(self.models),
            "unique_model_names": len(self.model_name_index),
            "default_model": self.default_model,
            "default_model_instance_id": self.default_model_instance_id,
            "available_models": list(self.model_name_index.keys()),
            "model_name_index": {
                name: len(instance_ids) 
                for name, instance_ids in self.model_name_index.items()
            },
            "routing_config": routing_dict,
            "status": "healthy"
        }
    
    def get_models_by_capability(self, capability: str) -> List[ModelConfig]:
        """
        Get all model instances that support a specific capability
        
        Supports both predefined capabilities (general, code, analysis, creative)
        and user-defined custom capabilities (any string defined in YAML).
        
        Returns models sorted by:
        1. is_healthy (True first)
        2. priority (higher first)
        
        Args:
            capability: The capability to search for. Can be:
                       - Predefined: "general", "code", "analysis", "creative"
                       - Custom: "medical", "legal", "financial", etc.
            
        Returns:
            List of ModelConfig objects sorted by health and priority
        """
        matching_models = []
        for model_config in self.models.values():
            if capability in model_config.capabilities and model_config.is_healthy:
                matching_models.append(model_config)
        
        # Sort by is_healthy (True first), then by priority (higher first)
        matching_models.sort(key=lambda m: (m.is_healthy, m.priority), reverse=True)
        
        logger.debug(
            f"Found {len(matching_models)} model instances for capability '{capability}': "
            f"{[f'{m.name}({m.instance_id[:8]})' for m in matching_models]}"
        )
        
        return matching_models
    
    @staticmethod
    def is_capability_request(model: str) -> bool:
        """
        Check if the model string is a capability request
        
        Args:
            model: The model string (e.g., "capability-code", "deepseek-chat")
            
        Returns:
            True if it's a capability request (starts with "capability-")
        """
        return bool(model and model.startswith(CAPABILITY_PREFIX))
    
    @staticmethod
    def extract_capability(model: str) -> str:
        """
        Extract capability name from capability request
        
        Args:
            model: The capability request string (e.g., "capability-code")
            
        Returns:
            The capability name (e.g., "code"), or empty string if invalid
        """
        if model and model.startswith(CAPABILITY_PREFIX):
            return model[len(CAPABILITY_PREFIX):]
        return ""


# Global config manager instance
_config_manager_instance: Optional[ModelConfigManager] = None


def get_config_manager() -> ModelConfigManager:
    """Get config manager instance (singleton pattern)"""
    global _config_manager_instance
    if _config_manager_instance is None:
        import os
        config_path = None
        
        # 1. Environment variable has highest priority
        config_path = os.getenv('SYSAIFRAME_CONFIG_PATH')
        if config_path:
            logger.info(f"Using config path from environment: {config_path}")
        else:
            # 2. Test environment: local config files fallback
            possible_paths = [
                'config/models.yaml',  # Current working directory
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'models.yaml'),  # Project root directory
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    logger.info(f"Using test environment config: {config_path}")
                    break
            
            # 3. Production environment fallback
            if not config_path:
                config_path = '/etc/sysaiframe/models.yaml'
                logger.info(f"Using default system config path: {config_path}")
        
        _config_manager_instance = ModelConfigManager(config_path=config_path)
    return _config_manager_instance


def reload_config_manager() -> bool:
    """Reload config manager configuration"""
    global _config_manager_instance
    if _config_manager_instance:
        return _config_manager_instance.reload_config()
    return False
