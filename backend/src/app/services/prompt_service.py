#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prompt Service - YAML-based prompt management with Git versioning.
Provides loading, caching, rendering, and binding resolution for prompts.
"""

from pathlib import Path
import yaml
import jinja2
import time
import hashlib
import json
import subprocess
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class PromptBinding:
    """Represents a resolved prompt binding."""
    target_type: str
    target_id: str
    locale: str
    prompt_file: str
    provider: str
    model: str
    params: Dict[str, Any]


@dataclass
class RenderedPrompt:
    """Represents a rendered prompt ready for LLM."""
    messages: List[Dict[str, str]]
    meta: Dict[str, Any]
    binding: PromptBinding


class PromptService:
    """
    YAML-based prompt service with hot caching and Git version management.
    
    Features:
    - YAML file loading with mtime-based hot cache
    - Jinja2 template rendering with variable substitution
    - Binding resolution (agent/workflow/global priority)
    - JSON Schema validation
    - Git operations for versioning
    """
    
    def __init__(self, base_dir: str = None):
        if base_dir is None:
            # Use path relative to this file
            current_file = Path(__file__)
            base_dir = current_file.parent.parent / "domain" / "prompts"
        self.base = Path(base_dir)
        self.cache: Dict[str, Tuple[float, Any]] = {}
        self.bindings_cache: Optional[Tuple[float, List[Dict]]] = None
        
        # Initialize Jinja2 environment with safe defaults
        self.jinja_env = jinja2.Environment(
            loader=jinja2.BaseLoader(),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Load JSON Schema for validation
        self.schema = self._load_schema()
        
        logger.info(f"PromptService initialized with base_dir: {self.base}")

    def _load_schema(self) -> Dict[str, Any]:
        """Load JSON Schema for prompt validation."""
        try:
            schema_path = self.base / "schema.json"
            if schema_path.exists():
                return json.loads(schema_path.read_text(encoding='utf-8'))
            else:
                logger.warning(f"Schema file not found: {schema_path}")
                return {}
        except Exception as e:
            logger.error(f"Failed to load schema: {e}")
            return {}

    def _get_file_mtime(self, rel_path: str) -> float:
        """Get file modification time safely."""
        try:
            path = self.base / rel_path
            return path.stat().st_mtime if path.exists() else 0.0
        except Exception:
            return 0.0

    def _load_yaml(self, rel_path: str) -> Dict[str, Any]:
        """
        Load YAML file with mtime-based caching.
        
        Args:
            rel_path: Relative path from base directory
            
        Returns:
            Parsed YAML data
            
        Raises:
            FileNotFoundError: If file doesn't exist
            yaml.YAMLError: If YAML parsing fails
        """
        path = self.base / rel_path
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")
            
        mtime = self._get_file_mtime(rel_path)
        cached = self.cache.get(rel_path)
        
        # Check cache validity
        if not cached or cached[0] < mtime:
            try:
                data = yaml.safe_load(path.read_text(encoding='utf-8'))
                self.cache[rel_path] = (mtime, data)
                logger.debug(f"Loaded and cached: {rel_path}")
            except yaml.YAMLError as e:
                logger.error(f"YAML parsing error in {rel_path}: {e}")
                raise
            except Exception as e:
                logger.error(f"Failed to load {rel_path}: {e}")
                raise
        
        return self.cache[rel_path][1]

    def _load_bindings(self) -> List[Dict[str, Any]]:
        """Load prompt bindings with caching."""
        bindings_path = "prompt_bindings.yaml"
        mtime = self._get_file_mtime(bindings_path)
        
        if not self.bindings_cache or self.bindings_cache[0] < mtime:
            try:
                data = self._load_yaml(bindings_path)
                bindings = data.get('bindings', [])
                self.bindings_cache = (mtime, bindings)
                logger.debug(f"Loaded {len(bindings)} prompt bindings")
            except Exception as e:
                logger.error(f"Failed to load bindings: {e}")
                return []
        
        return self.bindings_cache[1] if self.bindings_cache else []

    def resolve_binding(self, target_type: str, target_id: str, locale: str = "zh") -> PromptBinding:
        """
        Resolve prompt binding with priority: agent > workflow > global.
        
        Args:
            target_type: Type of target (agent, workflow, global)
            target_id: Target identifier
            locale: Language locale
            
        Returns:
            PromptBinding object
            
        Raises:
            ValueError: If no binding found
        """
        bindings = self._load_bindings()
        
        # Search with priority order
        for binding_data in bindings:
            if (binding_data.get('target_type') == target_type and 
                binding_data.get('target_id') == target_id and 
                binding_data.get('locale') == locale):
                
                # Parse model_ref (provider:model format)
                model_ref = binding_data.get('model_ref', 'siliconflow:Qwen/Qwen3-Coder-30B-A3B-Instruct')
                try:
                    provider, model = model_ref.split(':', 1)
                except ValueError:
                    logger.warning(f"Invalid model_ref format: {model_ref}, using default")
                    provider, model = 'siliconflow', 'Qwen/Qwen3-Coder-30B-A3B-Instruct'
                
                return PromptBinding(
                    target_type=target_type,
                    target_id=target_id,
                    locale=locale,
                    prompt_file=binding_data.get('prompt_file', ''),
                    provider=provider,
                    model=model,
                    params=binding_data.get('params', {})
                )
        
        raise ValueError(f"No binding found for {target_type}:{target_id}@{locale}")

    def render_prompt(self, binding: PromptBinding, variables: Dict[str, Any]) -> RenderedPrompt:
        """
        Render prompt with Jinja2 template variables.
        
        Args:
            binding: Resolved prompt binding
            variables: Template variables for rendering
            
        Returns:
            RenderedPrompt with messages and metadata
            
        Raises:
            FileNotFoundError: If prompt file not found
            jinja2.TemplateError: If template rendering fails
        """
        # Load prompt YAML
        prompt_data = self._load_yaml(binding.prompt_file)
        
        # Render messages
        messages = []
        for msg in prompt_data.get('messages', []):
            try:
                template = self.jinja_env.from_string(msg['content'])
                rendered_content = template.render(**variables)
                messages.append({
                    "role": msg['role'],
                    "content": rendered_content
                })
            except jinja2.TemplateError as e:
                logger.error(f"Template rendering error in {binding.prompt_file}: {e}")
                raise
        
        # Merge metadata from YAML and binding params
        meta = prompt_data.get('meta', {}).copy()
        meta.update(binding.params)
        
        return RenderedPrompt(
            messages=messages,
            meta=meta,
            binding=binding
        )

    def get_prompt(self, target_type: str, target_id: str, variables: Dict[str, Any], 
                   locale: str = "zh") -> RenderedPrompt:
        """
        High-level interface: resolve binding and render prompt.
        
        Args:
            target_type: Type of target (agent, workflow, global)
            target_id: Target identifier
            variables: Template variables
            locale: Language locale
            
        Returns:
            Rendered prompt ready for LLM
        """
        binding = self.resolve_binding(target_type, target_id, locale)
        return self.render_prompt(binding, variables)

    def list_prompts(self) -> List[Dict[str, Any]]:
        """
        List all available prompt files with metadata.
        
        Returns:
            List of prompt metadata dictionaries
        """
        prompts = []
        
        try:
            # Scan agents directory
            agents_dir = self.base / "agents"
            if agents_dir.exists():
                for yaml_file in agents_dir.glob("*.yaml"):
                    try:
                        data = self._load_yaml(f"agents/{yaml_file.name}")
                        prompts.append({
                            "id": data.get("id", yaml_file.stem),
                            "path": f"agents/{yaml_file.name}",
                            "agent": data.get("agent", "unknown"),
                            "locale": data.get("locale", "unknown"),
                            "version": data.get("version", 1),
                            "last_modified": self._get_file_mtime(f"agents/{yaml_file.name}")
                        })
                    except Exception as e:
                        logger.warning(f"Failed to read {yaml_file}: {e}")
            
            # Scan workflows directory
            workflows_dir = self.base / "workflows"
            if workflows_dir.exists():
                for yaml_file in workflows_dir.glob("*.yaml"):
                    try:
                        data = self._load_yaml(f"workflows/{yaml_file.name}")
                        prompts.append({
                            "id": data.get("id", yaml_file.stem),
                            "path": f"workflows/{yaml_file.name}",
                            "type": "workflow",
                            "locale": data.get("locale", "unknown"),
                            "version": data.get("version", 1),
                            "last_modified": self._get_file_mtime(f"workflows/{yaml_file.name}")
                        })
                    except Exception as e:
                        logger.warning(f"Failed to read {yaml_file}: {e}")
        
        except Exception as e:
            logger.error(f"Failed to list prompts: {e}")
        
        return prompts

    def validate_prompt(self, prompt_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate prompt data against JSON Schema.
        
        Args:
            prompt_data: Prompt data to validate
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        if not self.schema:
            return True, ["Schema not available"]
        
        try:
            import jsonschema
            jsonschema.validate(instance=prompt_data, schema=self.schema)
            return True, []
        except ImportError:
            logger.warning("jsonschema package not installed, skipping validation")
            return True, ["Validation skipped - jsonschema not installed"]
        except jsonschema.ValidationError as e:
            errors.append(f"Validation error: {e.message}")
        except Exception as e:
            errors.append(f"Validation failed: {e}")
        
        return len(errors) == 0, errors

    def save_prompt(self, rel_path: str, prompt_data: Dict[str, Any], 
                   commit_message: str = "Update prompt") -> bool:
        """
        Save prompt to YAML file with Git commit.
        
        Args:
            rel_path: Relative path for the prompt file
            prompt_data: Prompt data to save
            commit_message: Git commit message
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate prompt data
            is_valid, errors = self.validate_prompt(prompt_data)
            if not is_valid:
                logger.error(f"Prompt validation failed: {errors}")
                return False
            
            # Ensure directory exists
            file_path = self.base / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write YAML file
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(prompt_data, f, default_flow_style=False, 
                         allow_unicode=True, sort_keys=False)
            
            # Clear cache for this file
            if rel_path in self.cache:
                del self.cache[rel_path]
            
            # Git add and commit
            self._git_commit(rel_path, commit_message)
            
            logger.info(f"Saved prompt: {rel_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save prompt {rel_path}: {e}")
            return False

    def _git_commit(self, rel_path: str, message: str):
        """Execute git add and commit for the file."""
        try:
            file_path = self.base / rel_path
            subprocess.run(['git', 'add', str(file_path)], 
                          cwd=self.base.parent.parent.parent.parent, check=True)
            subprocess.run(['git', 'commit', '-m', message], 
                          cwd=self.base.parent.parent.parent.parent, check=True)
        except subprocess.CalledProcessError as e:
            logger.warning(f"Git commit failed: {e}")
        except Exception as e:
            logger.warning(f"Git operation error: {e}")

    def get_git_history(self, rel_path: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get Git history for a prompt file.
        
        Args:
            rel_path: Relative path of the file
            limit: Maximum number of commits to return
            
        Returns:
            List of commit information dictionaries
        """
        history = []
        try:
            file_path = self.base / rel_path
            cmd = ['git', 'log', '--oneline', f'-{limit}', '--', str(file_path)]
            result = subprocess.run(cmd, 
                                   cwd=self.base.parent.parent.parent.parent,
                                   capture_output=True, text=True, check=True)
            
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(' ', 1)
                    if len(parts) >= 2:
                        history.append({
                            "hash": parts[0],
                            "message": parts[1],
                            "short_hash": parts[0][:7]
                        })
        except Exception as e:
            logger.warning(f"Failed to get git history for {rel_path}: {e}")
        
        return history

    def clear_cache(self):
        """Clear all cached data."""
        self.cache.clear()
        self.bindings_cache = None
        logger.info("Prompt cache cleared")


# Global instance
prompt_service = PromptService()